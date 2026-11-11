-- =====================================================================
-- Виджет 1 (Metabase KPI Card): Главная метрика платформы (Net GMV)
-- Задание: З10 (Дашборд Metabase)
-- СУБД: ClickHouse (источник данных Metabase)
-- Визуализация: Number / KPI Scorecard (сравнение с планом/предыдущим периодом)
-- =====================================================================

SELECT
    count(o.order_id)                   AS delivered_orders_cnt,
    sum(o.total_amount)                 AS net_gmv_byn,
    sum(o.platform_commission)          AS yandex_take_rate_byn,
    sum(o.courier_payout)               AS courier_payout_byn,
    round(avg(o.surge_multiplier), 2)   AS avg_surge_multiplier
FROM yandex_dw.fact_orders AS o
LEFT JOIN yandex_dw.dim_districts AS d ON o.district_id = d.district_id
WHERE o.status IN ('Доставлен', 'Опоздание')
  -- Глобальные фильтры дашборда Metabase:
  [[AND d.district_name = {{district}}]]
  [[AND toDate(o.order_date) >= {{date_from}}]]
  [[AND toDate(o.order_date) <= {{date_to}}]];
