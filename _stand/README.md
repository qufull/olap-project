# Учебный стенд OLAP — проект «Доставка еды» (Constellation Schema)

**ФИО:** _Минович, Спарнюк, Телеш_  
**Группа:** _ИИ-231_  
**Домен:** Сервис экспресс-доставки еды из ресторанов  
**Архитектура:** Fact Constellation Schema (3 таблицы фактов, 6 измерений, 4 186 869 строк фактов)

---

## Статус выполнения лабораторных работ (З02 – З06)

| Задание | Тема | Реализованные файлы и артефакты | Статус |
| :--- | :--- | :--- | :---: |
| **З01** | Стенд и сырьё | `docker-compose.yml`, `scripts/init_ch.sh`, генератор `scripts/generate_data.py`, `data/raw/*.csv` | **Выполнено** |
| **З02** | Паспорт модели | [`passport.md`](passport.md), договор об ограничениях [`cut.md`](cut.md), схема созвездия | **Выполнено** |
| **З03** | Таблицы в DuckDB | DDL [`sql/ddl_duckdb.sql`](sql/ddl_duckdb.sql), сборщик [`scripts/build_duckdb.py`](scripts/build_duckdb.py), отчёт [`reports/z03_checks.txt`](reports/z03_checks.txt) | **Выполнено** |
| **З04** | Аналитический SQL | Эталон [`sql/canonical_metric.sql`](sql/canonical_metric.sql), запросы [`sql/analytics.sql`](sql/analytics.sql), раннер [`scripts/run_analytics.py`](scripts/run_analytics.py), отчёт [`reports/z04_analytics_output.txt`](reports/z04_analytics_output.txt) | **Выполнено** |
| **З05** | Загрузка и проверки | Пайплайн [`etl/elt_pipeline.py`](etl/elt_pipeline.py), 4 проверки качества, лог 2 прогонов [`etl/run_log.txt`](etl/run_log.txt) | **Выполнено** |
| **З06** | История справочника (SCD2) | Описание [`scd2.md`](scd2.md), DDL и демо [`sql/scd2_demo.sql`](sql/scd2_demo.sql), раннер [`scripts/demo_scd2.py`](scripts/demo_scd2.py), отчёт [`reports/z06_scd2_output.txt`](reports/z06_scd2_output.txt) | **Выполнено** |

---

## Архитектура модели данных (Fact Constellation)

* **3 таблицы фактов:**
  * `fact_orders` — Заказы на уровне чека (**1 000 000 строк**). Зерно: один оформленный заказ.
  * `fact_order_items` — Детализация позиций чека (**2 601 720 строк**). Зерно: позиция блюда в чеке.
  * `fact_reviews` — Отзывы и оценки клиентов (**585 149 строк**). Зерно: отзыв к выполненному заказу.
  * **Суммарный объём фактов:** **4 186 869 строк**.
* **5 справочников (измерений):**
  * `dim_districts` — 12 районов Минска с классификацией зон доставки.
  * `dim_users` — 100 000 клиентов сервиса.
  * `dim_restaurants` — 250 ресторанов с типами кухонь.
  * `dim_menu_items` — 2 500 блюд с категориями, ценами, весом и свойствами.
  * `dim_couriers` — 800 курьеров (реализован SCD2 в `dim_couriers_scd2`).
  * `dim_date` — 366 календарных дней периода `2025-10-01` — `2026-09-30`.

---

## Главная метрика (Net GMV)

- **Название:** Выручка по доставленным заказам (Net GMV / Оборот без учёта отмен).
- **Зафиксированный эталон:** **`54 595 838.25 BYN`** (по 899 763 доставленным заказам: 849 845 в срок + 49 918 с опозданием; 100 237 отмен).
- **Валовой оборот (Gross GMV):** **`60 648 870.64 BYN`**.
- **Файл эталона:** `sql/canonical_metric.sql`.

---

## Как запустить все проверки проекта

Из папки `_stand`:

```bash
# 1. Сборка витрины DuckDB (З03)
python scripts/build_duckdb.py

# 2. Выполнение аналитических запросов с оконными функциями (З04)
python scripts/run_analytics.py

# 3. Запуск ELT-пайплайна с проверками качества и доказательством идемпотентности (З05)
python etl/elt_pipeline.py

# 4. Демонстрация версионирования SCD2 и Point-in-Time джойна (З06)
python scripts/demo_scd2.py
```
Все отчёты сохраняются в папке `reports/` и `etl/run_log.txt`.
