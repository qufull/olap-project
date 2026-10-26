import sys
from pathlib import Path
import time
import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
DDL_PATH = BASE_DIR / "sql" / "ddl_duckdb.sql"
RAW_DIR = BASE_DIR / "data" / "raw"

def main():
    print(f"База данных будет создана/обновлена здесь: {DB_PATH}")
    t0 = time.time()
    con = duckdb.connect(str(DB_PATH))

    # 1. Выполняем DDL
    print("[1/3] Пересоздание схемы DDL (Яндекс Доставка: Fact Constellation Schema)...")
    con.execute(DDL_PATH.read_text(encoding="utf-8"))

    # 2. Грузим CSV из data/raw/
    print("[2/3] Загрузка данных из data/raw/*.csv в DuckDB...")
    con.execute(f"""
        -- Измерения (Dimensions)
        INSERT INTO dim_districts
        SELECT district_id, district_name, zone_type, 
               CAST(base_delivery_cost AS DECIMAL(6, 2)),
               CAST(avg_distance_km AS DECIMAL(4, 1))
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_districts.csv', header=True);

        INSERT INTO dim_users
        SELECT user_id, name, phone, CAST(registration_date AS DATE), district_id, has_plus_subscription
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_users.csv', header=True);

        INSERT INTO dim_restaurants
        SELECT restaurant_id, name, cuisine, district_id, partnership_tier, CAST(rating AS DECIMAL(3, 2))
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_restaurants.csv', header=True);

        INSERT INTO dim_menu_items
        SELECT item_id, restaurant_id, name, category,
               CAST(price AS DECIMAL(8, 2)), weight_grams, is_spicy, is_vegetarian
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_menu_items.csv', header=True);

        INSERT INTO dim_couriers
        SELECT courier_id, name, phone, vehicle_type, courier_tier
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_couriers.csv', header=True);

        INSERT INTO dim_date
        SELECT 
            d::DATE AS date_key,
            EXTRACT(YEAR FROM d)::INTEGER AS year,
            EXTRACT(MONTH FROM d)::INTEGER AS month,
            EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
            EXTRACT(ISODOW FROM d) IN (5, 6, 7) AS is_weekend
        FROM generate_series(DATE '2025-10-01', DATE '2026-10-01', INTERVAL 1 DAY) AS t(d);

        -- Факты (Facts)
        INSERT INTO fact_orders
        SELECT 
            order_id, user_id, restaurant_id, courier_id, district_id,
            CAST(order_date AS TIMESTAMP),
            tariff, weather,
            CAST(surge_multiplier AS DECIMAL(3, 2)),
            CAST(items_subtotal AS DECIMAL(10, 2)),
            CAST(delivery_fee AS DECIMAL(6, 2)),
            CAST(surge_fee AS DECIMAL(6, 2)),
            CAST(discount_amount AS DECIMAL(6, 2)),
            CAST(total_amount AS DECIMAL(10, 2)),
            CAST(platform_commission AS DECIMAL(10, 2)),
            CAST(courier_payout AS DECIMAL(8, 2)),
            CAST(tip_amount AS DECIMAL(6, 2)),
            cooking_time_min, transit_time_min,
            TRY_CAST(delivery_time_min AS INTEGER),
            status
        FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_orders.csv', header=True);

        INSERT INTO fact_order_items
        SELECT 
            order_item_id, order_id, item_id, quantity,
            CAST(unit_price AS DECIMAL(8, 2)),
            CAST(discount_amount AS DECIMAL(8, 2)),
            CAST(subtotal_amount AS DECIMAL(10, 2))
        FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_order_items.csv', header=True);

        INSERT INTO fact_courier_shifts
        SELECT 
            shift_id, courier_id, CAST(shift_date AS DATE),
            CAST(hours_online AS DECIMAL(4, 2)),
            orders_completed,
            CAST(base_earnings AS DECIMAL(8, 2)),
            CAST(bonus_earnings AS DECIMAL(8, 2)),
            CAST(tips_total AS DECIMAL(6, 2)),
            CAST(total_payout AS DECIMAL(8, 2))
        FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_courier_shifts.csv', header=True);

        INSERT INTO fact_reviews
        SELECT 
            review_id, order_id, user_id, restaurant_id, courier_id,
            CAST(review_date AS TIMESTAMP),
            food_rating, delivery_rating, complaint_tag, has_comment
        FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_reviews.csv', header=True);
    """)

    # 3. Проверки витрины
    print(f"[3/3] Выполнение контрольных проверок (время загрузки: {time.time() - t0:.2f} с)...")
    print("\n--- 1. Число строк во всех 10 таблицах модели ---")
    con.sql("""
        SELECT 'dim_districts' AS table_name, 'Измерение' AS role, COUNT(*) AS rows FROM dim_districts
        UNION ALL SELECT 'dim_users', 'Измерение', COUNT(*) FROM dim_users
        UNION ALL SELECT 'dim_restaurants', 'Измерение', COUNT(*) FROM dim_restaurants
        UNION ALL SELECT 'dim_menu_items', 'Измерение', COUNT(*) FROM dim_menu_items
        UNION ALL SELECT 'dim_couriers', 'Измерение', COUNT(*) FROM dim_couriers
        UNION ALL SELECT 'dim_date', 'Измерение', COUNT(*) FROM dim_date
        UNION ALL SELECT 'fact_orders', 'ФАКТ (Заказы)', COUNT(*) FROM fact_orders
        UNION ALL SELECT 'fact_order_items', 'ФАКТ (Позиции чеков)', COUNT(*) FROM fact_order_items
        UNION ALL SELECT 'fact_courier_shifts', 'ФАКТ (Смены курьеров)', COUNT(*) FROM fact_courier_shifts
        UNION ALL SELECT 'fact_reviews', 'ФАКТ (Отзывы)', COUNT(*) FROM fact_reviews
    """).show()

    print("--- 2. Проверка целостности внешних ключей (Broken Links / Orphans) ---")
    con.sql("""
        SELECT
            COUNT(*) FILTER (WHERE u.user_id IS NULL) AS missing_users,
            COUNT(*) FILTER (WHERE r.restaurant_id IS NULL) AS missing_restaurants,
            COUNT(*) FILTER (WHERE c.courier_id IS NULL) AS missing_couriers,
            COUNT(*) FILTER (WHERE d.district_id IS NULL) AS missing_districts
        FROM fact_orders f
        LEFT JOIN dim_users u ON f.user_id = u.user_id
        LEFT JOIN dim_restaurants r ON f.restaurant_id = r.restaurant_id
        LEFT JOIN dim_couriers c ON f.courier_id = c.courier_id
        LEFT JOIN dim_districts d ON f.district_id = d.district_id
    """).show()

    print("--- 3. Финансовые метрики Яндекс Доставки ---")
    con.sql("""
        SELECT
            COUNT(*) AS total_orders,
            SUM(total_amount) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS net_gmv_byn,
            SUM(platform_commission) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS platform_take_rate_byn,
            SUM(delivery_fee + surge_fee) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS total_delivery_revenue_byn,
            SUM(courier_payout) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS total_courier_payout_byn,
            ROUND(AVG(surge_multiplier), 2) AS avg_surge_multiplier
        FROM fact_orders
    """).show()

    con.close()
    print("Сборка витрины DuckDB успешно завершена!")

if __name__ == "__main__":
    main()
