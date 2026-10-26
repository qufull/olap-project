-- =====================================================================
-- DDL Аналитической витрины (Fact Constellation Schema / Созвездие фактов)
-- СУБД: DuckDB
-- Домен: Сервис доставки еды (Food Delivery)
-- =====================================================================

DROP TABLE IF EXISTS fact_reviews;
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_menu_items;
DROP TABLE IF EXISTS dim_restaurants;
DROP TABLE IF EXISTS dim_users;
DROP TABLE IF EXISTS dim_couriers;
DROP TABLE IF EXISTS dim_districts;
DROP TABLE IF EXISTS dim_date;

-- 1. Справочник районов города
CREATE TABLE dim_districts (
    district_id         INTEGER PRIMARY KEY,
    district_name       VARCHAR NOT NULL,
    zone_type           VARCHAR NOT NULL,  -- Центральная, Спальная, Промышленная, Пригород
    delivery_multiplier DECIMAL(3, 2) NOT NULL
);

-- 2. Справочник клиентов
CREATE TABLE dim_users (
    user_id             BIGINT PRIMARY KEY,
    name                VARCHAR NOT NULL,
    phone               VARCHAR NOT NULL,
    registration_date   DATE NOT NULL,
    district_id         INTEGER REFERENCES dim_districts(district_id)
);

-- 3. Справочник ресторанов
CREATE TABLE dim_restaurants (
    restaurant_id       BIGINT PRIMARY KEY,
    name                VARCHAR NOT NULL,
    cuisine             VARCHAR NOT NULL,
    district_id         INTEGER REFERENCES dim_districts(district_id),
    rating              DECIMAL(3, 2) NOT NULL
);

-- 4. Справочник блюд / меню ресторанов
CREATE TABLE dim_menu_items (
    item_id             BIGINT PRIMARY KEY,
    restaurant_id       BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    name                VARCHAR NOT NULL,
    category            VARCHAR NOT NULL,  -- Пицца, Суши, Бургеры, Горячее, Супы, Салаты, Десерты, Напитки
    price               DECIMAL(8, 2) NOT NULL,
    weight_grams        INTEGER NOT NULL,
    is_spicy            BOOLEAN NOT NULL,
    is_vegetarian       BOOLEAN NOT NULL
);

-- 5. Справочник курьеров (SCD2 кандидат)
CREATE TABLE dim_couriers (
    courier_id          BIGINT PRIMARY KEY,
    name                VARCHAR NOT NULL,
    phone               VARCHAR NOT NULL,
    vehicle_type        VARCHAR NOT NULL   -- Автомобиль, Электросамокат, Велосипед, Пешком
);

-- 6. Календарное измерение времени (Календарь)
CREATE TABLE dim_date (
    date_key            DATE PRIMARY KEY,
    year                INTEGER NOT NULL,
    month               INTEGER NOT NULL,
    day_of_week         INTEGER NOT NULL,
    is_weekend          BOOLEAN NOT NULL
);

-- =====================================================================
-- ТАБЛИЦЫ ФАКТОВ (FACT TABLES)
-- =====================================================================

-- 7. Таблица фактов: Заказы (Grain: один оформленный клиентский чек)
CREATE TABLE fact_orders (
    order_id                BIGINT PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES dim_users(user_id),
    restaurant_id           BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    courier_id              BIGINT NOT NULL REFERENCES dim_couriers(courier_id),
    district_id             INTEGER NOT NULL REFERENCES dim_districts(district_id),
    order_date              TIMESTAMP NOT NULL,
    delivery_fee            DECIMAL(6, 2) NOT NULL,
    total_amount            DECIMAL(10, 2) NOT NULL,
    delivery_time_minutes   INTEGER,
    status                  VARCHAR NOT NULL   -- Доставлен, Опоздание, Отменен
);

-- 8. Таблица фактов: Товарные позиции чеков (Grain: одна позиция конкретного блюда в заказе)
CREATE TABLE fact_order_items (
    order_item_id       BIGINT PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES fact_orders(order_id),
    item_id             BIGINT NOT NULL REFERENCES dim_menu_items(item_id),
    quantity            INTEGER NOT NULL,
    unit_price          DECIMAL(8, 2) NOT NULL,
    item_discount       DECIMAL(8, 2) NOT NULL,
    subtotal_amount     DECIMAL(10, 2) NOT NULL
);

-- 9. Таблица фактов: Отзывы и оценки клиентов (Grain: один оставленный отзыв к заказу)
CREATE TABLE fact_reviews (
    review_id           BIGINT PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES fact_orders(order_id),
    user_id             BIGINT NOT NULL REFERENCES dim_users(user_id),
    restaurant_id       BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    courier_id          BIGINT NOT NULL REFERENCES dim_couriers(courier_id),
    review_date         TIMESTAMP NOT NULL,
    food_rating         INTEGER NOT NULL,      -- 1..5
    delivery_rating     INTEGER NOT NULL,      -- 1..5
    has_comment         BOOLEAN NOT NULL
);
