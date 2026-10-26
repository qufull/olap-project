#!/usr/bin/env python3
"""Скрипт демонстрации З06: Slowly Changing Dimension Type 2 (SCD2).
Показывает версионирование курьеров логистической сети Яндекс Про (dim_couriers_scd2).
"""
from pathlib import Path
import sys
import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
SQL_PATH = BASE_DIR / "sql" / "scd2_demo.sql"
REPORT_PATH = BASE_DIR / "reports" / "z06_scd2_output.txt"


def main():
    print(f"Подключение к базе DuckDB: {DB_PATH}")
    con = duckdb.connect(str(DB_PATH))

    sql_content = SQL_PATH.read_text(encoding="utf-8")
    con.execute(sql_content)

    output_lines = []

    def log_print(msg: str):
        print(msg)
        output_lines.append(msg)

    log_print("=================================================================")
    log_print("ДЕМОНСТРАЦИЯ З06: ИСТОРИЯ СПРАВОЧНИКА (SCD2 ДЛЯ ЯНДЕКС ПРО)")
    log_print("=================================================================")

    log_print("\n--- 1. Все версии одной сущности (курьер ID 42 сменил транспорт и грейд дважды) ---")
    df_versions = con.sql("""
        SELECT 
            courier_sk, courier_id, name, vehicle_type, courier_tier,
            valid_from, valid_to, is_current
        FROM dim_couriers_scd2
        WHERE courier_id = 42
        ORDER BY valid_from;
    """).df()
    log_print(df_versions.to_string(index=False))

    log_print("\n--- 2. Корректный джойн заказов fact_orders на дату события (Point-in-Time Join) ---")
    df_orders = con.sql("""
        SELECT 
            o.order_id,
            o.order_date,
            scd.courier_id,
            scd.name AS courier_name,
            scd.vehicle_type AS historical_vehicle_type,
            scd.courier_tier AS historical_tier,
            scd.valid_from,
            scd.valid_to,
            o.cooking_time_min,
            o.transit_time_min,
            o.delivery_time_min,
            o.status
        FROM fact_orders o
        JOIN dim_couriers_scd2 scd 
          ON o.courier_id = scd.courier_id
         AND o.order_date >= scd.valid_from
         AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
        WHERE o.courier_id = 42
        ORDER BY o.order_date
        LIMIT 10;
    """).df()
    log_print(df_orders.to_string(index=False))

    log_print("\n--- 3. Доказательство ценности SCD2: агрегация заказов по транспорту на момент доставки ---")
    df_agg = con.sql("""
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
    """).df()
    log_print(df_agg.to_string(index=False))

    log_print("\nВывод: при SCD1 (перезапись) все заказы курьера за год ошибочно посчитались бы на Автомобиле,")
    log_print("исказив среднее время доставки и аналитику SLA. Благодаря SCD2 видна чистая история.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\nОтчёт по З06 сохранён в: {REPORT_PATH}")

    con.close()


if __name__ == "__main__":
    main()
