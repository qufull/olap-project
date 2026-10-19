


SELECT
    COUNT(order_id)   AS delivered_orders_cnt,
    SUM(total_amount) AS net_gmv_byn
FROM fact_orders
WHERE status IN ('Доставлен', 'Опоздание');