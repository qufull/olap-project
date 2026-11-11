-- =====================================================================
-- Виджет 3 (Metabase Chart): Юнит-экономика и доля маржи кухонь (Вопрос 1)
-- Задание: З10 (Дашборд Metabase)
-- СУБД: ClickHouse
-- Визуализация: Horizontal Bar Chart (столбчатая диаграмма) / Smart Table
-- Ось категорий: cuisine (тип кухни)
-- Значения: gmv_byn, yandex_take_rate_byn, margin_share_pct
-- =====================================================================

WITH monthly_cuisine AS (
    SELECT 
        r.cuisine                                                       AS cuisine,
        count(o.order_id)                                               AS orders_cnt,
        round(sum(o.total_amount), 2)                                   AS gmv_byn,
        round(sum(o.platform_commission), 2)                            AS yandex_take_rate_byn,
        round(sum(o.courier_payout), 2)                                 AS courier_payout_byn,
        round(sum(o.platform_commission + (o.delivery_fee + o.surge_fee) - o.courier_payout), 2) AS platform_net_margin_byn
    FROM yandex_dw.fact_orders AS o
    JOIN yandex_dw.dim_restaurants AS r ON o.restaurant_id = r.restaurant_id
    LEFT JOIN yandex_dw.dim_districts AS d ON o.district_id = d.district_id
    WHERE o.status IN ('Доставлен', 'Опоздание')
      [[AND d.district_name = {{district}}]]
      [[AND toDate(o.order_date) >= {{date_from}}]]
      [[AND toDate(o.order_date) <= {{date_to}}]]
    GROUP BY r.cuisine
)
SELECT 
    cuisine,
    orders_cnt,
    gmv_byn,
    yandex_take_rate_byn,
    courier_payout_byn,
    platform_net_margin_byn,
    round(platform_net_margin_byn * 100.0 / sum(platform_net_margin_byn) OVER (), 2) AS margin_share_pct,
    dense_rank() OVER (ORDER BY gmv_byn DESC) AS revenue_rank
FROM monthly_cuisine
ORDER BY revenue_rank;
