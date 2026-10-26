#!/usr/bin/env python3
"""Генератор учебного датасета «Доставка еды» -> data/raw/*.csv.

Запуск из корня проекта:
    python scripts/generate_data.py
    python scripts/generate_data.py --orders 100000 --users 8000 --seed 1

Зависимости: numpy, pandas. Результат детерминирован при одинаковых параметрах.

Таблицы:
    dim_users(user_id, name, phone, registration_date)
    dim_restaurants(restaurant_id, name, cuisine, rating)
    dim_couriers(courier_id, name, vehicle_type)
    fact_orders(order_id, user_id, restaurant_id, courier_id, order_date,
                total_amount, delivery_time_minutes, status)

Заложенные закономерности (чтобы на данных были осмысленные ответы):
    * сумма заказа зависит от кухни (суши и грузинская дороже, бургеры дешевле);
    * время доставки зависит от транспорта курьера (авто быстрее, пешком медленнее);
    * статус «Опоздание» = доставка дольше 60 минут, у «Отменен» времени доставки нет (NULL);
    * заказы идут пиками в обед и вечером, в выходные чаще, пользователи активны неравномерно;
    * заказ никогда не раньше даты регистрации пользователя.
"""
import argparse
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ справочники
MALE = ("Александр Алексей Андрей Антон Артём Владимир Виктор Глеб Григорий Даниил Денис "
        "Дмитрий Евгений Егор Иван Игорь Илья Кирилл Константин Максим Михаил Никита Николай "
        "Олег Павел Роман Руслан Сергей Станислав Тимофей Фёдор Юрий Ярослав").split()
FEMALE = ("Александра Алёна Алина Анастасия Анна Валерия Вера Виктория Дарья Евгения Екатерина "
          "Елена Ирина Ксения Лариса Людмила Марина Мария Милана Надежда Наталья Ольга Полина "
          "София Светлана Татьяна Юлия").split()
# отчества: (мужское, женское)
PATR = [("Александрович", "Александровна"), ("Алексеевич", "Алексеевна"),
        ("Андреевич", "Андреевна"), ("Викторович", "Викторовна"),
        ("Владимирович", "Владимировна"), ("Дмитриевич", "Дмитриевна"),
        ("Евгеньевич", "Евгеньевна"), ("Иванович", "Ивановна"), ("Игоревич", "Игоревна"),
        ("Максимович", "Максимовна"), ("Михайлович", "Михайловна"),
        ("Николаевич", "Николаевна"), ("Олегович", "Олеговна"), ("Павлович", "Павловна"),
        ("Петрович", "Петровна"), ("Сергеевич", "Сергеевна"), ("Юрьевич", "Юрьевна")]
# мужские фамилии; женская форма строится по окончанию
SURNAMES = ("Иванов Петров Сидоров Смирнов Кузнецов Попов Соколов Лебедев Козлов Новиков Морозов "
            "Волков Зайцев Павлов Семёнов Богданов Воробьёв Фёдоров Михайлов Беляев Тарасов "
            "Белов Комаров Орлов Киселёв Макаров Андреев Ковалёв Ильин Гусев Титов Кузьмин "
            "Кудрявцев Баранов Куликов Алексеев Степанов Яковлев Сорокин Сергеев Романов "
            "Захаров Борисов Королёв Герасимов Пономарёв Григорьев Лазарев Медведев Ершов "
            "Никитин Соболев Рябов Поляков Цветков Данилов Жуков Фролов Журавлёв Николаев "
            "Крылов Максимов Сидоренко Шевченко Мельник Лукашевич Ковалевский Климович "
            "Новицкий Островский Котов Рогов").split()

