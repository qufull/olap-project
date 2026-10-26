#!/usr/bin/env python3
"""Генератор расширенного учебного датасета «Доставка еды» (Constellation Schema) -> data/raw/*.csv.

Таблицы фактов:
    * fact_orders (заказы на уровне чека)
    * fact_order_items (товарные позиции заказов / детализация блюд)
    * fact_reviews (оценки и отзывы клиентов)

Справочники (измерения):
    * dim_users (пользователи/клиенты)
    * dim_restaurants (рестораны)
    * dim_menu_items (меню ресторанов)
    * dim_couriers (курьеры)
    * dim_districts (районы города)
"""
import argparse
from pathlib import Path
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ Справочные списки
MALE = ("Александр Алексей Андрей Антон Артём Владимир Виктор Глеб Григорий Даниил Денис "
        "Дмитрий Евгений Егор Иван Игорь Илья Кирилл Константин Максим Михаил Никита Николай "
        "Олег Павел Роман Руслан Сергей Станислав Тимофей Фёдор Юрий Ярослав Владислав Вадим Артур").split()
FEMALE = ("Александра Алёна Алина Анастасия Анна Валерия Вера Виктория Дарья Евгения Екатерина "
          "Елена Ирина Ксения Лариса Людмила Марина Мария Милана Надежда Наталья Ольга Полина "
          "София Светлана Татьяна Юлия Кристина Диана").split()
PATR = [("Александрович", "Александровна"), ("Алексеевич", "Алексеевна"),
        ("Андреевич", "Андреевна"), ("Викторович", "Викторовна"),
        ("Владимирович", "Владимировна"), ("Дмитриевич", "Дмитриевна"),
        ("Евгеньевич", "Евгеньевна"), ("Иванович", "Ивановна"), ("Игоревич", "Игоревна"),
        ("Максимович", "Максимовна"), ("Михайлович", "Михайловна"),
        ("Николаевич", "Николаевна"), ("Олегович", "Олеговна"), ("Павлович", "Павловна"),
        ("Петрович", "Петровна"), ("Сергеевич", "Сергеевна"), ("Юрьевич", "Юрьевна")]
SURNAMES = ("Иванов Петров Сидоров Смирнов Кузнецов Попов Соколов Лебедев Козлов Новиков Морозов "
            "Волков Зайцев Павлов Семёнов Богданов Воробьёв Фёдоров Михайлов Беляев Тарасов "
            "Белов Комаров Орлов Киселёв Макаров Андреев Ковалёв Ильин Гусев Титов Кузьмин "
            "Кудрявцев Баранов Куликов Алексеев Степанов Яковлев Сорокин Сергеев Романов "
            "Захаров Борисов Королёв Герасимов Пономарёв Григорьев Лазарев Медведев Ершов "
            "Никитин Соболев Рябов Поляков Цветков Данилов Жуков Фролов Журавлёв Николаев "
            "Крылов Максимов Сидоренко Шевченко Мельник Лукашевич Ковалевский Климович "
            "Новицкий Островский Котов Рогов").split()

DISTRICTS_DATA = [
    (1, "Центральный", "Центральная", 1.0),
    (2, "Советский", "Центральная", 1.0),
    (3, "Первомайский", "Спальная", 1.1),
    (4, "Партизанский", "Промышленная", 1.2),
    (5, "Заводской", "Промышленная", 1.2),
    (6, "Ленинский", "Спальная", 1.1),
    (7, "Октябрьский", "Спальная", 1.1),
    (8, "Московский", "Спальная", 1.1),
    (9, "Фрунзенский", "Спальная", 1.1),
    (10, "Каменная Горка", "Спальная", 1.2),
    (11, "Уручье", "Спальная", 1.2),
    (12, "Новая Боровая", "Пригород", 1.3),
]

