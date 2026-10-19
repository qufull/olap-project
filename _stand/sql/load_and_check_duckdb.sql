
TRUNCATE TABLE fact_orders;
TRUNCATE TABLE dim_users;
TRUNCATE TABLE dim_restaurants;
TRUNCATE TABLE dim_couriers;
TRUNCATE TABLE dim_date;

INSERT INTO dim_users
SELECT 
    CAST(user_id AS BIGINT),
    CAST(name AS VARCHAR),
    CAST(phone AS VARCHAR),
    CAST(registration_date AS DATE)
FROM read_csv_auto('data/raw/dim_users.csv', header=True);

INSERT INTO dim_restaurants
SELECT 
    CAST(restaurant_id AS BIGINT),
    CAST(name AS VARCHAR),
    CAST(cuisine AS VARCHAR),
    CAST(rating AS DECIMAL(3, 2))
FROM read_csv_auto('data/raw/dim_restaurants.csv', header=True);

INSERT INTO dim_couriers
SELECT 
    CAST(courier_id AS BIGINT),
    CAST(name AS VARCHAR),
    CAST(vehicle_type AS VARCHAR)
FROM read_csv_auto('data/raw/dim_couriers.csv', header=True);

INSERT INTO dim_date
SELECT 
    d::DATE AS date_key,
    EXTRACT(YEAR FROM d)::INTEGER AS year,
    EXTRACT(MONTH FROM d)::INTEGER AS month,
    EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week, -- 1 = Пн .. 7 = Вс
    EXTRACT(ISODOW FROM d) IN (5, 6, 7) AS is_weekend -- Пт-Вс по паспорту
FROM generate_series(DATE '2025-10-01', DATE '2026-10-01', INTERVAL 1 DAY) AS t(d);

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
FROM read_csv_auto('data/raw/fact_orders.csv', header=True);