CUISINES = {  # кухня: (вес, средний чек, [типы заведений], [названия])
    "Русская":     (22, 75,  ["Трактир", "Столовая", "Кафе"], ["Самовар", "Хлебосольный двор", "Теремок", "Старая Москва", "Борщ и компания"]),
    "Пицца":       (21, 78,  ["Пиццерия", "Пицца"], ["Номер Один", "Дон Карлоне", "Маргарита", "Печь и дрова", "Неаполь"]),
    "Веганская":   (20, 70,  ["Кафе", "Бистро"], ["Зелёный лист", "Росток", "Свежесть", "Овощной двор", "Эко Вкус"]),
    "Суши":        (19, 105, ["Суши-бар", "Суши"], ["Токио", "Сакура", "Нори", "Васаби", "Самурай"]),
    "Итальянская": (18, 95,  ["Траттория", "Ресторан"], ["Бона Сера", "Рим", "Венеция", "Тоскана", "Паста Нова"]),
    "Азиатская":   (18, 80,  ["Wok-бар", "Азия"], ["Лапша Хаус", "Бангкок", "Шанхай", "Дракон", "Тайский базар"]),
    "Грузинская":  (17, 100, ["Хинкальная", "Ресторан"], ["Тбилиси", "Кавказ", "Генацвале", "Чурчхела", "Сулугуни"]),
    "Бургеры":     (15, 65,  ["Бургерная", "Гриль"], ["Биг Тейсти", "Мясной Двор", "Бургер Лаб", "Котлета", "Гриль Хаус"]),
}
PLACES = ["центр", "север", "юг", "восток", "запад", "парк", "площадь", "рынок"]
VEHICLES = {"Электросамокат": (0.29, 36), "Велосипед": (0.27, 42), "Пешком": (0.24, 50), "Автомобиль": (0.20, 32)}
STATUS_P = {"Доставлен": 0.85, "Отменен": 0.10, "Опоздание": 0.05}
HOUR_W = np.array([2, 5, 9, 8, 4, 3, 4, 7, 10, 10, 7, 4, 2, 1], float)  # часы 10..23


# ------------------------------------------------------------------ вспомогательное
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
    out = []
    for i in range(n):
        if female[i]:
            out.append(f"{fem(sn[i])} {rng.choice(FEMALE)} {PATR[pt[i]][1]}")
        else:
            out.append(f"{sn[i]} {rng.choice(MALE)} {PATR[pt[i]][0]}")
    return out


def make_phones(rng, n):
    """Белорусские номера +375 (XX) XXX-XX-XX, без повторов."""
    seen, out = set(), []
    while len(out) < n:
        code = rng.choice(["29", "33", "44", "25"], p=[0.40, 0.25, 0.25, 0.10])
        t = str(rng.integers(1_000_000, 10_000_000))
        p = f"+375 ({code}) {t[:3]}-{t[3:5]}-{t[5:]}"
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def generate(n_users, n_rest, n_cour, n_orders, start, end, seed):
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")

    # --- рестораны
    cuis = list(CUISINES)
    w = np.array([CUISINES[c][0] for c in cuis], float)
    r_cuisine = rng.choice(cuis, n_rest, p=w / w.sum())
    r_name = []
    for c in r_cuisine:
        _, _, kinds, names = CUISINES[c]
        r_name.append(f"{rng.choice(kinds)} «{rng.choice(names)}»")
    used = set()                                              # названия ресторанов уникальны
    for i, nm in enumerate(r_name):
        cand, k = nm, 0
        while cand in used:
            k += 1
            place = PLACES[(k - 1) % len(PLACES)]
            cand = f"{nm}, {place}" + (f" №{k // len(PLACES) + 1}" if k > len(PLACES) else "")
        used.add(cand)
        r_name[i] = cand
    rating = np.clip(rng.normal(4.0, 0.5, n_rest), 3.0, 5.0).round(1)
    rests = pd.DataFrame({"restaurant_id": np.arange(1, n_rest + 1), "name": r_name,
                          "cuisine": r_cuisine, "rating": rating})

    # --- курьеры
    veh = rng.choice(list(VEHICLES), n_cour, p=[v[0] for v in VEHICLES.values()])
    couriers = pd.DataFrame({"courier_id": np.arange(1, n_cour + 1),
                             "name": make_fio(rng, n_cour), "vehicle_type": veh})

    # --- пользователи: 75% зарегистрированы до старта периода, 25% — внутри него
    span = (days[-1] - pd.Timestamp(start)).days + 1
    before = rng.random(n_users) < 0.75
    off = np.where(before, -rng.integers(1, 366, n_users), rng.integers(0, span, n_users))
    reg = pd.Timestamp(start) + pd.to_timedelta(off, "D")
    users = pd.DataFrame({"user_id": np.arange(1, n_users + 1), "name": make_fio(rng, n_users),
                          "phone": make_phones(rng, n_users),
                          "registration_date": reg.strftime("%Y-%m-%d")})

    # --- заказы
    reg_day_u = np.clip((reg - days[0]).days.to_numpy(), 0, len(days) - 1)
    uw = rng.lognormal(0, 0.7, n_users) * (len(days) - reg_day_u) / len(days)  # активность × время с регистрации
    user_idx = rng.choice(n_users, n_orders, p=uw / uw.sum())
    rw = rating ** 3 * rng.lognormal(0, 0.5, n_rest)          # популярность ресторанов
    rest_idx = rng.choice(n_rest, n_orders, p=rw / rw.sum())
    cour_idx = rng.integers(0, n_cour, n_orders)

    dw = np.where(days.dayofweek >= 4, 1.35, 1.0) * np.linspace(0.95, 1.15, len(days))  # выходные + небольшой рост
    day_idx = rng.choice(len(days), n_orders, p=dw / dw.sum())
    reg_day = reg_day_u[user_idx]
    for _ in range(30):                                       # заказ не раньше регистрации
        bad = day_idx < reg_day
        if not bad.any():
            break
        day_idx[bad] = rng.choice(len(days), bad.sum(), p=dw / dw.sum())
    day_idx = np.maximum(day_idx, reg_day)
    hour = rng.choice(np.arange(10, 24), n_orders, p=HOUR_W / HOUR_W.sum())
    order_dt = (days[day_idx] + pd.to_timedelta(hour, "h")
                + pd.to_timedelta(rng.integers(0, 3600, n_orders), "s"))
    order = np.argsort(order_dt, kind="stable")               # order_id идёт по времени
    user_idx, rest_idx, cour_idx, order_dt = user_idx[order], rest_idx[order], cour_idx[order], order_dt[order]

    status = rng.choice(list(STATUS_P), n_orders, p=list(STATUS_P.values()))
    mean_check = np.array([CUISINES[c][1] for c in r_cuisine])[rest_idx]
    amount = np.clip(mean_check * rng.lognormal(0, 0.35, n_orders), 15, 300).round(2)
    base_t = np.array([VEHICLES[v][1] for v in veh])[cour_idx]
    t_ok = np.clip(base_t + rng.normal(0, 9, n_orders), 15, 60)
    t_late = np.clip(base_t + 30 + rng.normal(0, 12, n_orders), 61, 120)
    t = pd.array(np.where(status == "Опоздание", t_late, t_ok).round(), dtype="Int64")
    t[status == "Отменен"] = pd.NA

    orders = pd.DataFrame({"order_id": np.arange(1, n_orders + 1),
                           "user_id": users["user_id"].to_numpy()[user_idx],
                           "restaurant_id": rests["restaurant_id"].to_numpy()[rest_idx],
                           "courier_id": couriers["courier_id"].to_numpy()[cour_idx],
                           "order_date": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
                           "total_amount": amount, "delivery_time_minutes": t, "status": status})
    return users, rests, couriers, orders


