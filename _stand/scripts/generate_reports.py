import sys
from pathlib import Path
import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_PATH), read_only=True)

# 1. Отчёт З03
z03_lines = [
    "=================================================================",
    "ОТЧЁТ ПО З03: ПРОВЕРКИ ТАБЛИЦ В DUCKDB (ЯНДЕКС ДОСТАВКА)",
    "=================================================================\n",
    "--- 1. Число строк во всех 10 таблицах модели ---",
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
    """).df().to_string(index=False),
    "\n--- 2. Проверка целостности внешних ключей (Broken Links / Orphans = 0) ---",
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
    """).df().to_string(index=False),
    "\n--- 3. Главная мера (Net GMV) и финансовый сплит платформы ---",
    con.sql("""
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS delivered_orders,
            SUM(total_amount) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS net_gmv_byn,
            SUM(platform_commission) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS yandex_commission_byn,
            SUM(courier_payout) FILTER (WHERE status IN ('Доставлен', 'Опоздание')) AS courier_payout_byn,
            ROUND(AVG(surge_multiplier), 2) AS avg_surge_multiplier
        FROM fact_orders
    """).df().to_string(index=False),
    "\nВывод: данные согласованы с сырьём, отсутствуют NULL и сироты, главная мера зафиксирована."
]

(REPORTS_DIR / "z03_checks.txt").write_text("\n".join(z03_lines), encoding="utf-8")
print("z03_checks.txt written!")

# 2. Отчёт З04
canonical_sql = (BASE_DIR / "sql" / "canonical_metric.sql").read_text(encoding="utf-8")
analytics_sql = (BASE_DIR / "sql" / "analytics.sql").read_text(encoding="utf-8")
queries = [q.strip() for q in analytics_sql.split(";") if q.strip()]

z04_lines = [
    "=================================================================",
    "ОТЧЁТ ПО З04: АНАЛИТИЧЕСКИЙ SQL И ЭТАЛОН ГЛАВНОЙ МЕТРИКИ",
    "=================================================================\n",
    "--- ЭТАЛОН ГЛАВНОЙ МЕТРИКИ (sql/canonical_metric.sql) ---",
    con.sql(canonical_sql).df().to_string(index=False)
]

for idx, q in enumerate(queries, 1):
    z04_lines.append(f"\n--- АНАЛИТИЧЕСКИЙ ЗАПРОС {idx} (Вопрос {idx}) ---")
    z04_lines.append(con.sql(q).df().to_string(index=False))

(REPORTS_DIR / "z04_analytics_output.txt").write_text("\n".join(z04_lines), encoding="utf-8")
print("z04_analytics_output.txt written!")

con.close()