CUISINES = {
    "Русская": {
        "weight": 22, "avg_check": 75, "kinds": ["Трактир", "Столовая", "Кафе"],
        "names": ["Самовар", "Хлебосольный двор", "Теремок", "Старая Москва", "Борщ и компания"],
        "items": [
            ("Борщ по-домашнему со сметаной", "Супы", 12.50, 350, False, False),
            ("Пельмени ручной лепки со сливочным маслом", "Горячее", 18.00, 300, False, False),
            ("Котлета по-киевски с пюре", "Горячее", 22.00, 380, False, False),
            ("Блины со слабосолёной сёмгой", "Закуски", 19.50, 220, False, False),
            ("Сельдь под шубой классическая", "Салаты", 11.00, 200, False, False),
            ("Морс клюквенный домашний", "Напитки", 5.50, 500, False, True),
            ("Медовик со сметанным кремом", "Десерты", 9.00, 150, False, True),
            ("Солянка сборная мясная", "Супы", 15.00, 350, False, False),
            ("Драники со сметаной и шкварками", "Горячее", 16.50, 320, False, False),
            ("Сырники из фермерского творога", "Десерты", 12.00, 220, False, True),
        ]
    },
    "Пицца": {
        "weight": 21, "avg_check": 78, "kinds": ["Пиццерия", "Пицца"],
        "names": ["Номер Один", "Дон Карлоне", "Маргарита", "Печь и дрова", "Неаполь"],
        "items": [
            ("Пицца Маргарита 35см", "Пицца", 21.00, 520, False, True),
            ("Пицца Пепперони острая 35см", "Пицца", 26.50, 560, True, False),
            ("Пицца Четыре сыра с мёдом 35см", "Пицца", 28.00, 510, False, True),
            ("Пицца Мясное барбекю 35см", "Пицца", 31.00, 620, False, False),
            ("Пицца Карбонара со сливками 35см", "Пицца", 27.00, 540, False, False),
            ("Сырные палочки с чесночным соусом", "Закуски", 12.00, 240, False, True),
            ("Куриные крылышки BBQ", "Закуски", 16.00, 300, True, False),
            ("Салат Цезарь с цыплёнком", "Салаты", 17.50, 250, False, False),
            ("Лимонад клубничный базилик", "Напитки", 7.00, 450, False, True),
            ("Шоколадный лава-кейк", "Десерты", 11.50, 130, False, True),
        ]
    },
    "Веганская": {
        "weight": 20, "avg_check": 70, "kinds": ["Кафе", "Бистро"],
        "names": ["Зелёный лист", "Росток", "Свежесть", "Овощной двор", "Эко Вкус"],
        "items": [
            ("Боул с хрустящим тофу, киноа и авокадо", "Салаты", 21.50, 340, False, True),
            ("Бургер Beyond Meat с бататом фри", "Горячее", 28.00, 420, False, True),
            ("Тыквенный крем-суп на кокосовом молоке", "Супы", 13.50, 320, False, True),
            ("Фалафель в пите с хумусом и тахини", "Закуски", 15.00, 290, True, True),
            ("Спринг-роллы со свежими овощами и манго", "Закуски", 14.00, 200, False, True),
            ("Паста из цукини с песто из кешью", "Горячее", 19.00, 280, False, True),
            ("Смузи Спирулина-Киви-Яблоко", "Напитки", 8.50, 400, False, True),
            ("Матча латте на овсяном молоке", "Напитки", 7.50, 350, False, True),
            ("Чизкейк сыроедческий малиновый", "Десерты", 13.00, 140, False, True),
            ("Овощное карри с диким рисом", "Горячее", 18.50, 350, True, True),
        ]
    },
    "Суши": {
        "weight": 19, "avg_check": 105, "kinds": ["Суши-бар", "Суши"],
        "names": ["Токио", "Сакура", "Нори", "Васаби", "Самурай"],
        "items": [
            ("Ролл Филадельфия Люкс с лососем", "Суши", 27.50, 280, False, False),
            ("Ролл Калифорния со снежным крабом", "Суши", 22.00, 260, False, False),
            ("Ролл Дракон с угрём и унаги соусом", "Суши", 32.00, 290, False, False),
            ("Сет Филадельфия Фреш (32 шт)", "Суши", 79.00, 950, False, False),
            ("Запечённый ролл с креветкой спайси", "Суши", 24.50, 270, True, False),
            ("Суп Мисо с тофу и водорослями вакаме", "Супы", 9.50, 300, False, True),
            ("Салат Чука с ореховым соусом", "Салаты", 13.00, 180, False, True),
            ("Эдамаме с морской солью", "Закуски", 10.00, 160, False, True),
            ("Зелёный чай Сенча со льдом", "Напитки", 6.00, 500, False, True),
            ("Моти с манго и маракуйей (3 шт)", "Десерты", 14.00, 120, False, True),
        ]
    },
    "Итальянская": {
        "weight": 18, "avg_check": 95, "kinds": ["Траттория", "Ресторан"],
        "names": ["Бона Сера", "Рим", "Венеция", "Тоскана", "Паста Нова"],
        "items": [
            ("Паста Карбонара с панчеттой и пармезаном", "Горячее", 23.50, 320, False, False),
            ("Лазанья Болоньезе запечённая", "Горячее", 25.00, 380, False, False),
            ("Ризотто с белыми грибами и трюфельным маслом", "Горячее", 28.00, 330, False, True),
            ("Тальятелле со сливочным соусом и тигровыми креветками", "Горячее", 33.00, 350, False, False),
            ("Суп Минестроне классический", "Супы", 12.00, 320, False, True),
            ("Брускетта со страчателлой и вялеными томатами", "Закуски", 16.50, 210, False, True),
            ("Салат Капрезе с соусом песто", "Салаты", 18.00, 230, False, True),
            ("Тирамису традиционный кофейный", "Десерты", 12.50, 160, False, True),
            ("Панна-котта с лесными ягодами", "Десерты", 11.00, 150, False, True),
            ("Сан-Пеллегрино Аранчата", "Напитки", 7.50, 330, False, True),
        ]
    },
    "Азиатская": {
        "weight": 18, "avg_check": 80, "kinds": ["Wok-бар", "Азия"],
        "names": ["Лапша Хаус", "Бангкок", "Шанхай", "Дракон", "Тайский базар"],
        "items": [
            ("Том Ям с морепродуктами и кокосовым молоком", "Супы", 26.50, 420, True, False),
            ("Wok удон с цыплёнком в соусе терияки", "Горячее", 19.50, 360, False, False),
            ("Пад Тай с креветками и арахисом", "Горячее", 24.00, 380, True, False),
            ("Рамен тонкоцу со свиной грудинкой", "Супы", 22.50, 550, False, False),
            ("Хрустящие спринг-роллы со сладким чили", "Закуски", 13.50, 200, True, True),
            ("Курица Гунбао с острым перцем и рисом", "Горячее", 21.00, 370, True, False),
            ("Битые огурцы с кунжутным маслом и чесноком", "Салаты", 10.50, 180, True, True),
            ("Гёдза с креветками на пару (6 шт)", "Закуски", 16.00, 190, False, False),
            ("Манго шейк со льдом", "Напитки", 9.00, 450, False, True),
            ("Бананы в хрустящей карамели", "Десерты", 11.00, 180, False, True),
        ]
    },
    "Грузинская": {
        "weight": 17, "avg_check": 100, "kinds": ["Хинкальная", "Ресторан"],
        "names": ["Тбилиси", "Кавказ", "Генацвале", "Чурчхела", "Сулугуни"],
        "items": [
            ("Хинкали с говядиной и свининой (5 шт)", "Горячее", 17.50, 400, True, False),
            ("Хинкали с сыром сулугуни и тархуном (5 шт)", "Горячее", 18.50, 390, False, True),
            ("Хачапури по-аджарски с сыром и яйцом", "Выпечка", 21.00, 450, False, True),
            ("Хачапури по-мегрельски слоёный", "Выпечка", 23.00, 500, False, True),
            ("Шашлык из свиной шейки на углях", "Горячее", 29.00, 320, False, False),
            ("Оджахури с телятиной и картофелем на кеци", "Горячее", 26.50, 380, False, False),
            ("Суп Харчо острый с говядиной и орехами", "Супы", 16.00, 350, True, False),
            ("Рулетики из баклажанов с ореховой начинкой", "Закуски", 17.00, 220, False, True),
            ("Лимонад Натахтари Тархун", "Напитки", 6.50, 500, False, True),
            ("Чурчхела грецкий орех в виноградном соке", "Десерты", 9.50, 120, False, True),
        ]
    },
    "Бургеры": {
        "weight": 15, "avg_check": 65, "kinds": ["Бургерная", "Гриль"],
        "names": ["Биг Тейсти", "Мясной Двор", "Бургер Лаб", "Котлета", "Гриль Хаус"],
        "items": [
            ("Бургер Классический Чизбургер Блэк Ангус", "Бургеры", 19.50, 340, False, False),
            ("Бургер Двойной бекон и копчёный чеддер", "Бургеры", 25.50, 420, False, False),
            ("Бургер Хрустящий Цыплёнок с халапеньо", "Бургеры", 18.00, 320, True, False),
            ("Картофель фри хрустящий с розмарином", "Закуски", 7.50, 180, False, True),
            ("Луковые кольца в пивном кляре с соусом ранч", "Закуски", 10.50, 210, False, True),
            ("Картофельные дольки по-деревенски", "Закуски", 8.50, 200, False, True),
            ("Наггетсы куриные из филе (8 шт)", "Закуски", 12.00, 200, False, False),
            ("Молочный коктейль Сливочный пломбир", "Напитки", 8.00, 400, False, True),
            ("Крафтовая Кола zero", "Напитки", 5.50, 500, False, True),
            ("Горячий вишнёвый пирожок", "Десерты", 7.00, 110, False, True),
        ]
    },
}

