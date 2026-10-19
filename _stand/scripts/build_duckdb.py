from pathlib import Path
import duckdb

# Автоматически определяет папку _stand (родитель папки scripts)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
DDL_PATH = BASE_DIR / "sql" / "ddl_duckdb.sql"
RAW_DIR = BASE_DIR / "data" / "raw"


def main():
  print(f"База данных будет создана/обновлена здесь: {DB_PATH}")
  con = duckdb.connect(str(DB_PATH))

  # 1. Выполняем DDL (пересоздаём таблицы, чтобы не было дублей при повторном запуске)
  con.execute(DDL_PATH.read_text(encoding="utf-8"))

  # 2. Грузим CSV из data/raw/
  con.execute(f"""
        INSERT INTO dim_users
        SELECT user_id, name, phone, CAST(registration_date AS DATE)
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_users.csv', header=True);

        INSERT INTO dim_restaurants
        SELECT restaurant_id, name, cuisine, CAST(rating AS DECIMAL(3, 2))
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_restaurants.csv', header=True);

        INSERT INTO dim_couriers
        SELECT courier_id, name, vehicle_type
        FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_couriers.csv', header=True);

        INSERT INTO dim_date
        SELECT 
            d::DATE AS date_key,
            EXTRACT(YEAR FROM d)::INTEGER AS year,
            EXTRACT(MONTH FROM d)::INTEGER AS month,
            EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
            EXTRACT(ISODOW FROM d) IN (5, 6, 7) AS is_weekend
        FROM generate_series(DATE '2025-10-01', DATE '2026-10-01', INTERVAL 1 DAY) AS t(d);

        INSERT INTO fact_orders
        SELECT 
            order_id,
            user_id,
            restaurant_id,
            courier_id,
            CAST(order_date AS TIMESTAMP),
            CAST(total_amount AS DECIMAL(10, 2)),
            TRY_CAST(delivery_time_minutes AS INTEGER),
            status
        FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_orders.csv', header=True);
    """)

  # 3. Выводим проверки для отчёта З03
  print("\n--- 1. Число строк в таблицах ---")
  con.sql("""
        SELECT 'dim_users' AS table_name, COUNT(*) AS rows FROM dim_users
        UNION ALL SELECT 'dim_restaurants', COUNT(*) FROM dim_restaurants
        UNION ALL SELECT 'dim_couriers', COUNT(*) FROM dim_couriers
        UNION ALL SELECT 'dim_date', COUNT(*) FROM dim_date
        UNION ALL SELECT 'fact_orders', COUNT(*) FROM fact_orders
    """).show()

  print("--- 2. Проверка на пустые ключи (NULL) и битые ссылки ---")
  con.sql("""
        SELECT
            COUNT(*) FILTER (WHERE f.order_id IS NULL OR f.user_id IS NULL OR f.restaurant_id IS NULL OR f.courier_id IS NULL) AS null_keys,
            COUNT(*) FILTER (WHERE u.user_id IS NULL) AS missing_users,
            COUNT(*) FILTER (WHERE r.restaurant_id IS NULL) AS missing_restaurants,
            COUNT(*) FILTER (WHERE c.courier_id IS NULL) AS missing_couriers
        FROM fact_orders f
        LEFT JOIN dim_users u ON f.user_id = u.user_id
        LEFT JOIN dim_restaurants r ON f.restaurant_id = r.restaurant_id
        LEFT JOIN dim_couriers c ON f.courier_id = c.courier_id
    """).show()

  print("--- 3. Главная мера (SUM total_amount) ---")
  con.sql("""
        SELECT
            COUNT(*) AS total_orders,
            SUM(total_amount) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS net_gmv_byn,
            SUM(total_amount) AS gross_gmv_byn
        FROM fact_orders
    """).show()

  con.close()


if __name__ == "__main__":
  main()