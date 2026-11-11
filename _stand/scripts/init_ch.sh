#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CH_HTTP="${CH_HTTP:-http://localhost:8123}"

echo "================================================================="
echo "Инициализация ClickHouse для платформы «Яндекс Доставка» (З07)"
echo "================================================================="

echo "Ожидание готовности ClickHouse на $CH_HTTP ..."
for i in $(seq 1 60); do
  if curl -sf "$CH_HTTP/ping" >/dev/null; then
    break
  fi
  sleep 1
  if [[ $i -eq 60 ]]; then
    echo "ClickHouse не ответил за 60 секунд. Проверьте запуск docker compose up -d" >&2
    exit 1
  fi
done

echo "1. Применение DDL схемы yandex_dw (MergeTree)..."
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^olap_clickhouse$'; then
  docker exec -i olap_clickhouse clickhouse-client --multiquery < "$ROOT/sql/ddl_clickhouse.sql"
else
  python3 "$ROOT/scripts/load_clickhouse.py" --url "$CH_HTTP"
  exit 0
fi

echo "2. Загрузка данных из data/raw/*.csv..."
load_csv() {
  local table="$1"
  local file="$2"
  if [[ -f "$file" ]]; then
    echo "  -> Загрузка $table из $file..."
    docker exec -i olap_clickhouse clickhouse-client --query "TRUNCATE TABLE IF EXISTS $table"
    docker exec -i olap_clickhouse clickhouse-client --query "INSERT INTO $table FORMAT CSVWithNames" < "$file"
  fi
}

DATA="$ROOT/data/raw"
load_csv "yandex_dw.dim_districts" "$DATA/dim_districts.csv"
load_csv "yandex_dw.dim_users" "$DATA/dim_users.csv"
load_csv "yandex_dw.dim_restaurants" "$DATA/dim_restaurants.csv"
load_csv "yandex_dw.dim_menu_items" "$DATA/dim_menu_items.csv"
load_csv "yandex_dw.dim_couriers" "$DATA/dim_couriers.csv"
load_csv "yandex_dw.fact_orders" "$DATA/fact_orders.csv"
load_csv "yandex_dw.fact_order_items" "$DATA/fact_order_items.csv"
load_csv "yandex_dw.fact_courier_shifts" "$DATA/fact_courier_shifts.csv"
load_csv "yandex_dw.fact_reviews" "$DATA/fact_reviews.csv"

echo "3. Генерация календаря yandex_dw.dim_date..."
docker exec -i olap_clickhouse clickhouse-client --query "
TRUNCATE TABLE IF EXISTS yandex_dw.dim_date;
INSERT INTO yandex_dw.dim_date
SELECT d AS date_key, toYear(d) AS year, toMonth(d) AS month, toDayOfWeek(d) AS day_of_week, toDayOfWeek(d) IN (5, 6, 7) AS is_weekend
FROM (SELECT toDate('2025-10-01') + number AS d FROM numbers(366));
"

echo "4. Контрольная сверка строк и главной метрики:"
docker exec -i olap_clickhouse clickhouse-client --query "
SELECT 'dim_districts' AS t, count() AS rows FROM yandex_dw.dim_districts
UNION ALL SELECT 'dim_users', count() FROM yandex_dw.dim_users
UNION ALL SELECT 'dim_restaurants', count() FROM yandex_dw.dim_restaurants
UNION ALL SELECT 'dim_menu_items', count() FROM yandex_dw.dim_menu_items
UNION ALL SELECT 'dim_couriers', count() FROM yandex_dw.dim_couriers
UNION ALL SELECT 'dim_date', count() FROM yandex_dw.dim_date
UNION ALL SELECT 'fact_orders', count() FROM yandex_dw.fact_orders
UNION ALL SELECT 'fact_order_items', count() FROM yandex_dw.fact_order_items
UNION ALL SELECT 'fact_courier_shifts', count() FROM yandex_dw.fact_courier_shifts
UNION ALL SELECT 'fact_reviews', count() FROM yandex_dw.fact_reviews
FORMAT Pretty
"

echo "5. Главная метрика (Net GMV):"
docker exec -i olap_clickhouse clickhouse-client --query "
SELECT count() AS delivered_orders, sum(total_amount) AS net_gmv_byn
FROM yandex_dw.fact_orders
WHERE status IN ('Доставлен', 'Опоздание')
FORMAT Pretty
"

echo "OK: yandex_dw в ClickHouse готов к работе!"
