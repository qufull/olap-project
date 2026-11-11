-- =====================================================================
-- Виджет 4 (Metabase Chart): Dynamic Surge и SLA по погоде и часам пик (Вопрос 2)
-- Задание: З10 (Дашборд Metabase)
-- СУБД: ClickHouse
-- Визуализация: Grouped Bar Chart / Matrix Heatmap
-- Категории: weather (Ясно, Дождь, Снегопад) × time_window (Час пик vs Обычные часы)
-- Метрики: avg_surge_multiplier, avg_total_delivery_min, late_rate_pct
-- =====================================================================

SELECT 
    o.weather                                           AS weather,
    CASE 
        WHEN toHour(o.order_date) IN (12, 13, 18, 19, 20) THEN 'Час пик (12-14, 18-21)'
        ELSE 'Обычные часы'
    END                                                 AS time_window,
    count(o.order_id)                                   AS orders_cnt,
    round(avg(o.surge_multiplier), 2)                   AS avg_surge_multiplier,
    round(avg(o.delivery_fee + o.surge_fee), 2)         AS avg_delivery_cost_byn,
    round(avg(o.delivery_time_min), 1)                  AS avg_delivery_min,
    countIf(o.status = 'Опоздание')                     AS late_orders_cnt,
    round(countIf(o.status = 'Опоздание') * 100.0 / count(*), 2) AS late_rate_pct
FROM yandex_dw.fact_orders AS o
LEFT JOIN yandex_dw.dim_districts AS d ON o.district_id = d.district_id
WHERE o.status IN ('Доставлен', 'Опоздание')
  [[AND d.district_name = {{district}}]]
  [[AND toDate(o.order_date) >= {{date_from}}]]
  [[AND toDate(o.order_date) <= {{date_to}}]]
GROUP BY weather, time_window
ORDER BY weather, time_window DESC;
