# Учебный стенд OLAP — проект «Яндекс Доставка» (Constellation Schema)

**ФИО:** _Минович, Спарнюк, Телеш_  
**Группа:** _ИИ-231_  
**Домен:** Платформа экспресс-доставки еды из ресторанов (аналог Яндекс Еда / Яндекс Go)  
**Архитектура:** Fact Constellation Schema (4 таблицы фактов, 6 измерений, 2 373 022 строки фактов)

---

## Статус выполнения лабораторных работ (З02 – З11)

| Задание | Тема | Реализованные файлы и артефакты | Статус |
| :--- | :--- | :--- | :---: |
| **З01** | Стенд и сырьё | `docker-compose.yml`, `scripts/init_ch.sh`, генератор `scripts/generate_data.py`, `data/raw/*.csv` | **Выполнено** |
| **З02** | Паспорт модели | [`passport.md`](passport.md), договор об ограничениях [`cut.md`](cut.md), схема созвездия | **Выполнено** |
| **З03** | Таблицы в DuckDB | DDL [`sql/ddl_duckdb.sql`](sql/ddl_duckdb.sql), сборщик [`scripts/build_duckdb.py`](scripts/build_duckdb.py), отчёт [`reports/z03_checks.txt`](reports/z03_checks.txt) | **Выполнено** |
| **З04** | Аналитический SQL | Эталон [`sql/canonical_metric.sql`](sql/canonical_metric.sql), запросы [`sql/analytics.sql`](sql/analytics.sql), раннер [`scripts/run_analytics.py`](scripts/run_analytics.py), отчёт [`reports/z04_analytics_output.txt`](reports/z04_analytics_output.txt) | **Выполнено** |
| **З05** | Загрузка и проверки | Пайплайн [`etl/elt_pipeline.py`](etl/elt_pipeline.py), 4 проверки качества, лог 2 прогонов [`etl/run_log.txt`](etl/run_log.txt) | **Выполнено** |
| **З06** | История справочника (SCD2) | Описание [`scd2.md`](scd2.md), DDL и демо [`sql/scd2_demo.sql`](sql/scd2_demo.sql), раннер [`scripts/demo_scd2.py`](scripts/demo_scd2.py), отчёт [`reports/z06_scd2_output.txt`](reports/z06_scd2_output.txt) | **Выполнено** |
| **З07** | Данные в ClickHouse | DDL [`sql/ddl_clickhouse.sql`](sql/ddl_clickhouse.sql), обоснование [`notes/order_by_rationale.md`](notes/order_by_rationale.md), загрузчик/сверка [`scripts/load_clickhouse.py`](scripts/load_clickhouse.py), отчёт [`reports/z07_clickhouse_verification.txt`](reports/z07_clickhouse_verification.txt) | **Выполнено** |
| **З08** | Запросы и ключи CH | SQL [`sql/canonical_metric_clickhouse.sql`](sql/canonical_metric_clickhouse.sql), [`sql/analytics_clickhouse.sql`](sql/analytics_clickhouse.sql), заметка [`notes/partitions_and_keys.md`](notes/partitions_and_keys.md), раннер [`scripts/run_analytics_ch.py`](scripts/run_analytics_ch.py), отчёт [`reports/z08_analytics_ch_output.txt`](reports/z08_analytics_ch_output.txt) | **Выполнено** |
| **З09** | Сводная таблица (MV) | DDL [`sql/ddl_summary_mv.sql`](sql/ddl_summary_mv.sql), заметка [`notes/z09.md`](notes/z09.md), сборщик [`scripts/build_summary_mv.py`](scripts/build_summary_mv.py), отчёт [`reports/z09_summary_verification.txt`](reports/z09_summary_verification.txt) | **Выполнено** |
| **З10** | Дашборд Metabase | Спецификация [`dashboards/dashboard_spec.md`](dashboards/dashboard_spec.md), SQL виджетов [`dashboards/*.sql`](dashboards/), 2 глобальных фильтра | **Выполнено** |
| **З11** | SQL и карточка — одно число | Протокол сверки [`notes/z11_protocol.md`](notes/z11_protocol.md), скрипт проверки [`scripts/verify_z11_reconciliation.py`](scripts/verify_z11_reconciliation.py), отчёт [`reports/z11_metric_reconciliation.txt`](reports/z11_metric_reconciliation.txt) | **Выполнено** |
| **З12** | Сборка к сдаче | Чеклист зачёта [`reports/checklist_defense.md`](reports/checklist_defense.md), мастер-скрипт [`scripts/run_all.py`](scripts/run_all.py), устный путь данных | **Выполнено** |

---

