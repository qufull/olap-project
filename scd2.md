---
title: "З06. История справочника (SCD2)"
assignment: З06
tags: [курс/olap, scd2, yandex-pro, dim_couriers]
---

# З06. История справочника: Реализация SCD2 для `dim_couriers` (Яндекс Про)

**Выбранный вариант:** **Вариант A — храним историю (SCD Type 2)**  
**Справочник:** `dim_couriers` (Курьеры логистической сети Яндекс Про)  
**Изменяемые атрибуты:** `vehicle_type` (тип транспорта: `Пешком` $\to$ `Электросамокат` $\to$ `Автомобиль`) и `courier_tier` (грейд в Яндекс Про: `Новичок` $\to$ `Опытный` $\to$ `Топ-курьер`).

---

## 1. Зачем здесь нужен SCD2 (Бизнес-контекст Яндекс Доставки)

Курьеры со временем развивают квалификацию в Яндекс Про: новичок начинает пешим курьером, нарабатывает рейтинг, берёт в аренду электросамокат, а затем переходит на автодоставку.

* **Если применить SCD1 (затирание старого значения):**
  При получении статуса автокурьера в июле 2026 года в справочнике курьера сразу перезаписывается значение `vehicle_type = 'Автомобиль'` и `courier_tier = 'Топ-курьер'`.
  * **Последствие для аналитики:** Все заказы за прошлую осень и зиму, которые курьер нёс пешком по заснеженному городу, задним числом припишутся к поездкам на автомобиле. Аналитика SLA и выработки автокурьеров будет грубо искажена (ложное завышение среднего времени доставки на автомобиле и искажение логистических бенчмарков).
* **При реализации SCD2 (версионирование строк):**
  Старая версия строки закрывается датой окончания действия (`valid_to`), а для каждого нового этапа создаётся отдельная версия строки. Любой ретроспективный запрос соединяет заказ с версией курьера, актуальной именно в момент доставки.

---

## 2. Структура таблицы `dim_couriers_scd2`

В таблицу добавлены технические атрибуты версионирования:
- `courier_sk` (BIGINT PK) — суррогатный первичный ключ конкретной версии записи.
- `courier_id` (BIGINT) — бизнес-ключ курьера в платформе Яндекс Про.
- `vehicle_type` (VARCHAR) — исторический атрибут транспорта.
- `courier_tier` (VARCHAR) — исторический грейд в системе мотивации.
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
    courier_tier    VARCHAR NOT NULL,
    valid_from      TIMESTAMP NOT NULL,
    valid_to        TIMESTAMP,
    is_current      BOOLEAN NOT NULL
);
```

---

## 3. Демонстрация версий курьера #42

### А. Запрос, отображающий все версии одной сущности:

```sql
SELECT 
    courier_sk, courier_id, name, vehicle_type, courier_tier,
    valid_from, valid_to, is_current
FROM dim_couriers_scd2
WHERE courier_id = 42
ORDER BY valid_from;
```

**Фактический результат:**
| courier_sk | courier_id | name | vehicle_type | courier_tier | valid_from | valid_to | is_current |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 42 | 42 | Новиков Григорий Игоревич | **Пешком** | **Новичок** | 2025-10-01 | 2026-03-01 | `false` |
| 801 | 42 | Новиков Григорий Игоревич | **Электросамокат** | **Опытный** | 2026-03-01 | 2026-07-01 | `false` |
| 802 | 42 | Новиков Григорий Игоревич | **Автомобиль** | **Топ-курьер** | 2026-07-01 | `NULL` | `true` |

---

## 4. Как факт привязывается к нужной версии (Point-in-Time Join)

В аналитических запросах таблица заказов `fact_orders` соединяется с версионированным справочником по интервалу `order_date >= valid_from AND (order_date < valid_to OR valid_to IS NULL)`:

```sql
SELECT 
    o.order_id,
    o.order_date,
    scd.courier_id,
    scd.name,
    scd.vehicle_type AS historical_vehicle_type,
    scd.courier_tier AS historical_tier,
    o.transit_time_min,
    o.delivery_time_min,
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
    scd.courier_tier,
    COUNT(o.order_id) AS orders_count,
    ROUND(AVG(o.transit_time_min), 1) AS avg_transit_minutes,
    ROUND(AVG(o.delivery_time_min), 1) AS avg_total_delivery_minutes,
    COUNT(*) FILTER (WHERE o.status = 'Опоздание') AS late_orders_cnt,
    MIN(o.order_date) AS first_order_date,
    MAX(o.order_date) AS last_order_date
FROM fact_orders o
JOIN dim_couriers_scd2 scd 
  ON o.courier_id = scd.courier_id
 AND o.order_date >= scd.valid_from
 AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
WHERE o.courier_id = 42 AND o.status IN ('Доставлен', 'Опоздание')
GROUP BY scd.vehicle_type, scd.courier_tier
ORDER BY MIN(o.order_date);
```

**Фактический результат выполнения:**
| vehicle_type | courier_tier | orders_count | avg_transit_minutes | avg_total_delivery_minutes | late_orders_cnt | first_order_date | last_order_date |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Пешком** | **Новичок** | 413 | 44.2 мин | 64.4 мин | 25 | 2025-10-01 | 2026-02-28 |
| **Электросамокат** | **Опытный** | 399 | 43.6 мин | 63.6 мин | 15 | 2026-03-01 | 2026-06-30 |
| **Автомобиль** | **Топ-курьер** | 315 | 43.8 мин | 63.3 мин | 18 | 2026-07-02 | 2026-09-30 |

*Итог:* Благодаря SCD2 история логистической эффективности сохранена без искажений.

---

## 6. Как запустить проверку

```bash
python scripts/demo_scd2.py
```
Полный протокол выполнения сохранён в `reports/z06_scd2_output.txt`.
