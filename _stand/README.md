# Учебный стенд OLAP — проект «Доставка еды» (Constellation Schema)

**ФИО:** _Минович, Спарнюк, Телеш_  
**Группа:** _ИИ-231_  
**Домен:** Сервис экспресс-доставки еды из ресторанов (заказы, позиции чеков, отзывы, меню, рестораны, курьеры, пользователи, районы города)

## Архитектура модели данных

Модель реализована в виде **Fact Constellation Schema** (Созвездие фактов):
* **3 таблицы фактов:**
  * `fact_orders` — Заказы на уровне чека (1 000 000 строк).
  * `fact_order_items` — Детализация позиций чека / блюда (2 601 720 строк).
  * `fact_reviews` — Отзывы и оценки клиентов к выполненным заказам (585 149 строк).
  * **Суммарный объём фактов в витрине:** **4 186 869 строк**.
* **5 справочников (измерений):**
  * `dim_districts` — 12 районов города с классификацией зон доставки.
  * `dim_users` — 100 000 клиентов сервиса.
  * `dim_restaurants` — 250 заведений питания по 8 типам кухонь.
  * `dim_menu_items` — 2 500 позиций блюд с категориями, ценами, весом и свойствами (острое/вегетарианское).
  * `dim_couriers` — 800 курьеров с типами транспорта (SCD2 кандидат).
  * `dim_date` — 366 календарных дней периода `2025-10-01` — `2026-09-30`.

---

## Где лежит сырьё

Папка `data/raw/` — синтетические данные (CSV с заголовком в кодировке UTF-8):

| Файл | Роль в модели | Число строк | Основные поля |
| :--- | :--- | :---: | :--- |
| `fact_orders.csv` | Таблица фактов | 1 000 000 | `order_id`, `user_id`, `restaurant_id`, `courier_id`, `district_id`, `order_date`, `delivery_fee`, `total_amount`, `delivery_time_minutes`, `status` |
| `fact_order_items.csv` | Таблица фактов | 2 601 720 | `order_item_id`, `order_id`, `item_id`, `quantity`, `unit_price`, `item_discount`, `subtotal_amount` |
| `fact_reviews.csv` | Таблица фактов | 585 149 | `review_id`, `order_id`, `user_id`, `restaurant_id`, `courier_id`, `review_date`, `food_rating`, `delivery_rating`, `has_comment` |
| `dim_districts.csv` | Измерение | 12 | `district_id`, `district_name`, `zone_type`, `delivery_multiplier` |
| `dim_users.csv` | Измерение | 100 000 | `user_id`, `name`, `phone`, `registration_date`, `district_id` |
| `dim_restaurants.csv` | Измерение | 250 | `restaurant_id`, `name`, `cuisine`, `district_id`, `rating` |
| `dim_menu_items.csv` | Измерение | 2 500 | `item_id`, `restaurant_id`, `name`, `category`, `price`, `weight_grams`, `is_spicy`, `is_vegetarian` |
| `dim_couriers.csv` | Измерение | 800 | `courier_id`, `name`, `phone`, `vehicle_type` |

---

## Инструкция по запуску

### 1. Генерация сырых данных (Data Generator)
Для повторной генерации или масштабирования объёма:
```bash
python scripts/generate_data.py --orders 1000000 --users 100000 --restaurants 250 --couriers 800
```

### 2. З03. Сборка витрины DuckDB
Создаёт DDL-схему, загружает данные и выводит контрольные проверки:
```bash
python scripts/build_duckdb.py
```

### 3. З04. Аналитический SQL
Вычисляет эталон главной метрики (`Net GMV`) и выполняет 3 сложных аналитических запроса:
```bash
python scripts/run_analytics.py
```

### 4. З05. Автоматизированный ELT-пайплайн и проверки качества
Выполняет сквозную загрузку через staging-слой, Data Quality проверки и тестирование идемпотентности:
```bash
python etl/elt_pipeline.py
```
Результаты двойного прогона фиксируются в `etl/run_log.txt`.
