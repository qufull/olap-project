-- =====================================================================
-- DDL Хранилища данных: Яндекс Доставка (Yandex Food & Express Delivery)
-- СУБД: DuckDB
-- Архитектура: Fact Constellation Schema (4 таблицы фактов, 6 измерений)
-- =====================================================================

DROP TABLE IF EXISTS fact_reviews;
DROP TABLE IF EXISTS fact_courier_shifts;
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_menu_items;
DROP TABLE IF EXISTS dim_restaurants;
DROP TABLE IF EXISTS dim_users;
DROP TABLE IF EXISTS dim_couriers;
DROP TABLE IF EXISTS dim_districts;
DROP TABLE IF EXISTS dim_date;

-- 1. Справочник районов и логистических зон города
CREATE TABLE dim_districts (
    district_id         INTEGER PRIMARY KEY,
    district_name       VARCHAR NOT NULL,
    zone_type           VARCHAR NOT NULL,       -- Центр, Спальный, Промзона, Пригород
    base_delivery_cost  DECIMAL(6, 2) NOT NULL, -- Базовая стоимость доставки
    avg_distance_km     DECIMAL(4, 1) NOT NULL  -- Среднее логистическое плечо в км
);

-- 2. Справочник клиентов платформы
CREATE TABLE dim_users (
    user_id                 BIGINT PRIMARY KEY,
    name                    VARCHAR NOT NULL,
    phone                   VARCHAR NOT NULL,
    registration_date       DATE NOT NULL,
    district_id             INTEGER REFERENCES dim_districts(district_id),
    has_plus_subscription   BOOLEAN NOT NULL    -- Признак подписки Яндекс Плюс
);

-- 3. Справочник ресторанов и Dark Kitchens
CREATE TABLE dim_restaurants (
    restaurant_id       BIGINT PRIMARY KEY,
    name                VARCHAR NOT NULL,
    cuisine             VARCHAR NOT NULL,       -- Русская, Пицца, Суши, Бургеры и др.
    district_id         INTEGER REFERENCES dim_districts(district_id),
    partnership_tier    VARCHAR NOT NULL,       -- Стратегический (18%), Стандартный (22%), Базовый (28%)
    rating              DECIMAL(3, 2) NOT NULL  -- Рейтинг заведения (3.0..5.0)
);

-- 4. Справочник позиций меню
CREATE TABLE dim_menu_items (
    item_id             BIGINT PRIMARY KEY,
    restaurant_id       BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    name                VARCHAR NOT NULL,
    category            VARCHAR NOT NULL,       -- Пицца, Суши, Бургеры, Горячее, Супы, Десерты и т.д.
    price               DECIMAL(8, 2) NOT NULL,
    weight_grams        INTEGER NOT NULL,
    is_spicy            BOOLEAN NOT NULL,
    is_vegetarian       BOOLEAN NOT NULL
);

-- 5. Справочник курьеров Яндекс Про (SCD2 кандидат)
CREATE TABLE dim_couriers (
    courier_id          BIGINT PRIMARY KEY,
    name                VARCHAR NOT NULL,
    phone               VARCHAR NOT NULL,
    vehicle_type        VARCHAR NOT NULL,       -- Пешком, Электросамокат, Велосипед, Автомобиль
    courier_tier        VARCHAR NOT NULL        -- Новичок, Опытный, Топ-курьер
);

-- 6. Календарное измерение (Календарь)
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

