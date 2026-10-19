
WITH monthly_cuisine AS (
    SELECT
        DATE_TRUNC('month', f.order_date)::DATE AS order_month,
        r.cuisine                               AS cuisine,
        COUNT(f.order_id)                       AS orders_cnt,
        SUM(f.total_amount)                     AS net_gmv_byn,
        ROUND(SUM(f.total_amount) / COUNT(f.order_id), 2) AS avg_order_value_byn
    FROM fact_orders f
    JOIN dim_restaurants r ON f.restaurant_id = r.restaurant_id
    WHERE f.status IN ('Доставлен', 'Опоздание')
    GROUP BY 1, 2
)
SELECT
    order_month,
    cuisine,
    orders_cnt,
    net_gmv_byn,
    avg_order_value_byn,
    -- Оконная функция 1: доля кухни в выручке конкретного месяца (%)
    ROUND(net_gmv_byn * 100.0 / SUM(net_gmv_byn) OVER (PARTITION BY order_month), 2) AS month_revenue_share_pct,
    -- Оконная функция 2: место (рейтинг) кухни по выручке внутри месяца
    RANK() OVER (PARTITION BY order_month ORDER BY net_gmv_byn DESC) AS cuisine_rank_in_month
FROM monthly_cuisine
ORDER BY order_month, cuisine_rank_in_month;


-- ============================================================================
-- Вопрос 2 → Операционная эффективность транспорта (vehicle_type) и SLA доставки:
--            среднее время доставки и доля опозданий в часы пик (12:00-13:59, 18:00-19:59) 
--            против остальных часов
-- ============================================================================
SELECT
    c.vehicle_type,
    CASE 
        WHEN EXTRACT(HOUR FROM f.order_date) IN (12, 13, 18, 19) THEN 'Час пик (12-14, 18-20)'
        ELSE 'Обычные часы'
    END AS time_period,
    COUNT(f.order_id) AS completed_orders_cnt,
    ROUND(AVG(f.delivery_time_minutes), 1) AS avg_delivery_minutes,
    COUNT(*) FILTER (WHERE f.status = 'Опоздание') AS late_orders_cnt,
    ROUND(
        COUNT(*) FILTER (WHERE f.status = 'Опоздание') * 100.0 / COUNT(f.order_id),
        2
    ) AS late_delivery_rate_pct
FROM fact_orders f
JOIN dim_couriers c ON f.courier_id = c.courier_id
WHERE f.status IN ('Доставлен', 'Опоздание')
GROUP BY 1, 2
ORDER BY c.vehicle_type, time_period DESC;


-- ============================================================================
-- Вопрос 3 → Когортная активность и вклад выходных дней (Пт–Вс против Пн–Чт) 
--            + доля ранних пользователей (регистрация до 2025-10-01) против новых
-- ============================================================================
WITH cohort_stats AS (
    SELECT
        CASE 
            WHEN d.is_weekend THEN 'Выходные (Пт-Вс)'
            ELSE 'Будни (Пн-Чт)'
        END AS day_type,
        CASE 
            WHEN u.registration_date < DATE '2025-10-01' THEN '1. Ранние (до 2025-10-01)'
            ELSE '2. Новые (с 2025-10-01)'
        END AS user_cohort,
        COUNT(DISTINCT d.date_key) AS calendar_days_cnt,
        COUNT(f.order_id)          AS orders_cnt,
        SUM(f.total_amount)        AS net_gmv_byn
    FROM fact_orders f
    JOIN dim_date d  ON CAST(f.order_date AS DATE) = d.date_key
    JOIN dim_users u ON f.user_id = u.user_id
    WHERE f.status IN ('Доставлен', 'Опоздание')
    GROUP BY 1, 2
)
SELECT
    day_type,
    user_cohort,
    orders_cnt,
    ROUND(orders_cnt * 1.0 / calendar_days_cnt, 1) AS avg_orders_per_day,
    net_gmv_byn,
    ROUND(net_gmv_byn / calendar_days_cnt, 2)      AS avg_daily_gmv_byn,
    -- Оконная функция: доля сегмента в общей чистой выручке сервиса (%)
    ROUND(net_gmv_byn * 100.0 / SUM(net_gmv_byn) OVER (), 2) AS total_gmv_share_pct
FROM cohort_stats
ORDER BY day_type DESC, user_cohort;