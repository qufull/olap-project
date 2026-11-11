-- =====================================================================
-- DDL Хранилища данных в ClickHouse: Яндекс Доставка (Yandex Delivery DW)
-- СУБД: ClickHouse
-- Движок таблиц: MergeTree Family
-- Назначение: Задание З07 (Данные в ClickHouse)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS yandex_dw;

-- ---------------------------------------------------------------------
-- 1. Справочник районов и логистических зон города
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_districts
(
    district_id         Int32,
    district_name       String,
    zone_type           String,       -- Центр, Спальный, Промзона, Пригород
    base_delivery_cost  Decimal(6, 2),
    avg_distance_km     Decimal(4, 1)
)
ENGINE = MergeTree
ORDER BY district_id;

-- ---------------------------------------------------------------------
-- 2. Справочник пользователей / клиентов платформы
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_users
(
    user_id                 Int64,
    name                    String,
    phone                   String,
    registration_date       Date,
    district_id             Int32,
    has_plus_subscription   Bool
)
ENGINE = MergeTree
ORDER BY (district_id, user_id);

-- ---------------------------------------------------------------------
-- 3. Справочник ресторанов и Dark Kitchens
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_restaurants
(
    restaurant_id       Int64,
    name                String,
    cuisine             String,
    district_id         Int32,
    partnership_tier    String,       -- Стратегический (18%), Стандартный (22%), Базовый (28%)
    rating              Decimal(3, 2)
)
ENGINE = MergeTree
ORDER BY (cuisine, district_id, restaurant_id);

-- ---------------------------------------------------------------------
-- 4. Справочник позиций меню ресторанов
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_menu_items
(
    item_id             Int64,
    restaurant_id       Int64,
    name                String,
    category            String,
    price               Decimal(8, 2),
    weight_grams        Int32,
    is_spicy            Bool,
    is_vegetarian       Bool
)
ENGINE = MergeTree
ORDER BY (restaurant_id, category, item_id);

-- ---------------------------------------------------------------------
-- 5. Справочник курьеров (Текущий срез)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_couriers
(
    courier_id          Int64,
    name                String,
    phone               String,
    vehicle_type        String,       -- Пешком, Электросамокат, Велосипед, Автомобиль
    courier_tier        String        -- Новичок, Опытный, Топ-курьер
)
ENGINE = MergeTree
ORDER BY (vehicle_type, courier_tier, courier_id);

-- ---------------------------------------------------------------------
-- 5b. Справочник курьеров с версионированием истории (SCD2)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_couriers_scd2
(
    courier_sk          Int64,
    courier_id          Int64,
    name                String,
    phone               String,
    vehicle_type        String,
    courier_tier        String,
    valid_from          DateTime,
    valid_to            Nullable(DateTime),
    is_current          Bool
)
ENGINE = MergeTree
ORDER BY (courier_id, valid_from);

-- ---------------------------------------------------------------------
-- 6. Календарное измерение времени (Календарная сетка)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.dim_date
(
    date_key            Date,
    year                Int32,
    month               Int32,
    day_of_week         Int32,
    is_weekend          Bool
)
ENGINE = MergeTree
ORDER BY date_key;

-- =====================================================================
-- ТАБЛИЦЫ ФАКТОВ (FACT TABLES)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 7. ФАКТ 1: Заказы Яндекс Доставки (Grain: один оформленный заказ/доставка)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.fact_orders
(
    order_id                Int64,
    user_id                 Int64,
    restaurant_id           Int64,
    courier_id              Int64,
    district_id             Int32,
    order_date              DateTime,
    tariff                  String,        -- Экспресс, Стандарт, Эконом
    weather                 String,        -- Ясно, Дождь, Снегопад
    surge_multiplier        Decimal(3, 2), -- Коэффициент повышенного спроса (1.00..2.20)
    items_subtotal          Decimal(10, 2),-- Стоимость блюд
    delivery_fee            Decimal(6, 2), -- Базовый тариф доставки
    surge_fee               Decimal(6, 2), -- Надбавка за Surge
    discount_amount         Decimal(6, 2), -- Скидка (Яндекс Плюс)
    total_amount            Decimal(10, 2),-- Итоговый чек клиента (GMV)
    platform_commission     Decimal(10, 2),-- Комиссия Яндекс Доставки (Take Rate)
    courier_payout          Decimal(8, 2), -- Выплата курьеру
    tip_amount              Decimal(6, 2), -- Чаевые
    cooking_time_min        Int32,
    transit_time_min        Int32,
    delivery_time_min       Nullable(Int32), -- Время доставки (NULL при отмене)
    status                  String         -- Доставлен, Опоздание, Отменен
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(order_date)
ORDER BY (status, toDate(order_date), district_id, restaurant_id, courier_id, order_id);

-- ---------------------------------------------------------------------
-- 8. ФАКТ 2: Товарные позиции чеков (Grain: позиция конкретного блюда)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.fact_order_items
(
    order_item_id           Int64,
    order_id                Int64,
    item_id                 Int64,
    quantity                Int32,
    unit_price              Decimal(8, 2),
    discount_amount         Decimal(8, 2),
    subtotal_amount         Decimal(10, 2)
)
ENGINE = MergeTree
ORDER BY (order_id, item_id, order_item_id);

-- ---------------------------------------------------------------------
-- 9. ФАКТ 3: Рабочие смены курьеров в Яндекс Про (Grain: одна смена курьера)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.fact_courier_shifts
(
    shift_id                Int64,
    courier_id              Int64,
    shift_date              Date,
    hours_online            Decimal(4, 2), -- Отработано часов на линии
    orders_completed        Int32,
    base_earnings           Decimal(8, 2),
    bonus_earnings          Decimal(8, 2),
    tips_total              Decimal(6, 2),
    total_payout            Decimal(8, 2)  -- Итоговая выплата за смену
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(shift_date)
ORDER BY (shift_date, courier_id, shift_id);

-- ---------------------------------------------------------------------
-- 10. ФАКТ 4: Отзывы и оценки клиентов (Grain: один отзыв к заказу)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.fact_reviews
(
    review_id               Int64,
    order_id                Int64,
    user_id                 Int64,
    restaurant_id           Int64,
    courier_id              Int64,
    review_date             DateTime,
    food_rating             Int32,        -- Оценка кухни (1..5)
    delivery_rating         Int32,        -- Оценка доставки (1..5)
    complaint_tag           String,       -- Без нареканий, Остыло, Долгая доставка, Помята упаковка
    has_comment             Bool
)
ENGINE = MergeTree
ORDER BY (restaurant_id, courier_id, review_date, review_id);