## Архитектура модели данных (Fact Constellation)

* **4 таблицы фактов:**
  * `fact_orders` — Заказы Яндекс Доставки с Surge-ценообразованием, тарифами, погодными условиями, комиссией платформы и выплатами курьерам (**600 000 строк**). Зерно: один оформленный заказ.
  * `fact_order_items` — Детализация позиций чека / блюда (**1 278 404 строки**). Зерно: позиция блюда в чеке.
  * `fact_courier_shifts` — Смены курьеров в Яндекс Про с часами на линии, выполненными заказами и бонусами (**144 000 строк**). Зерно: одна смена курьера.
  * `fact_reviews` — Отзывы и клиентские оценки кухни и доставки с тегами жалоб (**350 618 строк**). Зерно: отзыв к выполненному заказу.
  * **Суммарный объём фактов:** **2 373 022 строки**.
* **5 справочников (измерений):**
  * `dim_districts` — 12 районов города с базовыми тарифами и логистическим плечом.
  * `dim_users` — 100 000 клиентов платформы с подпиской Яндекс Плюс.
  * `dim_restaurants` — 250 заведений с партнерскими уровнями комиссии Take Rate (18..28%).
  * `dim_menu_items` — 2 500 блюд с категориями, весом и свойствами.
  * `dim_couriers` — 800 курьеров Яндекс Про (реализован SCD2 в `dim_couriers_scd2`).
  * `dim_date` — 366 календарных дней периода `2025-10-01` — `2026-09-30`.

---

## Главная метрика (Net GMV)

- **Название:** Выручка по доставленным заказам (Net GMV / Оборот доставленных заказов).
- **Зафиксированный эталон:** **`27 399 331.21 BYN`** (по 539 801 доставленному заказу: 509 780 в срок + 30 021 с опозданием; 60 199 отмен).
- **Комиссионная выручка Яндекса (Platform Commission):** **`5 499 204.05 BYN`**.
- **Фонд выплат курьерам (Courier Payout):** **`4 876 167.06 BYN`**.
- **Средний Surge коэффициент повышенного спроса:** **`1.36x`**.
- **Файл эталона:** `sql/canonical_metric.sql`.

---

## Быстрый запуск стенда за 5 шагов

1. **Запуск Docker-контейнеров:**
   ```bash
   docker compose up -d
   ```
   *(Поднимает ClickHouse на `:8123` и Metabase на `:3000`)*.

2. **Сквозной прогон всех этапов (З01 — З11) одной командой:**
   ```bash
   python scripts/run_all.py
   ```
   *(Генерация данных, сборка DuckDB, ELT с 4 Data Quality проверками, SCD2, перенос в ClickHouse, построение сводки З09 и финальная сверка З11)*.

3. **Эталонный SQL главной метрики:**
   * Файлы: [`sql/canonical_metric.sql`](sql/canonical_metric.sql) (DuckDB) и [`sql/canonical_metric_clickhouse.sql`](sql/canonical_metric_clickhouse.sql) (ClickHouse).
   * Значение Net GMV: **`27 399 331.21 BYN`** (539 801 заказ).

4. **Дашборд Metabase:**
   * URL: **`http://localhost:3000`** (база `yandex_dw` в ClickHouse).
   * Спецификация и запросы всех виджетов: [`dashboards/dashboard_spec.md`](dashboards/dashboard_spec.md).

5. **Куда смотреть при ошибках:**
   * Чеклист готовности: [`reports/checklist_defense.md`](reports/checklist_defense.md).
   * Протоколы проверок и сверок: папка [`reports/`](reports/) и лог [`etl/run_log.txt`](etl/run_log.txt).

---

## Устный рассказ: Путь данных от сырья до карточки (1–2 минуты)

> «**Путь данных выстроен следующим образом:**  
> Исходные CSV-файлы (`data/raw/`) $\to$ ELT-скрипт с 4 шлюзами качества (NOT NULL, диапазоны, уникальность PK, отсутствие orphans) $\to$ витрина созвездия фактов в ClickHouse на движке `MergeTree` с помесячным партиционированием и физическим порядком сортировки `(status, order_date, district_id)`, который собирает отмены в конец куска и дает максимальное сжатие $\to$ эталонный SQL канонической метрики Net GMV $\to$ карточка и графики на дашборде Metabase с теми же фильтрами.  
> **Одна строка факта (`fact_orders`)** = один оформленный заказ клиента.  
> **Главная мера** = валовой оборот доставленных заказов (Net GMV) = 27 399 331.21 BYN (расхождение с карточкой дашборда ровно 0.00 BYN благодаря `DECIMAL`)».
