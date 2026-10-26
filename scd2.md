---
title: "З06. История справочника (SCD2)"
assignment: З06
tags: [курс/olap, scd2, dim_couriers]
---

# З06. История справочника: Реализация SCD2 для `dim_couriers`

**Выбранный вариант:** **Вариант A — храним историю (SCD Type 2)**  
**Справочник:** `dim_couriers` (Курьеры)  
**Изменяемый атрибут:** `vehicle_type` (тип транспорта: `Пешком` $\to$ `Электросамокат` $\to$ `Автомобиль`).

---

## 1. Зачем здесь нужен SCD2 (Бизнес-контекст)

Курьеры со временем меняют средство передвижения (например, начинают пешком, затем копят на электросамокат или покупают автомобиль).

* **Если применить SCD1 (затирание старого значения):**
  При покупке курьером автомобиля в июле 2026 года в справочнике курьера сразу перезаписывается значение `vehicle_type = 'Автомобиль'`.
  * **Последствие для аналитики:** Все зимние и весенние заказы, которые курьер нёс пешком по снегу за 50 минут, в отчётах за октябрь-февраль задним числом припишутся к «Автомобилю». Анализ эффективности автокурьеров будет грубо искажён (завышенное среднее время, ложные опоздания).
* **При реализации SCD2 (версионирование строк):**
  Строка с типом «Пешком» остаётся в истории с меткой окончания действия, а для «Электросамоката» и «Автомобиля» заводятся новые версии строки. Исторический отчёт по каждому периоду показывает истинную скорость и SLA доставки.

---

## 2. Структура таблицы `dim_couriers_scd2`

В таблицу добавлены атрибуты версионирования:
- `courier_sk` (BIGINT PK) — технический суррогатный ключ конкретной версии записи.
- `courier_id` (BIGINT) — неизменный бизнес-ключ курьера.
- `vehicle_type` (VARCHAR) — исторический атрибут.
- `valid_from` (TIMESTAMP) — дата начала действия версии.
- `valid_to` (TIMESTAMP, NULL для актуальной) — дата закрытия версии.
- `is_current` (BOOLEAN) — признак текущей действующей версии (`TRUE` / `FALSE`).

```sql
CREATE TABLE dim_couriers_scd2 (
    courier_sk      BIGINT PRIMARY KEY,
    courier_id      BIGINT NOT NULL,
    name            VARCHAR NOT NULL,
    phone           VARCHAR NOT NULL,
    vehicle_type    VARCHAR NOT NULL,
    valid_from      TIMESTAMP NOT NULL,
    valid_to        TIMESTAMP,
    is_current      BOOLEAN NOT NULL
);
```

---

## 3. Демонстрация смены версий курьера #42

### А. Запрос, отображающий все версии одной сущности:

```sql
SELECT 
    courier_sk, courier_id, name, vehicle_type,
    valid_from, valid_to, is_current
FROM dim_couriers_scd2
WHERE courier_id = 42
ORDER BY valid_from;
```

**Результат выполнения:**
| courier_sk | courier_id | name | vehicle_type | valid_from | valid_to | is_current |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| 42 | 42 | Данилова Наталья Евгеньевна | **Пешком** | 2025-10-01 | 2026-03-01 | `false` |
| 801 | 42 | Данилова Наталья Евгеньевна | **Электросамокат** | 2026-03-01 | 2026-07-01 | `false` |
| 802 | 42 | Данилова Наталья Евгеньевна | **Автомобиль** | 2026-07-01 | `NULL` | `true` |

---

## 4. Как факт привязывается к нужной версии (Point-in-Time Join)

В аналитических запросах таблица фактов соединяется со справочником не только по `courier_id`, но и по условию попадания даты заказа `order_date` в интервал действия версии `[valid_from; valid_to)`:

```sql
SELECT 
    o.order_id,
    o.order_date,
    scd.courier_id,
    scd.name,
    scd.vehicle_type AS historical_vehicle_type,
    o.delivery_time_minutes,
    o.status
FROM fact_orders o
JOIN dim_couriers_scd2 scd 
  ON o.courier_id = scd.courier_id
 AND o.order_date >= scd.valid_from
 AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
WHERE o.courier_id = 42
ORDER BY o.order_date;
```

---

## 5. Доказательство ценности SCD2: Агрегация заказов по фактическому транспорту

```sql
SELECT 
    scd.vehicle_type,
    COUNT(o.order_id) AS orders_count,
    ROUND(AVG(o.delivery_time_minutes), 1) AS avg_delivery_minutes,
    COUNT(*) FILTER (WHERE o.status = 'Опоздание') AS late_orders_cnt,
    MIN(o.order_date) AS first_order_date,
    MAX(o.order_date) AS last_order_date
FROM fact_orders o
JOIN dim_couriers_scd2 scd 
  ON o.courier_id = scd.courier_id
 AND o.order_date >= scd.valid_from
 AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
WHERE o.courier_id = 42 AND o.status IN ('Доставлен', 'Опоздание')
GROUP BY scd.vehicle_type
ORDER BY MIN(o.order_date);
```

**Фактический результат по курьеру #42:**
| vehicle_type | orders_count | avg_delivery_minutes | late_orders_cnt | first_order_date | last_order_date |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Пешком** | 410 | 35.4 мин | 28 | 2025-10-02 | 2026-02-28 |
| **Электросамокат** | 366 | 35.5 мин | 28 | 2026-03-01 | 2026-06-29 |
| **Автомобиль** | 332 | 34.8 мин | 22 | 2026-07-01 | 2026-09-30 |

*Итог:* Благодаря SCD2 видна чистая динамика и корректное распределение нагрузки.

---

## 6. Как запустить проверку

```bash
python scripts/demo_scd2.py
```
Полный лог работы сохраняется в `reports/z06_scd2_output.txt`.
