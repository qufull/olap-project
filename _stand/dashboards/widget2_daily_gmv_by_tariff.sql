-- =====================================================================
-- Виджет 2 (Metabase Chart): Динамика выручки по тарифам (из сводки З09)
-- Задание: З10 (Дашборд Metabase)
-- СУБД: ClickHouse (таблица agg_daily_district_tariff)
-- Визуализация: Stacked Area Chart (накопительные площади) или Multi-Line Chart
-- Ось X: order_date (день)
-- Ось Y: daily_gmv_byn (выручка в BYN)
-- Группировка: tariff (Экспресс / Стандарт / Эконом)
-- =====================================================================

SELECT
    a.order_date                    AS order_date,
    a.tariff                        AS tariff,
    sum(a.net_gmv_byn)              AS daily_gmv_byn,
    sum(a.delivered_orders_cnt)     AS daily_orders_cnt,
    sum(a.platform_commission_byn)  AS daily_commission_byn
FROM yandex_dw.agg_daily_district_tariff AS a
LEFT JOIN yandex_dw.dim_districts AS d ON a.district_id = d.district_id
WHERE 1 = 1
  -- Глобальные фильтры дашборда Metabase:
  [[AND d.district_name = {{district}}]]
  [[AND a.order_date >= {{date_from}}]]
  [[AND a.order_date <= {{date_to}}]]
GROUP BY a.order_date, a.tariff
ORDER BY a.order_date, a.tariff;
