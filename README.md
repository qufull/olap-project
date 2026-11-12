# OLAP Project — Платформа «Яндекс Доставка» (Yandex Food & Express Delivery)

Учебный проект по курсу **«OLAP и аналитические хранилища данных»**.

**Команда:** Минович, Спарнюк, Телеш  
**Группа:** ИИ-231  
**СУБД хранилища:** DuckDB (локальный OLAP), ClickHouse + Metabase (Docker)

---

## Навигация по выполненным лабораторным работам

- **[З01. Стенд и сырьё](_stand/README.md):** Развёртывание окружения Docker (ClickHouse, Metabase), структура каталогов, генерация сырых CSV-данных.
- **[З02. Паспорт модели (Constellation Schema)](_stand/passport.md):**
  - Паспорт витрины: зерна 4 таблиц фактов (`fact_orders`, `fact_order_items`, `fact_courier_shifts`, `fact_reviews`), схема, меры и главная метрика.
  - Договор об ограничениях: [cut.md](_stand/cut.md).
- **[З03. Витрина DuckDB](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з11):** DDL-схема 10 таблиц (`sql/ddl_duckdb.sql`), скрипт сборки/проверки базы (`scripts/build_duckdb.py`), отчёт проверок (`reports/z03_checks.txt`).
- **[З04. Аналитический SQL](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з11):** Расчёт эталона главной метрики (`sql/canonical_metric.sql`), 3 аналитических запроса с окнами (`sql/analytics.sql`, `scripts/run_analytics.py`), отчёт (`reports/z04_analytics_output.txt`).
- **[З05. ELT-пайплайн и проверки качества](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з11):** Автоматизированная загрузка через staging-слой, 4 Data Quality проверки и тестирование идемпотентности (`etl/elt_pipeline.py`), лог (`etl/run_log.txt`).
- **[З06. История справочника (SCD2)](_stand/scd2.md):** Версионирование транспорта и грейдов курьеров в Яндекс Про (`sql/scd2_demo.sql`, `scripts/demo_scd2.py`), Point-in-Time джойн, отчёт (`reports/z06_scd2_output.txt`).
- **[З07. Данные в ClickHouse](_stand/notes/order_by_rationale.md):** DDL на движке MergeTree (`sql/ddl_clickhouse.sql`), обоснование `ORDER BY` (`notes/order_by_rationale.md`), скрипт загрузки и сверки DuckDB $\leftrightarrow$ ClickHouse (`scripts/load_clickhouse.py`), отчёт сверки (`reports/z07_clickhouse_verification.txt`).
- **[З08. Запросы и ключи ClickHouse](_stand/notes/partitions_and_keys.md):** Эталон метрики (`sql/canonical_metric_clickhouse.sql`), 3 аналитических запроса (`sql/analytics_clickhouse.sql`), обоснование партиций и `ORDER BY` (`notes/partitions_and_keys.md`), раннер (`scripts/run_analytics_ch.py`), отчёт (`reports/z08_analytics_ch_output.txt`).
- **[З09. Сводная таблица под график](_stand/notes/z09.md):** DDL таблицы агрегатов и MV (`sql/ddl_summary_mv.sql`), обоснование зёрен (`notes/z09.md`), сборщик (`scripts/build_summary_mv.py`), отчёт сверки (`reports/z09_summary_verification.txt`).
- **[З10. Дашборд Metabase](_stand/dashboards/dashboard_spec.md):** Архитектура дашборда поверх ClickHouse, макет сетки 12 колонок, глобальные фильтры, SQL всех виджетов (`dashboards/*.sql`).
- **[З11. SQL и карточка — одно число](_stand/notes/z11_protocol.md):** Протокол сверки эталона с карточкой BI (`notes/z11_protocol.md`), скрипт сверки 3 срезов (`scripts/verify_z11_reconciliation.py`), отчёт (`reports/z11_metric_reconciliation.txt`).
- **[З12. Сборка к сдаче](_stand/reports/checklist_defense.md):** Чеклист зачёта без красных флагов ([`reports/checklist_defense.md`](_stand/reports/checklist_defense.md)), мастер-скрипт сквозного запуска ([`scripts/run_all.py`](_stand/scripts/run_all.py)), устный путь данных на 1 минуту.

---

## Архитектура модели данных (Fact Constellation Schema)

- **4 Таблицы фактов (2 373 022 строки фактов суммарно):**
  - `fact_orders` — Заказы Яндекс Доставки с Surge-ценообразованием, тарифами, погодными условиями, комиссией платформы и выплатами курьерам (600 000 строк).
  - `fact_order_items` — Детализация позиций чека / блюда (1 278 404 строки).
  - `fact_courier_shifts` — Смены курьеров в Яндекс Про с часами на линии, выполненными заказами и бонусами (144 000 строк).
  - `fact_reviews` — Отзывы и клиентские оценки кухни и доставки с тегами жалоб (350 618 строк).