PLACES = ["центр", "север", "юг", "восток", "запад", "парк", "площадь", "рынок", "проспект", "набережная"]
VEHICLES = {"Электросамокат": (0.29, 36), "Велосипед": (0.27, 42), "Пешком": (0.24, 50), "Автомобиль": (0.20, 32)}
STATUS_P = {"Доставлен": 0.85, "Отменен": 0.10, "Опоздание": 0.05}
HOUR_W = np.array([2, 5, 9, 8, 4, 3, 4, 7, 10, 10, 7, 4, 2, 1], float)

def fem(surname: str) -> str:
    for end, f in (("ский", "ская"), ("цкий", "цкая"), ("ов", "ова"), ("ев", "ева"),
                   ("ёв", "ёва"), ("ин", "ина")):
        if surname.endswith(end):
            return surname[: -len(end)] + f
    return surname

def make_fio(rng, n):
    female = rng.random(n) < 0.5
    sn = rng.choice(SURNAMES, n)
    pt = rng.integers(0, len(PATR), n)
    out = [f"{fem(sn[i]) if female[i] else sn[i]} {rng.choice(FEMALE if female[i] else MALE)} {PATR[pt[i]][1 if female[i] else 0]}"
           for i in range(n)]
    return out

def make_phones(rng, n):
    seen = set()
    out = []
    codes = np.array(["29", "33", "44", "25"])
    cp = [0.40, 0.25, 0.25, 0.10]
    while len(out) < n:
        chunk = min(n - len(out) + 1000, 50000)
        c = rng.choice(codes, chunk, p=cp)
        nums = rng.integers(1_000_000, 10_000_000, chunk)
        for code, num in zip(c, nums):
            s = str(num)
            p = f"+375 ({code}) {s[:3]}-{s[3:5]}-{s[5:]}"
            if p not in seen:
                seen.add(p)
                out.append(p)
                if len(out) >= n:
                    break
    return out

