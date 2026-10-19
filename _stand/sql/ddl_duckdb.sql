

DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_users;
DROP TABLE IF EXISTS dim_restaurants;
DROP TABLE IF EXISTS dim_couriers;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_users (
    user_id           BIGINT PRIMARY KEY,
    name              VARCHAR NOT NULL,
    phone             VARCHAR,
    registration_date DATE NOT NULL
);

CREATE TABLE dim_restaurants (
    restaurant_id     BIGINT PRIMARY KEY,
    name              VARCHAR NOT NULL,
    cuisine           VARCHAR NOT NULL,
    rating            DECIMAL(3, 2)
);


CREATE TABLE dim_couriers (
    courier_id        BIGINT PRIMARY KEY,
    name              VARCHAR NOT NULL,
    vehicle_type      VARCHAR NOT NULL
);


CREATE TABLE dim_date (
    date_key          DATE PRIMARY KEY,
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL,
    day_of_week       INTEGER NOT NULL,
    is_weekend        BOOLEAN NOT NULL
);


CREATE TABLE fact_orders (
    order_id              BIGINT PRIMARY KEY,
    user_id               BIGINT NOT NULL,
    restaurant_id         BIGINT NOT NULL,
    courier_id            BIGINT NOT NULL,
    order_date            TIMESTAMP NOT NULL,
    total_amount          DECIMAL(10, 2) NOT NULL, -- Деньги строго в DECIMAL (BYN)
    delivery_time_minutes INTEGER,                 -- NULL для статуса 'Отменен'
    status                VARCHAR NOT NULL         -- 'Доставлен' | 'Опоздание' | 'Отменен'
);