-- 7. ФАКТ 1: Заказы Яндекс Доставки (Grain: один оформленный заказ/доставка)
CREATE TABLE fact_orders (
    order_id                BIGINT PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES dim_users(user_id),
    restaurant_id           BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    courier_id              BIGINT NOT NULL REFERENCES dim_couriers(courier_id),
    district_id             INTEGER NOT NULL REFERENCES dim_districts(district_id),
    order_date              TIMESTAMP NOT NULL,
    tariff                  VARCHAR NOT NULL,        -- Экспресс, Стандарт, Эконом
    weather                 VARCHAR NOT NULL,        -- Ясно, Дождь, Снегопад
    surge_multiplier        DECIMAL(3, 2) NOT NULL,  -- Коэффициент повышенного спроса (1.00..2.20)
    items_subtotal          DECIMAL(10, 2) NOT NULL, -- Стоимость блюд
    delivery_fee            DECIMAL(6, 2) NOT NULL,  -- Базовый тариф доставки
    surge_fee               DECIMAL(6, 2) NOT NULL,  -- Надбавка за Surge
    discount_amount         DECIMAL(6, 2) NOT NULL,  -- Скидка (Яндекс Плюс / промокоды)
    total_amount            DECIMAL(10, 2) NOT NULL, -- Итоговая сумма чека (GMV)
    platform_commission     DECIMAL(10, 2) NOT NULL, -- Комиссия Яндекс Доставки (Take Rate с ресторана)
    courier_payout          DECIMAL(8, 2) NOT NULL,  -- Выплата курьеру за доставку
    tip_amount              DECIMAL(6, 2) NOT NULL,  -- Чаевые курьеру
    cooking_time_min        INTEGER NOT NULL,        -- Время готовки рестораном
    transit_time_min        INTEGER NOT NULL,        -- Время курьера в пути
    delivery_time_min       INTEGER,                 -- Общее время доставки клиенту (NULL для отмен)
    status                  VARCHAR NOT NULL         -- Доставлен, Опоздание, Отменен
);

-- 8. ФАКТ 2: Товарные позиции чеков (Grain: одна позиция конкретного блюда в чеке)
CREATE TABLE fact_order_items (
    order_item_id           BIGINT PRIMARY KEY,
    order_id                BIGINT NOT NULL REFERENCES fact_orders(order_id),
    item_id                 BIGINT NOT NULL REFERENCES dim_menu_items(item_id),
    quantity                INTEGER NOT NULL,
    unit_price              DECIMAL(8, 2) NOT NULL,
    discount_amount         DECIMAL(8, 2) NOT NULL,
    subtotal_amount         DECIMAL(10, 2) NOT NULL
);

-- 9. ФАКТ 3: Рабочие смены курьеров в Яндекс Про (Grain: одна рабочая смена курьера)
CREATE TABLE fact_courier_shifts (
    shift_id                BIGINT PRIMARY KEY,
    courier_id              BIGINT NOT NULL REFERENCES dim_couriers(courier_id),
    shift_date              DATE NOT NULL,
    hours_online            DECIMAL(4, 2) NOT NULL,  -- Отработано часов на линии
    orders_completed        INTEGER NOT NULL,        -- Выполнено заказов за смену
    base_earnings           DECIMAL(8, 2) NOT NULL,  -- Базовая оплата
    bonus_earnings          DECIMAL(8, 2) NOT NULL,  -- Бонусы за слоты и скорость
    tips_total              DECIMAL(6, 2) NOT NULL,  -- Суммарные чаевые
    total_payout            DECIMAL(8, 2) NOT NULL   -- Итоговая сумма выплаты за смену
);

-- 10. ФАКТ 4: Отзывы и оценки клиентов (Grain: один оставленный отзыв к заказу)
CREATE TABLE fact_reviews (
    review_id               BIGINT PRIMARY KEY,
    order_id                BIGINT NOT NULL REFERENCES fact_orders(order_id),
    user_id                 BIGINT NOT NULL REFERENCES dim_users(user_id),
    restaurant_id           BIGINT NOT NULL REFERENCES dim_restaurants(restaurant_id),
    courier_id              BIGINT NOT NULL REFERENCES dim_couriers(courier_id),
    review_date             TIMESTAMP NOT NULL,
    food_rating             INTEGER NOT NULL,        -- Оценка блюд (1..5)
    delivery_rating         INTEGER NOT NULL,        -- Оценка доставки (1..5)
    complaint_tag           VARCHAR NOT NULL,        -- Без нареканий, Остыло, Долгая доставка и др.
    has_comment             BOOLEAN NOT NULL
);
