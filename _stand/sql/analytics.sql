-- =====================================================================
-- Аналитические SQL-запросы к витрине (Fact Constellation Schema)
-- СУБД: DuckDB
-- =====================================================================

-- ---------------------------------------------------------------------
-- ВОПРОС 1: Топ категорий блюд, глубина продаж и структура спроса
-- «Какие категории блюд (Пицца, Суши, Бургеры и др.) приносят наибольшую выручку,
--  каков объём проданных порций, средняя цена блюда, а также доля выручки каждой
--  категории внутри каждого месяца (оконная функция)?»
-- ---------------------------------------------------------------------
WITH monthly_categories AS (
    SELECT 
        DATE_TRUNC('month', o.order_date)::DATE AS order_month,
        m.category AS item_category,
        COUNT(oi.order_item_id) AS items_sold_cnt,
        SUM(oi.quantity) AS total_portions_qty,
        ROUND(AVG(oi.unit_price), 2) AS avg_unit_price_byn,
        ROUND(SUM(oi.subtotal_amount), 2) AS category_revenue_byn
    FROM fact_order_items oi
    JOIN fact_orders o ON oi.order_id = o.order_id
    JOIN dim_menu_items m ON oi.item_id = m.item_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
    GROUP BY 1, 2
)
SELECT 
    order_month,
    item_category,
    items_sold_cnt,
    total_portions_qty,
    avg_unit_price_byn,
    category_revenue_byn,
    ROUND(category_revenue_byn * 100.0 / SUM(category_revenue_byn) OVER (PARTITION BY order_month), 2) AS month_revenue_share_pct,
    DENSE_RANK() OVER (PARTITION BY order_month ORDER BY category_revenue_byn DESC) AS rank_in_month
FROM monthly_categories
ORDER BY order_month, rank_in_month;


-- ---------------------------------------------------------------------
-- ВОПРОС 2: SLA доставки, опоздания и клиентские оценки по типам транспорта
-- «Каково среднее время доставки, процент опозданий (>60 мин) и средняя
--  оценка доставки клиентами (delivery_rating из fact_reviews) в разрезе
--  типа транспорта курьера в часы пик против обычных часов?»
-- ---------------------------------------------------------------------
WITH peak_hours_classified AS (
    SELECT 
        c.vehicle_type,
        CASE 
            WHEN EXTRACT(HOUR FROM o.order_date) IN (12, 13, 18, 19) THEN 'Час пик (12-14, 18-20)'
            ELSE 'Обычные часы'
        END AS time_period,
        o.order_id,
        o.delivery_time_minutes,
        o.status,
        r.delivery_rating
    FROM fact_orders o
    JOIN dim_couriers c ON o.courier_id = c.courier_id
    LEFT JOIN fact_reviews r ON o.order_id = r.order_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
)
SELECT 
    vehicle_type,
    time_period,
    COUNT(order_id) AS completed_orders_cnt,
    ROUND(AVG(delivery_time_minutes), 1) AS avg_delivery_minutes,
    COUNT(*) FILTER (WHERE status = 'Опоздание') AS late_orders_cnt,
    ROUND(COUNT(*) FILTER (WHERE status = 'Опоздание') * 100.0 / COUNT(*), 2) AS late_delivery_rate_pct,
    ROUND(AVG(delivery_rating), 2) AS avg_delivery_rating,
    COUNT(delivery_rating) AS reviews_cnt
FROM peak_hours_classified
GROUP BY vehicle_type, time_period
ORDER BY vehicle_type, time_period DESC;


-- ---------------------------------------------------------------------
-- ВОПРОС 3: География доставки, средний чек и рейтинг еды по районам города
-- «Каковы объём чистой выручки (Net GMV), средний чек заказа, средняя стоимость
--  доставки и средняя оценка качества блюд (food_rating) в разрезе районов Минска
--  и типов зон (Центральная, Спальная, Промышленная, Пригород)?»
-- ---------------------------------------------------------------------
WITH district_orders AS (
    SELECT 
        d.district_name,
        d.zone_type,
        COUNT(DISTINCT o.order_id) AS orders_cnt,
        SUM(o.total_amount) AS net_gmv_byn,
        ROUND(AVG(o.total_amount), 2) AS avg_order_value_byn,
        ROUND(AVG(o.delivery_fee), 2) AS avg_delivery_fee_byn,
        ROUND(AVG(rev.food_rating), 2) AS avg_food_rating,
        COUNT(rev.review_id) AS reviews_received_cnt
    FROM fact_orders o
    JOIN dim_districts d ON o.district_id = d.district_id
    LEFT JOIN fact_reviews rev ON o.order_id = rev.order_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
    GROUP BY d.district_name, d.zone_type
)
SELECT 
    district_name,
    zone_type,
    orders_cnt,
    net_gmv_byn,
    avg_order_value_byn,
    avg_delivery_fee_byn,
    avg_food_rating,
    reviews_received_cnt,
    ROUND(net_gmv_byn * 100.0 / SUM(net_gmv_byn) OVER (), 2) AS city_gmv_share_pct,
    RANK() OVER (ORDER BY net_gmv_byn DESC) AS district_revenue_rank
FROM district_orders
ORDER BY net_gmv_byn DESC;
