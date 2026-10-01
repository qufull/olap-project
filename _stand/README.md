# Учебный стенд OLAP — проект «Доставка еды»

**ФИО:** _Минович, Спарнюк, Телеш_  
**Группа:** _ИИ-231_  
**Домен:** доставка еды (заказы, рестораны, курьеры, пользователи)

## Что в проекте

Учебный стенд курса (ClickHouse + Metabase в Docker, DuckDB локально) и мои исходные данные в `data/raw/`.
Из этого сырья в следующих заданиях соберу аналитическую модель (star).

## Как поднять

Нужен Docker Desktop. Из папки проекта:

```bash
docker compose up -d
chmod +x scripts/init_ch.sh
./scripts/init_ch.sh        
curl http://localhost:8123/ping
```

Ответ `Ok.` — ClickHouse работает.
Дополнительная проверка:

```bash
docker exec -it olap_clickhouse clickhouse-client \
  --query "SELECT count() FROM retail_dw.fact_sales"
```

Проверка DuckDB (локально, без Docker):

```bash
pip install duckdb
python scripts/duckdb_smoke.py
```

Остановка: `docker compose down` (с удалением данных: `docker compose down -v`).

## Порты

| Сервис | Порт |
|--------|------|
| ClickHouse HTTP | 8123 |
| ClickHouse native | 9000 |
| Metabase | 3000 |

## Где лежит сырьё

Папка `data/raw/` — мои данные (синтетические, CSV с заголовком, UTF-8).
Папка `data/sample/` — учебный sample курса (розница), он нужен только для проверки стенда.

| Файл | Строк | Поля |
|------|-------|------|
| `fact_orders.csv` | 50 000 | `order_id`, `user_id`, `restaurant_id`, `courier_id`, `order_date` (дата и время), `total_amount` (сумма заказа), `delivery_time_minutes`, `status` |
| `dim_users.csv` | 5 000 | `user_id`, `name`, `phone`, `registration_date` |
| `dim_restaurants.csv` | 150 | `restaurant_id`, `name`, `cuisine` (кухня), `rating` |
| `dim_couriers.csv` | 300 | `courier_id`, `name`, `vehicle_type` (вид транспорта) |

Период заказов: 2025-10-01 — 2026-10-01.
Статусы заказа: `Доставлен` (42 511), `Отменен` (5 023), `Опоздание` (2 466).
Связи: `fact_orders.user_id → dim_users`, `.restaurant_id → dim_restaurants`, `.courier_id → dim_couriers`
(пропусков и «висячих» ключей нет).

## Что буду считать

- **Метрика:** выручка (`sum(total_amount)`), число заказов, доля отмен и опозданий, среднее время доставки.
- **Вопросы:** какая кухня приносит больше выручки; как транспорт курьера влияет на время доставки и опоздания; как меняется число заказов по месяцам.


