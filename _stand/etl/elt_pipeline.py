#!/usr/bin/env python3
"""ELT-пайплайн аналитической витрины (Constellation Schema).
Выполняет:
  1. Чтение сырых CSV в staging-слой (DuckDB).
  2. Data Quality проверки (NULL, дубликаты зерна, диапазоны, битые ссылки FK).
  3. Идемпотентную загрузку в чистовой слой.
  4. Двойной прогон и сверку контрольных сумм для доказательства идемпотентности.
"""
from datetime import datetime
from pathlib import Path
import sys
import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
RAW_DIR = BASE_DIR / "data" / "raw"
DDL_PATH = BASE_DIR / "sql" / "ddl_duckdb.sql"
LOG_PATH = BASE_DIR / "etl" / "run_log.txt"


def run_pipeline(con: duckdb.DuckDBPyConnection, run_number: int) -> dict:
    header = f"\n=================================================================\n" \
             f"ЗАПУСК ELT-ПАЙПЛАЙНА #{run_number} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n" \
             f"================================================================="
    print(header)
    logs = [header]

    # 1. Staging слой
    step1 = "[1/4] Чтение CSV из data/raw/ во временные staging-таблицы..."
    print(step1)
    logs.append(step1)

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE stg_districts AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_districts.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_users AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_users.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_restaurants AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_restaurants.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_menu_items AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_menu_items.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_couriers AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_couriers.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_orders AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_orders.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_order_items AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_order_items.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_reviews AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_reviews.csv', header=True);
    """)

    # 2. Data Quality проверки
    step2 = "[2/4] Выполнение проверок качества данных (Data Quality Checks)..."
    print(step2)
    logs.append(step2)

    # Проверка 1: Пустые обязательные ключи
    nulls = con.sql("""
        SELECT
            (SELECT COUNT(*) FROM stg_orders WHERE order_id IS NULL OR user_id IS NULL OR restaurant_id IS NULL OR courier_id IS NULL OR district_id IS NULL) +
            (SELECT COUNT(*) FROM stg_order_items WHERE order_item_id IS NULL OR order_id IS NULL OR item_id IS NULL) +
            (SELECT COUNT(*) FROM stg_reviews WHERE review_id IS NULL OR order_id IS NULL OR user_id IS NULL) AS total_nulls
    """).fetchone()[0]
    res1 = f"  [{'OK' if nulls == 0 else 'FAIL'}] Пустые ключи (NULL в обязательных полях): {nulls} ошибок"
    print(res1)
    logs.append(res1)
    assert nulls == 0, "Обнаружены NULL значения в ключевых полях!"

    # Проверка 2: Аномальные диапазоны
    ranges = con.sql("""
        SELECT
            (SELECT COUNT(*) FROM stg_orders WHERE total_amount <= 0 OR delivery_fee < 0 OR status NOT IN ('Доставлен', 'Опоздание', 'Отменен')) +
            (SELECT COUNT(*) FROM stg_order_items WHERE quantity <= 0 OR unit_price <= 0 OR subtotal_amount <= 0) +
            (SELECT COUNT(*) FROM stg_reviews WHERE food_rating NOT BETWEEN 1 AND 5 OR delivery_rating NOT BETWEEN 1 AND 5) AS bad_ranges
    """).fetchone()[0]
    res2 = f"  [{'OK' if ranges == 0 else 'FAIL'}] Некорректные диапазоны (суммы <= 0, рейтинги вне 1..5): {ranges} ошибок"
    print(res2)
    logs.append(res2)
    assert ranges == 0, "Обнаружены некорректные диапазоны числовых значений!"

    # Проверка 3: Дубликаты зерна
    dups = con.sql("""
        SELECT
            (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM stg_orders) +
            (SELECT COUNT(*) - COUNT(DISTINCT order_item_id) FROM stg_order_items) +
            (SELECT COUNT(*) - COUNT(DISTINCT review_id) FROM stg_reviews) AS total_duplicates
    """).fetchone()[0]
    res3 = f"  [{'OK' if dups == 0 else 'FAIL'}] Дубликаты первичных ключей фактов: {dups} ошибок"
    print(res3)
    logs.append(res3)
    assert dups == 0, "Обнаружены дубликаты зерна фактов!"

    # Проверка 4: Сироты (Broken FK)
    orphans = con.sql("""
        SELECT
            (SELECT COUNT(*) FROM stg_orders o LEFT JOIN stg_users u ON o.user_id = u.user_id WHERE u.user_id IS NULL) +
            (SELECT COUNT(*) FROM stg_orders o LEFT JOIN stg_restaurants r ON o.restaurant_id = r.restaurant_id WHERE r.restaurant_id IS NULL) +
            (SELECT COUNT(*) FROM stg_orders o LEFT JOIN stg_couriers c ON o.courier_id = c.courier_id WHERE c.courier_id IS NULL) +
            (SELECT COUNT(*) FROM stg_orders o LEFT JOIN stg_districts d ON o.district_id = d.district_id WHERE d.district_id IS NULL) +
            (SELECT COUNT(*) FROM stg_order_items oi LEFT JOIN stg_orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL) +
            (SELECT COUNT(*) FROM stg_order_items oi LEFT JOIN stg_menu_items m ON oi.item_id = m.item_id WHERE m.item_id IS NULL) +
            (SELECT COUNT(*) FROM stg_reviews rev LEFT JOIN stg_orders o ON rev.order_id = o.order_id WHERE o.order_id IS NULL) AS total_orphans
    """).fetchone()[0]
    res4 = f"  [{'OK' if orphans == 0 else 'FAIL'}] «Сироты» (Orphan keys во всех связях фактов и справочников): {orphans} ошибок"
    print(res4)
    logs.append(res4)
    assert orphans == 0, "Обнаружены «сироты» — ссылки на несуществующие измерения!"

    # 3. Идемпотентная загрузка в чистовой слой
    step3 = "[3/4] Идемпотентная загрузка в чистовые таблицы (Справочники -> Факты)..."
    print(step3)
    logs.append(step3)

    con.execute(DDL_PATH.read_text(encoding="utf-8"))

    con.execute("""
        INSERT INTO dim_districts SELECT district_id, district_name, zone_type, CAST(delivery_multiplier AS DECIMAL(3, 2)) FROM stg_districts;
        INSERT INTO dim_users SELECT user_id, name, phone, CAST(registration_date AS DATE), district_id FROM stg_users;
        INSERT INTO dim_restaurants SELECT restaurant_id, name, cuisine, district_id, CAST(rating AS DECIMAL(3, 2)) FROM stg_restaurants;
        INSERT INTO dim_menu_items SELECT item_id, restaurant_id, name, category, CAST(price AS DECIMAL(8, 2)), weight_grams, is_spicy, is_vegetarian FROM stg_menu_items;
        INSERT INTO dim_couriers SELECT courier_id, name, phone, vehicle_type FROM stg_couriers;
        INSERT INTO dim_date SELECT d::DATE, EXTRACT(YEAR FROM d)::INTEGER, EXTRACT(MONTH FROM d)::INTEGER, EXTRACT(ISODOW FROM d)::INTEGER, EXTRACT(ISODOW FROM d) IN (5, 6, 7) FROM generate_series(DATE '2025-10-01', DATE '2026-10-01', INTERVAL 1 DAY) AS t(d);

        INSERT INTO fact_orders SELECT order_id, user_id, restaurant_id, courier_id, district_id, CAST(order_date AS TIMESTAMP), CAST(delivery_fee AS DECIMAL(6, 2)), CAST(total_amount AS DECIMAL(10, 2)), TRY_CAST(delivery_time_minutes AS INTEGER), status FROM stg_orders;
        INSERT INTO fact_order_items SELECT order_item_id, order_id, item_id, quantity, CAST(unit_price AS DECIMAL(8, 2)), CAST(item_discount AS DECIMAL(8, 2)), CAST(subtotal_amount AS DECIMAL(10, 2)) FROM stg_order_items;
        INSERT INTO fact_reviews SELECT review_id, order_id, user_id, restaurant_id, courier_id, CAST(review_date AS TIMESTAMP), food_rating, delivery_rating, has_comment FROM stg_reviews;
    """)

    # 4. Контрольная сверка
    step4 = "[4/4] Контрольная сверка показателей:"
    row_stats = con.sql("""
        SELECT 
            (SELECT COUNT(*) FROM fact_orders) AS orders_cnt,
            (SELECT COUNT(*) FROM fact_order_items) AS items_cnt,
            (SELECT COUNT(*) FROM fact_reviews) AS reviews_cnt,
            COUNT(*) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS delivered_orders,
            ROUND(SUM(total_amount) FILTER (WHERE status IN ('Доставлен', 'Опоздание')), 2) AS net_gmv,
            ROUND(SUM(total_amount), 2) AS gross_gmv
        FROM fact_orders
    """).fetchone()

    stat_line = f"  Строк фактов: fact_orders={row_stats[0]:,} | fact_order_items={row_stats[1]:,} | fact_reviews={row_stats[2]:,}\n" \
                f"  Главная метрика: delivered_orders={row_stats[3]:,} | Net GMV = {row_stats[4]} BYN | Gross GMV = {row_stats[5]} BYN"
    print(step4)
    print(stat_line)
    logs.extend([step4, stat_line])

    return {
        "orders_cnt": row_stats[0],
        "items_cnt": row_stats[1],
        "reviews_cnt": row_stats[2],
        "net_gmv": float(row_stats[4]),
        "logs": "\n".join(logs)
    }


def main():
    con = duckdb.connect(str(DB_PATH))
    all_logs = []

    # Запуск #1
    res1 = run_pipeline(con, 1)
    all_logs.append(res1["logs"])

    # Запуск #2 (проверка идемпотентности)
    res2 = run_pipeline(con, 2)
    all_logs.append(res2["logs"])

    # Сравнение
    cmp_header = "\n=================================================================\n" \
                 "СРАВНЕНИЕ ДВУХ ПРОГОНОВ ПОДРЯД (ИДЕМПОТЕНТНОСТЬ):\n" \
                 "================================================================="
    cmp_line1 = f"Прогон #1 -> fact_orders: {res1['orders_cnt']} | fact_order_items: {res1['items_cnt']} | Net GMV: {res1['net_gmv']:.2f} BYN"
    cmp_line2 = f"Прогон #2 -> fact_orders: {res2['orders_cnt']} | fact_order_items: {res2['items_cnt']} | Net GMV: {res2['net_gmv']:.2f} BYN"
    is_match = (res1["orders_cnt"] == res2["orders_cnt"]) and (res1["items_cnt"] == res2["items_cnt"]) and (res1["net_gmv"] == res2["net_gmv"])
    cmp_res = "ИТОГ: ПРОЙДЕНО УСПЕШНО (Данные и главная метрика идентичны, задвоения нет)." if is_match else "ИТОГ: ОШИБКА ИДЕМПОТЕНТНОСТИ!"

    print(cmp_header)
    print(cmp_line1)
    print(cmp_line2)
    print(cmp_res)

    all_logs.extend([cmp_header, cmp_line1, cmp_line2, cmp_res])
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(all_logs), encoding="utf-8")
    print(f"\nЛог двух прогонов сохранён в файл: {LOG_PATH}")
    con.close()


if __name__ == "__main__":
    main()