def check(users, rests, couriers, orders):
    """Быстрые проверки целостности: падает, если генератор что-то сломал."""
    assert orders["user_id"].isin(users["user_id"]).all()
    assert orders["restaurant_id"].isin(rests["restaurant_id"]).all()
    assert orders["courier_id"].isin(couriers["courier_id"]).all()
    m = orders.merge(users, on="user_id")
    assert (pd.to_datetime(m["order_date"]).dt.normalize() >= pd.to_datetime(m["registration_date"])).all()
    assert orders.loc[orders.status == "Отменен", "delivery_time_minutes"].isna().all()
    assert orders.loc[orders.status != "Отменен", "delivery_time_minutes"].notna().all()
    assert users["phone"].str.fullmatch(r"\+375 \((29|33|44|25)\) \d{3}-\d{2}-\d{2}").all()


def main():
    default_out = Path(__file__).resolve().parent.parent / "data" / "raw"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", type=int, default=100000, help="число пользователей (по умолчанию 100 000)")
    ap.add_argument("--restaurants", type=int, default=250, help="число ресторанов (по умолчанию 250)")
    ap.add_argument("--couriers", type=int, default=800, help="число курьеров (по умолчанию 800)")
    ap.add_argument("--orders", type=int, default=1000000, help="число заказов / фактов (по умолчанию 1 000 000)")
    ap.add_argument("--start", default="2025-10-01", help="первый день заказов")
    ap.add_argument("--end", default="2026-09-30", help="последний день заказов")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(default_out), help="папка для сохранения CSV")
    a = ap.parse_args()

    users, rests, couriers, orders = generate(a.users, a.restaurants, a.couriers, a.orders,
                                              a.start, a.end, a.seed)
    check(users, rests, couriers, orders)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in (("dim_users", users), ("dim_restaurants", rests),
                     ("dim_couriers", couriers), ("fact_orders", orders)):
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name:16s} {len(df):>7} строк -> {out / (name + '.csv')}")
    print("статусы:", orders["status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