def generate_all(n_users, n_rest, n_cour, n_orders, start, end, seed):
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    span = (days[-1] - pd.Timestamp(start)).days + 1

    print("[1/5] Генерация справочников (районы, рестораны, меню, курьеры, пользователи)...")
    # 1. Районы
    districts = pd.DataFrame(DISTRICTS_DATA, columns=["district_id", "district_name", "zone_type", "delivery_multiplier"])
    n_dist = len(districts)

    # 2. Рестораны
    cuis = list(CUISINES)
    w = np.array([CUISINES[c]["weight"] for c in cuis], float)
    r_cuisine = rng.choice(cuis, n_rest, p=w / w.sum())
    r_name = []
    for c in r_cuisine:
        kinds = CUISINES[c]["kinds"]
        names = CUISINES[c]["names"]
        r_name.append(f"{rng.choice(kinds)} «{rng.choice(names)}»")
    used = set()
    for i, nm in enumerate(r_name):
        cand, k = nm, 0
        while cand in used:
            k += 1
            place = PLACES[(k - 1) % len(PLACES)]
            cand = f"{nm}, {place}" + (f" №{k // len(PLACES) + 1}" if k > len(PLACES) else "")
        used.add(cand)
        r_name[i] = cand
    r_rating = np.clip(rng.normal(4.1, 0.45, n_rest), 3.0, 5.0).round(1)
    r_dist = rng.integers(1, n_dist + 1, n_rest)
    rests = pd.DataFrame({
        "restaurant_id": np.arange(1, n_rest + 1),
        "name": r_name,
        "cuisine": r_cuisine,
        "district_id": r_dist,
        "rating": r_rating
    })

    # 3. Меню ресторанов (dim_menu_items)
    menu_items_list = []
    item_id_counter = 1
    # Словарь быстрых индексов: rest_id -> [список item_id и их цен]
    rest_menu_map = {}
    for r_idx in range(n_rest):
        r_id = r_idx + 1
        c_name = r_cuisine[r_idx]
        items_template = CUISINES[c_name]["items"]
        cur_items = []
        for (i_name, cat, price, weight, spicy, veg) in items_template:
            # Небольшая вариация цены (+/- 10%)
            var_price = round(price * rng.uniform(0.9, 1.1), 2)
            menu_items_list.append((item_id_counter, r_id, i_name, cat, var_price, weight, spicy, veg))
            cur_items.append((item_id_counter, var_price))
            item_id_counter += 1
        rest_menu_map[r_id] = cur_items

    menu_df = pd.DataFrame(menu_items_list, columns=[
        "item_id", "restaurant_id", "name", "category", "price", "weight_grams", "is_spicy", "is_vegetarian"
    ])

    # 4. Курьеры
    veh = rng.choice(list(VEHICLES), n_cour, p=[v[0] for v in VEHICLES.values()])
    couriers = pd.DataFrame({
        "courier_id": np.arange(1, n_cour + 1),
        "name": make_fio(rng, n_cour),
        "phone": make_phones(rng, n_cour),
        "vehicle_type": veh
    })

    # 5. Пользователи
    before = rng.random(n_users) < 0.75
    off = np.where(before, -rng.integers(1, 366, n_users), rng.integers(0, span, n_users))
    reg = pd.Timestamp(start) + pd.to_timedelta(off, "D")
    u_dist = rng.integers(1, n_dist + 1, n_users)
    users = pd.DataFrame({
        "user_id": np.arange(1, n_users + 1),
        "name": make_fio(rng, n_users),
        "phone": make_phones(rng, n_users),
        "registration_date": reg.strftime("%Y-%m-%d"),
        "district_id": u_dist
    })

    print(f"[2/5] Генерация {n_orders:,} заказов (fact_orders)...")
    reg_day_u = np.clip((reg - days[0]).days.to_numpy(), 0, len(days) - 1)
    uw = rng.lognormal(0, 0.7, n_users) * (len(days) - reg_day_u) / len(days)
    user_idx = rng.choice(n_users, n_orders, p=uw / uw.sum())

    rw = r_rating ** 3 * rng.lognormal(0, 0.5, n_rest)
    rest_idx = rng.choice(n_rest, n_orders, p=rw / rw.sum())
    cour_idx = rng.integers(0, n_cour, n_orders)

    dw = np.where(days.dayofweek >= 4, 1.35, 1.0) * np.linspace(0.95, 1.15, len(days))
    day_idx = rng.choice(len(days), n_orders, p=dw / dw.sum())
    reg_day = reg_day_u[user_idx]
    for _ in range(30):
        bad = day_idx < reg_day
        if not bad.any():
            break
        day_idx[bad] = rng.choice(len(days), bad.sum(), p=dw / dw.sum())
    day_idx = np.maximum(day_idx, reg_day)

    hour = rng.choice(np.arange(10, 24), n_orders, p=HOUR_W / HOUR_W.sum())
    order_dt = (days[day_idx] + pd.to_timedelta(hour, "h") + pd.to_timedelta(rng.integers(0, 3600, n_orders), "s"))
    order_sort = np.argsort(order_dt, kind="stable")
    user_idx, rest_idx, cour_idx, order_dt = user_idx[order_sort], rest_idx[order_sort], cour_idx[order_sort], order_dt[order_sort]

    status = rng.choice(list(STATUS_P), n_orders, p=list(STATUS_P.values()))
    base_t = np.array([VEHICLES[v][1] for v in veh])[cour_idx]
    t_ok = np.clip(base_t + rng.normal(0, 9, n_orders), 15, 60)
    t_late = np.clip(base_t + 30 + rng.normal(0, 12, n_orders), 61, 120)
    t = pd.array(np.where(status == "Опоздание", t_late, t_ok).round(), dtype="Int64")
    t[status == "Отменен"] = pd.NA

    # Район доставки заказа (по умолчанию район пользователя в 80% случаев, иначе случайный)
    order_dist = np.where(rng.random(n_orders) < 0.80, u_dist[user_idx], rng.integers(1, n_dist + 1, n_orders))
    delivery_fee = np.round(rng.choice([3.50, 4.00, 5.00, 6.00], n_orders, p=[0.4, 0.3, 0.2, 0.1]), 2)

    print(f"[3/5] Генерация товарных позиций в чеках (fact_order_items)...")
    # Количество позиций в заказе от 1 до 5
    items_cnt = rng.choice([1, 2, 3, 4, 5], n_orders, p=[0.15, 0.35, 0.30, 0.15, 0.05])
    total_items = np.sum(items_cnt)

    item_order_ids = np.repeat(np.arange(1, n_orders + 1), items_cnt)
    item_rest_ids = np.repeat(rest_idx + 1, items_cnt)

    # Выбираем случайное блюдо из меню конкретного ресторана (у каждого по 10 блюд: offset 0..9)
    dish_offset = rng.integers(0, 10, total_items)
    # item_id = (rest_id - 1) * 10 + dish_offset + 1
    chosen_item_ids = (item_rest_ids - 1) * 10 + dish_offset + 1
    quantities = rng.choice([1, 2, 3], total_items, p=[0.80, 0.16, 0.04])

    # Получаем цены блюд
    item_prices = menu_df.set_index("item_id")["price"].to_numpy()
    chosen_prices = item_prices[chosen_item_ids - 1]

    # Скидка на позицию (в 10% случаев небольшая скидка 1-3 BYN)
    has_disc = rng.random(total_items) < 0.10
    discounts = np.where(has_disc, np.round(rng.uniform(1.0, 3.5, total_items), 2), 0.0)
    subtotals = np.round(np.maximum(quantities * chosen_prices - discounts, 1.0), 2)

    order_items_df = pd.DataFrame({
        "order_item_id": np.arange(1, total_items + 1),
        "order_id": item_order_ids,
        "item_id": chosen_item_ids,
        "quantity": quantities,
        "unit_price": chosen_prices,
        "item_discount": discounts,
        "subtotal_amount": subtotals
    })

    # Считаем total_amount заказа строго как сумма блюд + стоимость доставки
    order_subtotals = np.bincount(item_order_ids, weights=subtotals)[1:]
    order_total = np.round(order_subtotals + delivery_fee, 2)

    orders_df = pd.DataFrame({
        "order_id": np.arange(1, n_orders + 1),
        "user_id": users["user_id"].to_numpy()[user_idx],
        "restaurant_id": rests["restaurant_id"].to_numpy()[rest_idx],
        "courier_id": couriers["courier_id"].to_numpy()[cour_idx],
        "district_id": order_dist,
        "order_date": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_fee": delivery_fee,
        "total_amount": order_total,
        "delivery_time_minutes": t,
        "status": status
    })

    print(f"[4/5] Генерация отзывов клиентов (fact_reviews)...")
    # Отзывы оставляют только по доставленным заказам (Доставлен или Опоздание)
    deliv_mask = (status == "Доставлен") | (status == "Опоздание")
    deliv_indices = np.where(deliv_mask)[0]
    # Примерно 65% клиентов оставляют отзыв
    review_mask = rng.random(len(deliv_indices)) < 0.65
    chosen_review_orders = deliv_indices[review_mask]
    n_reviews = len(chosen_review_orders)

    # Оценка еды зависит от рейтинга ресторана
    rev_rest_ratings = r_rating[rest_idx[chosen_review_orders]]
    food_r = np.clip(np.round(rng.normal(rev_rest_ratings, 0.6)), 1, 5).astype(int)

    # Оценка доставки: если опоздание - оценка ниже
    is_late = (status[chosen_review_orders] == "Опоздание")
    deliv_r = np.where(
        is_late,
        rng.choice([1, 2, 3], n_reviews, p=[0.45, 0.40, 0.15]),
        rng.choice([3, 4, 5], n_reviews, p=[0.10, 0.35, 0.55])
    )
    has_comment = rng.random(n_reviews) < 0.25
    review_dt = (order_dt[chosen_review_orders] + pd.to_timedelta(rng.integers(1800, 86400, n_reviews), "s"))

    reviews_df = pd.DataFrame({
        "review_id": np.arange(1, n_reviews + 1),
        "order_id": chosen_review_orders + 1,
        "user_id": users["user_id"].to_numpy()[user_idx[chosen_review_orders]],
        "restaurant_id": rests["restaurant_id"].to_numpy()[rest_idx[chosen_review_orders]],
        "courier_id": couriers["courier_id"].to_numpy()[cour_idx[chosen_review_orders]],
        "review_date": review_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "food_rating": food_r,
        "delivery_rating": deliv_r,
        "has_comment": has_comment
    })

    print("[5/5] Проверки ссылочной целостности...")
    assert order_items_df["order_id"].isin(orders_df["order_id"]).all()
    assert order_items_df["item_id"].isin(menu_df["item_id"]).all()
    assert reviews_df["order_id"].isin(orders_df["order_id"]).all()
    assert reviews_df["user_id"].isin(users["user_id"]).all()
    assert orders_df["user_id"].isin(users["user_id"]).all()
    assert orders_df["restaurant_id"].isin(rests["restaurant_id"]).all()
    assert orders_df["courier_id"].isin(couriers["courier_id"]).all()
    assert orders_df["district_id"].isin(districts["district_id"]).all()
    print("Целостность проверена: 0 ошибок!")

    return districts, users, rests, menu_df, couriers, orders_df, order_items_df, reviews_df

