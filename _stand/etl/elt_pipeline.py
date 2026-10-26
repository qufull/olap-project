import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
# _stand/etl/elt_pipeline.py
from datetime import datetime
from pathlib import Path
import sys
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
DDL_PATH = BASE_DIR / "sql" / "ddl_duckdb.sql"
RAW_DIR = BASE_DIR / "data" / "raw"
LOG_PATH = Path(__file__).resolve().parent / "run_log.txt"


def log(msg: str, log_lines: list[str]):
  print(msg)
  log_lines.append(msg)


def run_single_elt(con: duckdb.DuckDBPyConnection, run_number: int, log_lines: list[str]):
  log(f"\n{'='*65}", log_lines)
  log(f"ЗАПУСК ELT-ПАЙПЛАЙНА #{run_number} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})", log_lines)
  log(f"{'='*65}", log_lines)

  # 1. EXTRACT & LOAD TO STAGING (Сырьё -> временные stg-таблицы)
  log("[1/4] Чтение CSV из data/raw/ во временные staging-таблицы...", log_lines)
  con.execute(f"""
        CREATE OR REPLACE TEMP TABLE stg_users AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_users.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_restaurants AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_restaurants.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_couriers AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/dim_couriers.csv', header=True);

        CREATE OR REPLACE TEMP TABLE stg_orders AS
        SELECT * FROM read_csv_auto('{RAW_DIR.as_posix()}/fact_orders.csv', header=True);
    """)

  # 2. DATA QUALITY CHECKS (Проверки качества — останавливают загрузку при ошибке)
  log("[2/4] Выполнение проверок качества данных (Data Quality Checks)...", log_lines)

  checks = [
      (
          "Пустые ключи или суммы (NULL в обязательных полях)",
          """
            SELECT COUNT(*) FROM stg_orders
            WHERE order_id IS NULL
               OR user_id IS NULL
               OR restaurant_id IS NULL
               OR courier_id IS NULL
               OR order_date IS NULL
               OR total_amount IS NULL
               OR status IS NULL
            """,
      ),
      (
          "Странный диапазон (сумма <= 0, время доставки <= 0, даты вне 2025-2026 или неверный статус)",
          """
            SELECT COUNT(*) FROM stg_orders
            WHERE CAST(total_amount AS DECIMAL(10,2)) <= 0
               OR CAST(order_date AS TIMESTAMP) < TIMESTAMP '2025-01-01'
               OR CAST(order_date AS TIMESTAMP) > TIMESTAMP '2027-01-01'
               OR (status != 'Отменен' AND TRY_CAST(delivery_time_minutes AS INTEGER) <= 0)
               OR status NOT IN ('Доставлен', 'Опоздание', 'Отменен')
            """,
      ),
      (
          "Дубликаты зерна факта (два заказа с одинаковым order_id)",
          """
            SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM stg_orders
            """,
      ),
      (
          "«Сироты» (Orphan keys: ссылки в факте на несуществующий user_id, restaurant_id или courier_id)",
          """
            SELECT
                COUNT(*) FILTER (WHERE u.user_id IS NULL) +
                COUNT(*) FILTER (WHERE r.restaurant_id IS NULL) +
                COUNT(*) FILTER (WHERE c.courier_id IS NULL)
            FROM stg_orders f
            LEFT JOIN stg_users u ON f.user_id = u.user_id
            LEFT JOIN stg_restaurants r ON f.restaurant_id = r.restaurant_id
            LEFT JOIN stg_couriers c ON f.courier_id = c.courier_id
            """,
      ),
  ]

  for check_name, sql_query in checks:
    bad_rows = con.execute(sql_query).fetchone()[0]
    if bad_rows > 0:
      err_msg = f"[FAIL] ПРОВЕРКА НЕ ПРОШЛА: {check_name} -> найдено битых строк: {bad_rows}. Загрузка остановлена!"
      log(err_msg, log_lines)
      raise RuntimeError(err_msg)
    log(f"  [OK] {check_name}: 0 ошибок", log_lines)

  # 3. ЗАГРУЗКА В ВИТРИНУ (Строгий порядок: сначала справочники, потом факт)
  # Стратегия идемпотентности: очищаем целевые таблицы перед вставкой в одной транзакции
  log("[3/4] Загрузка в чистовые таблицы (Справочники -> Факт)...", log_lines)
  con.execute("BEGIN TRANSACTION;")
  try:
    # Очищаем в обратном порядке (сначала факт, затем справочники)
    con.execute("""
            TRUNCATE TABLE fact_orders;
            TRUNCATE TABLE dim_users;
            TRUNCATE TABLE dim_restaurants;
            TRUNCATE TABLE dim_couriers;
            TRUNCATE TABLE dim_date;
        """)

    # 3.1. Сначала загружаем ВСЕ справочники
    con.execute("""
            INSERT INTO dim_users
            SELECT CAST(user_id AS BIGINT), CAST(name AS VARCHAR), CAST(phone AS VARCHAR), CAST(registration_date AS DATE)
            FROM stg_users;

            INSERT INTO dim_restaurants
            SELECT CAST(restaurant_id AS BIGINT), CAST(name AS VARCHAR), CAST(cuisine AS VARCHAR), CAST(rating AS DECIMAL(3, 2))
            FROM stg_restaurants;

            INSERT INTO dim_couriers
            SELECT CAST(courier_id AS BIGINT), CAST(name AS VARCHAR), CAST(vehicle_type AS VARCHAR)
            FROM stg_couriers;

            INSERT INTO dim_date
            SELECT 
                d::DATE AS date_key,
                EXTRACT(YEAR FROM d)::INTEGER AS year,
                EXTRACT(MONTH FROM d)::INTEGER AS month,
                EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
                EXTRACT(ISODOW FROM d) IN (5, 6, 7) AS is_weekend
            FROM generate_series(DATE '2025-10-01', DATE '2026-10-01', INTERVAL 1 DAY) AS t(d);
        """)
    log("  -> Справочники (dim_users, dim_restaurants, dim_couriers, dim_date) загружены.", log_lines)

    # 3.2. Только после справочников загружаем таблицу фактов
    con.execute("""
            INSERT INTO fact_orders
            SELECT 
                CAST(order_id AS BIGINT),
                CAST(user_id AS BIGINT),
                CAST(restaurant_id AS BIGINT),
                CAST(courier_id AS BIGINT),
                CAST(order_date AS TIMESTAMP),
                CAST(total_amount AS DECIMAL(10, 2)),
                TRY_CAST(delivery_time_minutes AS INTEGER),
                CAST(status AS VARCHAR)
            FROM stg_orders;
        """)
    log("  -> Таблица фактов (fact_orders) загружена.", log_lines)
    con.execute("COMMIT;")
  except Exception:
    con.execute("ROLLBACK;")
    raise

  # 4. СНЯТИЕ КОНТРОЛЬНЫХ МЕТРИК ПОСЛЕ ПРОГОНА
  log("[4/4] Контрольная сверка после загрузки:", log_lines)
  counts = con.execute("""
        SELECT
            (SELECT COUNT(*) FROM dim_users) AS users_cnt,
            (SELECT COUNT(*) FROM dim_restaurants) AS restaurants_cnt,
            (SELECT COUNT(*) FROM dim_couriers) AS couriers_cnt,
            (SELECT COUNT(*) FROM dim_date) AS dates_cnt,
            (SELECT COUNT(*) FROM fact_orders) AS fact_orders_cnt,
            (SELECT COUNT(*) FROM fact_orders WHERE status IN ('Доставлен', 'Опоздание')) AS delivered_orders_cnt,
            (SELECT SUM(total_amount) FROM fact_orders WHERE status IN ('Доставлен', 'Опоздание')) AS net_gmv_byn,
            (SELECT SUM(total_amount) FROM fact_orders) AS gross_gmv_byn
    """).fetchone()

  result = {
      "users_cnt": counts[0],
      "restaurants_cnt": counts[1],
      "couriers_cnt": counts[2],
      "dates_cnt": counts[3],
      "fact_orders_cnt": counts[4],
      "delivered_orders_cnt": counts[5],
      "net_gmv_byn": counts[6],
      "gross_gmv_byn": counts[7],
  }

  log(
      f"  Строки: dim_users={result['users_cnt']} | dim_restaurants={result['restaurants_cnt']} | "
      f"dim_couriers={result['couriers_cnt']} | dim_date={result['dates_cnt']} | fact_orders={result['fact_orders_cnt']}",
      log_lines,
  )
  log(
      f"  Метрика: delivered_orders={result['delivered_orders_cnt']} | "
      f"Net GMV (главная мера) = {result['net_gmv_byn']} BYN | Gross GMV = {result['gross_gmv_byn']} BYN",
      log_lines,
  )
  return result


