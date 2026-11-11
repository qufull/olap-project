-- =====================================================================
-- Эталон главной аналитической метрики (Net GMV) в ClickHouse
-- Задание: З08 (Запросы и ключи)
-- СУБД: ClickHouse
-- =====================================================================

SELECT
    count(order_id)   AS delivered_orders_cnt,
    sum(total_amount) AS net_gmv_byn
FROM yandex_dw.fact_orders
WHERE status IN ('Доставлен', 'Опоздание');
