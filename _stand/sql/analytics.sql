-- =====================================================================
-- Аналитический SQL: Модель платформы «Яндекс Доставка»
-- СУБД: DuckDB
-- =====================================================================

-- ---------------------------------------------------------------------
-- ВОПРОС 1: Юнит-экономика платформы, комиссия Яндекса (Take Rate) и маржинальность
-- «Каков объём GMV, комиссионная выручка Яндекса (platform_commission),
--  выплаты курьерам и чистая операционная прибыль платформы по типам кухонь помесячно,
--  а также доля комиссии каждой кухни в ежемесячной прибыли (SUM OVER)
--  и ранг кухни в структуре выручки месяца (DENSE_RANK)?»
-- ---------------------------------------------------------------------
WITH monthly_cuisine_economy AS (
    SELECT 
        DATE_TRUNC('month', o.order_date)::DATE AS order_month,
        r.cuisine,
        COUNT(o.order_id) AS orders_cnt,
        ROUND(SUM(o.total_amount), 2) AS gmv_byn,
        ROUND(SUM(o.platform_commission), 2) AS yandex_take_rate_byn,
        ROUND(SUM(o.delivery_fee + o.surge_fee), 2) AS delivery_revenue_byn,
        ROUND(SUM(o.courier_payout), 2) AS courier_payout_byn,
        -- Чистая прибыль платформы = комиссия с ресторана + плата за доставку и surge - выплата курьеру
        ROUND(SUM(o.platform_commission + (o.delivery_fee + o.surge_fee) - o.courier_payout), 2) AS platform_net_margin_byn
    FROM fact_orders o
    JOIN dim_restaurants r ON o.restaurant_id = r.restaurant_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
    GROUP BY 1, 2
)
SELECT 
    order_month,
    cuisine,
    orders_cnt,
    gmv_byn,
    yandex_take_rate_byn,
    courier_payout_byn,
    platform_net_margin_byn,
    ROUND(platform_net_margin_byn * 100.0 / SUM(platform_net_margin_byn) OVER (PARTITION BY order_month), 2) AS margin_share_in_month_pct,
    DENSE_RANK() OVER (PARTITION BY order_month ORDER BY gmv_byn DESC) AS cuisine_gmv_rank
FROM monthly_cuisine_economy
ORDER BY order_month, cuisine_gmv_rank;


-- ---------------------------------------------------------------------
-- ВОПРОС 2: Динамический спрос (Surge Pricing), погодные аномалии и SLA
-- «Как погодные условия (Ясно, Дождь, Снегопад) и тарифы доставки (Экспресс, Стандарт, Эконом)
--  влияют на средний коэффициент Surge, средний чек доставки, время в пути курьера
--  и процент опозданий (>60 минут) в часы пик против обычных часов?»
-- ---------------------------------------------------------------------
WITH surge_weather_sla AS (
    SELECT 
        o.weather,
        o.tariff,
        CASE 
            WHEN EXTRACT(HOUR FROM o.order_date) IN (12, 13, 18, 19, 20) THEN 'Час пик (12-14, 18-21)'
            ELSE 'Обычные часы'
        END AS time_window,
        o.order_id,
        o.surge_multiplier,
        o.delivery_fee + o.surge_fee AS total_delivery_cost,
        o.cooking_time_min,
        o.transit_time_min,
        o.delivery_time_min,
        o.status
    FROM fact_orders o
    WHERE o.status IN ('Доставлен', 'Опоздание')
)
SELECT 
    weather,
    tariff,
    time_window,
    COUNT(order_id) AS orders_cnt,
    ROUND(AVG(surge_multiplier), 2) AS avg_surge_multiplier,
    ROUND(AVG(total_delivery_cost), 2) AS avg_client_delivery_cost_byn,
    ROUND(AVG(cooking_time_min), 1) AS avg_restaurant_cooking_min,
    ROUND(AVG(transit_time_min), 1) AS avg_courier_transit_min,
    ROUND(AVG(delivery_time_min), 1) AS avg_total_delivery_min,
    COUNT(*) FILTER (WHERE status = 'Опоздание') AS late_orders_cnt,
    ROUND(COUNT(*) FILTER (WHERE status = 'Опоздание') * 100.0 / COUNT(*), 2) AS late_rate_pct
FROM surge_weather_sla
GROUP BY weather, tariff, time_window
ORDER BY weather, tariff, time_window DESC;


-- ---------------------------------------------------------------------
-- ВОПРОС 3: Аналитика выработки смен курьеров в Яндекс Про
-- «Какова средняя производительность курьеров за смену (заказов в час),
--  средний часовой заработок курьера, средние чаевые и структура бонусов
--  в разрезе видов транспорта и грейдов курьеров (Топ, Опытный, Новичок),
--  а также рейтинг доходности грейдов через оконную функцию RANK()?»
-- ---------------------------------------------------------------------
WITH shift_analytics AS (
    SELECT 
        c.vehicle_type,
        c.courier_tier,
        COUNT(s.shift_id) AS total_shifts_cnt,
        ROUND(SUM(s.hours_online), 1) AS total_hours_online,
        SUM(s.orders_completed) AS total_orders_completed,
        ROUND(AVG(s.orders_completed / s.hours_online), 2) AS avg_orders_per_hour,
        ROUND(AVG(s.total_payout / s.hours_online), 2) AS avg_hourly_payout_byn,
        ROUND(AVG(s.bonus_earnings), 2) AS avg_shift_bonus_byn,
        ROUND(AVG(s.tips_total), 2) AS avg_shift_tips_byn,
        ROUND(AVG(s.total_payout), 2) AS avg_shift_total_payout_byn
    FROM fact_courier_shifts s
    JOIN dim_couriers c ON s.courier_id = c.courier_id
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
    RANK() OVER (ORDER BY avg_hourly_payout_byn DESC) AS payout_rank
FROM shift_analytics
ORDER BY payout_rank;