def main():
  log_lines: list[str] = []
  con = duckdb.connect(str(DB_PATH))

  # Убеждаемся, что таблицы созданы (если база чистая)
  if DDL_PATH.exists():
    con.execute(DDL_PATH.read_text(encoding="utf-8"))

  try:
    # Запускаем два прогона подряд для доказательства идемпотентности (З05 п. 3)
    res1 = run_single_elt(con, run_number=1, log_lines=log_lines)
    res2 = run_single_elt(con, run_number=2, log_lines=log_lines)

    log(f"\n{'='*65}", log_lines)
    log("СРАВНЕНИЕ ДВУХ ПРОГОНОВ ПОДРЯД (ИДЕМПОТЕНТНОСТЬ):", log_lines)
    log(f"{'='*65}", log_lines)
    log(f"Прогон #1 -> fact_orders: {res1['fact_orders_cnt']} строк | Net GMV: {res1['net_gmv_byn']} BYN", log_lines)
    log(f"Прогон #2 -> fact_orders: {res2['fact_orders_cnt']} строк | Net GMV: {res2['net_gmv_byn']} BYN", log_lines)

    if res1 == res2:
      log("ИТОГ: ПРОЙДЕНО УСПЕШНО (Данные и главная метрика идентичны, задвоения нет).", log_lines)
    else:
      raise RuntimeError("ОШИБКА ИДЕМПОТЕНТНОСТИ: Результаты первого и второго прогона отличаются!")

  except Exception as e:
    log(f"\nАВАРИЙНАЯ ОСТАНОВКА ПАЙПЛАЙНА: {e}", log_lines)
    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    con.close()
    sys.exit(1)

  LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
  log(f"\nЛог двух прогонов сохранён в файл: {LOG_PATH}", log_lines)
  con.close()


if __name__ == "__main__":
  main()