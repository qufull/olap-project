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
- **[З03. Витрина DuckDB](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з07):** DDL-схема 10 таблиц (`sql/ddl_duckdb.sql`), скрипт сборки/проверки базы (`scripts/build_duckdb.py`), отчёт проверок (`reports/z03_checks.txt`).
- **[З04. Аналитический SQL](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з07):** Расчёт эталона главной метрики (`sql/canonical_metric.sql`), 3 аналитических запроса с окнами (`sql/analytics.sql`, `scripts/run_analytics.py`), отчёт (`reports/z04_analytics_output.txt`).
- **[З05. ELT-пайплайн и проверки качества](_stand/README.md#статус-выполнения-лабораторных-работ-з02--з07):** Автоматизированная загрузка через staging-слой, 4 Data Quality проверки и тестирование идемпотентности (`etl/elt_pipeline.py`), лог (`etl/run_log.txt`).
- **[З06. История справочника (SCD2)](_stand/scd2.md):** Версионирование транспорта и грейдов курьеров в Яндекс Про (`sql/scd2_demo.sql`, `scripts/demo_scd2.py`), Point-in-Time джойн, отчёт (`reports/z06_scd2_output.txt`).
- **[З07. Данные в ClickHouse](_stand/notes/order_by_rationale.md):** DDL на движке MergeTree (`sql/ddl_clickhouse.sql`), обоснование `ORDER BY` (`notes/order_by_rationale.md`), скрипт загрузки и сверки DuckDB $\leftrightarrow$ ClickHouse (`scripts/load_clickhouse.py`), отчёт сверки (`reports/z07_clickhouse_verification.txt`).

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

## Быстрый старт (Запуск всех лабораторных работ)

```bash
# Генерация сырых данных (при необходимости перегенерации)
python _stand/scripts/generate_data.py --orders 600000 --users 100000

# З03: Сборка витрины DuckDB
python _stand/scripts/build_duckdb.py

# З04: Выполнение аналитического SQL
python _stand/scripts/run_analytics.py

# З05: Запуск ELT-пайплайна с проверкой качества и идемпотентности
python _stand/etl/elt_pipeline.py

# З06: Демонстрация версионирования курьеров Яндекс Про (SCD2)
python _stand/scripts/demo_scd2.py

# З07: Загрузка в ClickHouse и сверка метрик с DuckDB
python _stand/scripts/load_clickhouse.py
```
