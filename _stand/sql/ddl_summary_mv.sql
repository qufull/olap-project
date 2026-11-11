-- =====================================================================
-- DDL Сводной таблицы и Materialized View под график в ClickHouse
-- Задание: З09 (Сводная таблица под график)
-- СУБД: ClickHouse (схема yandex_dw)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Целевая таблица агрегатов (Summary / Aggregate Table)
-- График: «Динамика выручки (Net GMV) и заказов по дням в разрезе районов и тарифов»
-- Зерно: один день (order_date) × один район (district_id) × один тариф (tariff)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yandex_dw.agg_daily_district_tariff
(
    order_date              Date,
    district_id             Int32,
    tariff                  String,          -- Экспресс, Стандарт, Эконом
    delivered_orders_cnt    UInt32,          -- Доставлено заказов
    net_gmv_byn             Decimal(14, 2),  -- Оборот доставленных заказов (GMV)
    platform_commission_byn Decimal(12, 2),  -- Комиссия Яндекс Доставки (Take Rate)
    delivery_revenue_byn    Decimal(12, 2),  -- Плата за доставку
    surge_revenue_byn       Decimal(12, 2),  -- Надбавка за повышенный спрос
    courier_payout_byn      Decimal(12, 2)   -- Выплаты курьерам
)
ENGINE = SummingMergeTree(
    (delivered_orders_cnt, net_gmv_byn, platform_commission_byn, delivery_revenue_byn, surge_revenue_byn, courier_payout_byn)
)
PARTITION BY toYYYYMM(order_date)
ORDER BY (order_date, district_id, tariff);


-- ---------------------------------------------------------------------
-- 2. Materialized View для автоматической синхронизации при вставках в fact_orders
-- При поступлении новых пачек заказов ClickHouse на лету доагрегирует строки в таблицу
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS yandex_dw.mv_daily_district_tariff
TO yandex_dw.agg_daily_district_tariff AS
SELECT
    toDate(order_date)          AS order_date,
    district_id                 AS district_id,
    tariff                      AS tariff,
    count(order_id)             AS delivered_orders_cnt,
    sum(total_amount)           AS net_gmv_byn,
    sum(platform_commission)    AS platform_commission_byn,
    sum(delivery_fee)           AS delivery_revenue_byn,
    sum(surge_fee)              AS surge_revenue_byn,
    sum(courier_payout)         AS courier_payout_byn
FROM yandex_dw.fact_orders
WHERE status IN ('Доставлен', 'Опоздание')
GROUP BY order_date, district_id, tariff;


-- ---------------------------------------------------------------------
-- 3. SQL первичного/повторного заполнения сводки (Backfill / Rebuild)
-- Используется при пакетном перезапуске ETL-пайплайна
-- ---------------------------------------------------------------------
-- TRUNCATE TABLE IF EXISTS yandex_dw.agg_daily_district_tariff;
-- INSERT INTO yandex_dw.agg_daily_district_tariff
-- SELECT
--     toDate(order_date)          AS order_date,
--     district_id                 AS district_id,
--     tariff                      AS tariff,
--     count(order_id)             AS delivered_orders_cnt,
--     sum(total_amount)           AS net_gmv_byn,
--     sum(platform_commission)    AS platform_commission_byn,
--     sum(delivery_fee)           AS delivery_revenue_byn,
--     sum(surge_fee)              AS surge_revenue_byn,
--     sum(courier_payout)         AS courier_payout_byn
-- FROM yandex_dw.fact_orders
-- WHERE status IN ('Доставлен', 'Опоздание')
-- GROUP BY order_date, district_id, tariff;