- **5 Справочников (Измерений):**
  - `dim_districts` — 12 районов города с базовыми тарифами и логистическим плечом.
  - `dim_users` — 100 000 клиентов платформы с подпиской Яндекс Плюс.
  - `dim_restaurants` — 250 заведений с партнерскими уровнями комиссии Take Rate (18..28%).
  - `dim_menu_items` — 2 500 блюд с категориями, весом и свойствами.
  - `dim_couriers` / `dim_couriers_scd2` — Курьеры Яндекс Про и версионирование транспорта (SCD2).
  - `dim_date` — Календарное измерение (366 дней).
- **Главная метрика (Net GMV):** Выручка по доставленным заказам = **`27 399 331.21 BYN`** (539 801 доставленный заказ).

---

---

## Быстрый старт за 5 шагов (Подъём и запуск проекта)

### Шаг 1. Запуск серверного окружения (Docker)
```bash
cd _stand
docker compose up -d
# Поднимает ClickHouse (порт 8123 / 9000) и Metabase (порт 3000)
```

### Шаг 2. Сквозной запуск всех этапов проекта одной командой (З01 — З11)
```bash
# Из корневой папки проекта:
python _stand/scripts/run_all.py
```
*Скрипт сквозного запуска последовательно выполняет генерацию сырья, сборку витрины DuckDB, ELT-пайплайн с проверками качества, демо SCD2, перенос в ClickHouse, построение сводки З09 и финальную сверку З11 за ~50 секунд.*

### Шаг 3. Где находится эталонный SQL главной метрики
* **Канонический файл DuckDB:** [`_stand/sql/canonical_metric.sql`](_stand/sql/canonical_metric.sql)
* **Канонический файл ClickHouse:** [`_stand/sql/canonical_metric_clickhouse.sql`](_stand/sql/canonical_metric_clickhouse.sql)
* **Эталонное число Net GMV:** **`27 399 331.21 BYN`** (539 801 доставленный заказ).

### Шаг 4. Как открыть дашборд и визуализировать метрики
1. Откройте в браузере: **`http://localhost:3000`** (Metabase).
2. Подключение к ClickHouse: хост `clickhouse` (или `localhost`), порт `8123`, база `yandex_dw`.
3. Спецификация макета, глобальных фильтров и SQL всех виджетов: [`_stand/dashboards/dashboard_spec.md`](_stand/dashboards/dashboard_spec.md).

### Шаг 5. Куда смотреть, если что-то пошло не так
* **Протоколы верификации:** папка [`_stand/reports/`](_stand/reports/) (`checklist_defense.md`, `z11_metric_reconciliation.txt`).
* **Логи валидации данных:** [`_stand/etl/run_log.txt`](_stand/etl/run_log.txt) (проверки NOT NULL, диапазонов, уникальности и внешних ключей).
* **Контроль округления копеек:** убедитесь, что денежные суммы объявлены как `DECIMAL`, а не `FLOAT`.

---

## Устный путь данных для комиссии (1–2 минуты на защите)

> **«Путь данных в нашем проекте выстроен следующим образом:**  
> 1. **Сырьё:** Генератор создаёт детерминированные CSV-файлы в слое bronze (`data/raw/`).  
> 2. **Загрузка и валидация:** Скрипт ELT-пайплайна принимает данные в staging-слой и прогоняет их через 4 обязательных шлюза качества (Data Quality Gates: отсутствие `NULL`, проверка диапазонов, уникальность первичных ключей и ссылочная целостность). Пайплайн на 100% идемпотентен — повторный прогон не задваивает строки.  
> 3. **Хранилище ClickHouse:** Справочники и факты созвездия разворачиваются на движке `MergeTree` с помесячным партиционированием `toYYYYMM(order_date)`. В ключе физической сортировки `ORDER BY` первым стоит `status`, что собирает все отменённые заказы в конец куска и сжимает колонку почти до нуля; второй стоит дата `order_date` для быстрого отсечения диапазонов гранулами по 8192 строки. Это разреженный индекс, а **не** уникальный первичный ключ, как в OLTP.  
> 4. **Эталонная метрика:** В файле `sql/canonical_metric.sql` зафиксирована формула главной метрики — валового оборота доставленных заказов (**Net GMV = 27 399 331.21 BYN** по 539 801 заказу).  
> 5. **Дашборд Metabase:** Виджеты обращаются напрямую к ClickHouse и к предрассчитанной сводке `agg_daily_district_tariff` (сжатие в 41 раз). Карточка KPI на дашборде при одинаковых фильтрах показывает **ровно то же число копейка-в-копейку (расхождение 0.00 BYN)** благодаря строгому использованию типов `DECIMAL`.  
> 
> * **Одна строка таблицы факта (`fact_orders`)** = один оформленный заказ клиента.  
> * **Главная мера** = валовой оборот доставленных заказов (Net GMV) в BYN».
