-- =====================================================================
-- Аналитический SQL для ClickHouse: Платформа «Яндекс Доставка»
-- Задание: З08 (Запросы и ключи)
-- СУБД: ClickHouse (движок MergeTree, синтаксис ClickHouse SQL)
-- =====================================================================

-- ---------------------------------------------------------------------
-- ВОПРОС 1: Юнит-экономика платформы, комиссия Яндекса (Take Rate) и маржинальность
-- «Каков объём GMV, комиссионная выручка Яндекса (platform_commission),
--  выплаты курьерам и чистая операционная прибыль платформы по типам кухонь помесячно,
--  а также доля комиссии каждой кухни в ежемесячной прибыли (SUM OVER)
--  и ранг кухни в структуре выручки месяца (DENSE_RANK)?»
-- Особенности ClickHouse: toStartOfMonth(toDate(o.order_date)), dense_rank()
-- ---------------------------------------------------------------------
WITH monthly_cuisine_economy AS (
    SELECT 
        toStartOfMonth(toDate(o.order_date)) AS order_month,
        r.cuisine AS cuisine,
        count(o.order_id) AS orders_cnt,
        round(sum(o.total_amount), 2) AS gmv_byn,
        round(sum(o.platform_commission), 2) AS yandex_take_rate_byn,
        round(sum(o.delivery_fee + o.surge_fee), 2) AS delivery_revenue_byn,
        round(sum(o.courier_payout), 2) AS courier_payout_byn,
        -- Чистая прибыль платформы = комиссия с ресторана + плата за доставку и surge - выплата курьеру
        round(sum(o.platform_commission + (o.delivery_fee + o.surge_fee) - o.courier_payout), 2) AS platform_net_margin_byn
    FROM yandex_dw.fact_orders AS o
    JOIN yandex_dw.dim_restaurants AS r ON o.restaurant_id = r.restaurant_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
    GROUP BY order_month, cuisine
)
SELECT 
    order_month,
    cuisine,
    orders_cnt,
    gmv_byn,
    yandex_take_rate_byn,
    courier_payout_byn,
    platform_net_margin_byn,
    round(platform_net_margin_byn * 100.0 / sum(platform_net_margin_byn) OVER (PARTITION BY order_month), 2) AS margin_share_in_month_pct,
    dense_rank() OVER (PARTITION BY order_month ORDER BY gmv_byn DESC) AS cuisine_gmv_rank
FROM monthly_cuisine_economy
ORDER BY order_month, cuisine_gmv_rank;


-- ---------------------------------------------------------------------
-- ВОПРОС 2: Динамический спрос (Surge Pricing), погодные аномалии и SLA
-- «Как погодные условия (Ясно, Дождь, Снегопад) и тарифы доставки (Экспресс, Стандарт, Эконом)
--  влияют на средний коэффициент Surge, средний чек доставки, время в пути курьера
--  и процент опозданий (>60 минут) в часы пик против обычных часов?»
-- Особенности ClickHouse: toHour(o.order_date), countIf(status = 'Опоздание')
-- ---------------------------------------------------------------------
WITH surge_weather_sla AS (
    SELECT 
        o.weather AS weather,
        o.tariff AS tariff,
        CASE 
            WHEN toHour(o.order_date) IN (12, 13, 18, 19, 20) THEN 'Час пик (12-14, 18-21)'
            ELSE 'Обычные часы'
        END AS time_window,
        o.order_id AS order_id,
        o.surge_multiplier AS surge_multiplier,
        o.delivery_fee + o.surge_fee AS total_delivery_cost,
        o.cooking_time_min AS cooking_time_min,
        o.transit_time_min AS transit_time_min,
        o.delivery_time_min AS delivery_time_min,
        o.status AS status
    FROM yandex_dw.fact_orders AS o
    WHERE o.status IN ('Доставлен', 'Опоздание')
)
SELECT 
    weather,
    tariff,
    time_window,
    count(order_id) AS orders_cnt,
    round(avg(surge_multiplier), 2) AS avg_surge_multiplier,
    round(avg(total_delivery_cost), 2) AS avg_client_delivery_cost_byn,
    round(avg(cooking_time_min), 1) AS avg_restaurant_cooking_min,
    round(avg(transit_time_min), 1) AS avg_courier_transit_min,
    round(avg(delivery_time_min), 1) AS avg_total_delivery_min,
    countIf(status = 'Опоздание') AS late_orders_cnt,
    round(countIf(status = 'Опоздание') * 100.0 / count(*), 2) AS late_rate_pct
FROM surge_weather_sla
GROUP BY weather, tariff, time_window
ORDER BY weather, tariff, time_window DESC;


-- ---------------------------------------------------------------------
-- ВОПРОС 3: Аналитика выработки смен курьеров в Яндекс Про
-- «Какова средняя производительность курьеров за смену (заказов в час),
--  средний часовой заработок курьера, средние чаевые и структура бонусов
--  в разрезе видов транспорта и грейдов курьеров (Топ, Опытный, Новичок),
--  а также рейтинг доходности грейдов через оконную функцию RANK()?»
-- Особенности ClickHouse: rank() OVER ()
-- ---------------------------------------------------------------------
WITH shift_analytics AS (
    SELECT 
        c.vehicle_type AS vehicle_type,
        c.courier_tier AS courier_tier,
        count(s.shift_id) AS total_shifts_cnt,
        round(sum(s.hours_online), 1) AS total_hours_online,
        sum(s.orders_completed) AS total_orders_completed,
        round(avg(s.orders_completed / s.hours_online), 2) AS avg_orders_per_hour,
        round(avg(s.total_payout / s.hours_online), 2) AS avg_hourly_payout_byn,
        round(avg(s.bonus_earnings), 2) AS avg_shift_bonus_byn,
        round(avg(s.tips_total), 2) AS avg_shift_tips_byn,
        round(avg(s.total_payout), 2) AS avg_shift_total_payout_byn
    FROM yandex_dw.fact_courier_shifts AS s
    JOIN yandex_dw.dim_couriers AS c ON s.courier_id = c.courier_id
    GROUP BY c.vehicle_type, c.courier_tier
)
SELECT 
    vehicle_type,
    courier_tier,
    total_shifts_cnt,
    avg_orders_per_hour,
    avg_hourly_payout_byn,
    avg_shift_bonus_byn,
    avg_shift_tips_byn,
    avg_shift_total_payout_byn,
    rank() OVER (ORDER BY avg_hourly_payout_byn DESC) AS payout_rank
FROM shift_analytics
ORDER BY payout_rank;