def main():
    default_out = Path(__file__).resolve().parent.parent / "data" / "raw"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", type=int, default=100000, help="число пользователей (100 000)")
    ap.add_argument("--restaurants", type=int, default=250, help="число ресторанов (250)")
    ap.add_argument("--couriers", type=int, default=800, help="число курьеров (800)")
    ap.add_argument("--orders", type=int, default=1000000, help="число заказов (1 000 000)")
    ap.add_argument("--start", default="2025-10-01", help="первый день заказов")
    ap.add_argument("--end", default="2026-09-30", help="последний день заказов")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(default_out), help="папка сохранения CSV")
    a = ap.parse_args()

    t_start = time.time()
    districts, users, rests, menu, couriers, orders, items, reviews = generate_all(
        a.users, a.restaurants, a.couriers, a.orders, a.start, a.end, a.seed
    )
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tables = [
        ("dim_districts", districts),
        ("dim_users", users),
        ("dim_restaurants", rests),
        ("dim_menu_items", menu),
        ("dim_couriers", couriers),
        ("fact_orders", orders),
        ("fact_order_items", items),
        ("fact_reviews", reviews),
    ]

    print("\n--- Запись CSV файлов в data/raw/ ---")
    for name, df in tables:
        csv_file = out / f"{name}.csv"
        df.to_csv(csv_file, index=False)
        print(f"  {name:18s} {len(df):>9,} строк -> {csv_file.name}")

    total_facts = len(orders) + len(items) + len(reviews)
    print(f"\nВСЕГО СТРОК ФАКТОВ В МОДЕЛИ: {total_facts:,} (заказы: {len(orders):,}, позиции блюд: {len(items):,}, отзывы: {len(reviews):,})")
    print(f"Время выполнения генерации: {time.time() - t_start:.2f} сек.")

if __name__ == "__main__":
    main()
