-- =====================================================================
-- З06. Реализация SCD2 (Slowly Changing Dimension Type 2)
-- Таблица: dim_couriers_scd2 (История смены транспорта курьеров)
-- =====================================================================

-- 1. Создание таблицы с версионированием
DROP TABLE IF EXISTS dim_couriers_scd2;

CREATE TABLE dim_couriers_scd2 (
    courier_sk      BIGINT PRIMARY KEY,       -- Суррогатный ключ конкретной версии
    courier_id      BIGINT NOT NULL,          -- Бизнес-ключ курьера
    name            VARCHAR NOT NULL,
    phone           VARCHAR NOT NULL,
    vehicle_type    VARCHAR NOT NULL,         -- Версионируемый атрибут
    valid_from      TIMESTAMP NOT NULL,       -- Дата/время начала действия версии
    valid_to        TIMESTAMP,                -- Дата/время окончания (NULL = текущая)
    is_current      BOOLEAN NOT NULL          -- Флаг актуальной версии
);

-- 2. Начальное наполнение данными из dim_couriers (первичные версии с 2025-10-01)
INSERT INTO dim_couriers_scd2
SELECT 
    courier_id AS courier_sk,
    courier_id,
    name,
    phone,
    vehicle_type,
    TIMESTAMP '2025-10-01 00:00:00' AS valid_from,
    CAST(NULL AS TIMESTAMP) AS valid_to,
    TRUE AS is_current
FROM dim_couriers;

-- 3. Демонстрация сценария смены атрибута (курьер courier_id = 42)
-- Допустим, курьер #42 изначально был пешим ('Пешком').
UPDATE dim_couriers_scd2
SET vehicle_type = 'Пешком'
WHERE courier_id = 42;

-- Событие 1: 2026-03-01 курьер пересаживается на 'Электросамокат'.
-- Закрываем первую версию:
UPDATE dim_couriers_scd2
SET valid_to = TIMESTAMP '2026-03-01 00:00:00',
    is_current = FALSE
WHERE courier_id = 42 AND is_current = TRUE;

-- Вставляем вторую версию:
INSERT INTO dim_couriers_scd2 VALUES (
    (SELECT COALESCE(MAX(courier_sk), 0) + 1 FROM dim_couriers_scd2),
    42,
    (SELECT name FROM dim_couriers WHERE courier_id = 42),
    (SELECT phone FROM dim_couriers WHERE courier_id = 42),
    'Электросамокат',
    TIMESTAMP '2026-03-01 00:00:00',
    TIMESTAMP '2026-07-01 00:00:00',
    FALSE
);

-- Событие 2: 2026-07-01 курьер покупает 'Автомобиль'.
-- Вставляем третью (актуальную) версию:
INSERT INTO dim_couriers_scd2 VALUES (
    (SELECT COALESCE(MAX(courier_sk), 0) + 1 FROM dim_couriers_scd2),
    42,
    (SELECT name FROM dim_couriers WHERE courier_id = 42),
    (SELECT phone FROM dim_couriers WHERE courier_id = 42),
    'Автомобиль',
    TIMESTAMP '2026-07-01 00:00:00',
    NULL,
    TRUE
);

-- ---------------------------------------------------------------------
-- ПРОВЕРКА 1: Демонстрация всех версий одной сущности (курьер 42)
-- ---------------------------------------------------------------------
SELECT 
    courier_sk,
    courier_id,
    name,
    vehicle_type,
    valid_from,
    valid_to,
    is_current
FROM dim_couriers_scd2
WHERE courier_id = 42
ORDER BY valid_from;

-- ---------------------------------------------------------------------
-- ПРОВЕРКА 2: Привязка заказов факта fact_orders к правильной версии SCD2 на дату события
-- ---------------------------------------------------------------------
SELECT 
    o.order_id,
    o.order_date,
    scd.courier_id,
    scd.name AS courier_name,
    scd.vehicle_type AS historical_vehicle_type,
    scd.valid_from,
    scd.valid_to,
    o.delivery_time_minutes,
    o.status
FROM fact_orders o
JOIN dim_couriers_scd2 scd 
  ON o.courier_id = scd.courier_id
 AND o.order_date >= scd.valid_from
 AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
WHERE o.courier_id = 42
ORDER BY o.order_date
LIMIT 15;

-- ---------------------------------------------------------------------
-- ПРОВЕРКА 3: Доказательство ценности SCD2 против искажения при SCD1
-- При SCD1 (затирание) все заказы за год считались бы выполненными на автомобиле!
-- При SCD2 видно распределение заказов по реальному транспорту на момент доставки:
-- ---------------------------------------------------------------------
SELECT 
    scd.vehicle_type,
    COUNT(o.order_id) AS orders_count,
    ROUND(AVG(o.delivery_time_minutes), 1) AS avg_delivery_minutes,
    COUNT(*) FILTER (WHERE o.status = 'Опоздание') AS late_orders_cnt,
    MIN(o.order_date) AS first_order_date,
    MAX(o.order_date) AS last_order_date
FROM fact_orders o
JOIN dim_couriers_scd2 scd 
  ON o.courier_id = scd.courier_id
 AND o.order_date >= scd.valid_from
 AND (o.order_date < scd.valid_to OR scd.valid_to IS NULL)
WHERE o.courier_id = 42 AND o.status IN ('Доставлен', 'Опоздание')
GROUP BY scd.vehicle_type
ORDER BY MIN(o.order_date);
