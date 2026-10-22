"""Демо-данные: вымышленные клиенты, заказы, партии — для показа CRM (портфолио, демо-вход).

Демо-база (OIL_DEMO_DB) пересоздаётся раз в день при входе демо-пользователя: даты заказов
считаются от «сегодня», поэтому сводка, лента дней и план прессов всегда живые, а то, что
насоздавали посетители, к следующему дню исчезает.
"""
import random
import threading
from datetime import date, datetime, timedelta
from typing import Dict

import assistant
import crm
from OrderItem import OrderItem
from UseDatabase import UseDatabase, active_database, config, current_database

PRICES = {
    'льняное': [(250, 450), (500, 870), (1000, 1600)],
    'подсолнечное': [(500, 520), (1000, 950)],
    'тыквы штирийской': [(250, 1100), (500, 2070)],
    'черного тмина': [(100, 930), (250, 1900), (500, 3230)],
    'кедровое': [(100, 820), (250, 1700)],
    'конопляное': [(250, 640), (500, 1280)],
    'рыжиковое': [(500, 1160), (1000, 2100)],
    'горчичное': [(500, 900)],
    'кунжутное': [(250, 690), (500, 1250)],
    'грецкого ореха': [(100, 650), (250, 1400)],
}
# Норма закладки: кг семян, выход %, закладок в день, цена семян за кг.
PROFILES = {
    'льняное': (10, 30, 4, 120),
    'подсолнечное': (12, 33, 4, 60),
    'тыквы штирийской': (8, 28, 3, 420),
    'черного тмина': (6, 22, 2, 380),
    'кедровое': (5, 25, 2, 1300),
    'конопляное': (8, 26, 3, 260),
    'рыжиковое': (10, 28, 3, 140),
    'горчичное': (10, 25, 3, 110),
    'кунжутное': (8, 40, 3, 230),
    'грецкого ореха': (5, 45, 2, 700),
}
FIRST = ['Анна', 'Мария', 'Елена', 'Ольга', 'Наталья', 'Ирина', 'Светлана', 'Татьяна', 'Юлия', 'Ксения',
         'Алексей', 'Дмитрий', 'Сергей', 'Андрей', 'Михаил', 'Игорь', 'Павел', 'Николай']
LAST_F = ['Смирнова', 'Иванова', 'Кузнецова', 'Попова', 'Соколова', 'Лебедева', 'Козлова', 'Новикова',
          'Морозова', 'Волкова', 'Орлова', 'Белова']
LAST_M = ['Смирнов', 'Иванов', 'Кузнецов', 'Попов', 'Соколов', 'Лебедев', 'Козлов', 'Новиков', 'Морозов']
STREETS = ['ул. Ленина', 'пр. Мира', 'ул. Садовая', 'ул. Лесная', 'ул. Полевая', 'ул. Речная']
SOURCES = ['Avito', 'Avito', 'Ozon', 'сарафан', 'сарафан', 'соцсети', 'сайт']
NOTES = ['позвонить за час', 'самовывоз после 18:00', 'доставка СДЭК', 'подарочная упаковка', None, None, None]
MARKER = 'demo_seeded_on'
# Меняется вместе с составом демо-данных: после деплоя демо-база пересоздаётся, не дожидаясь утра.
SEED_VERSION = 'v3'

_lock = threading.Lock()
_fresh_on: Dict[str, str] = {}


def is_demo_database(name: str) -> bool:
    """Сбрасывать можно только явно демо-базу и никогда — рабочую."""
    return bool(name) and name != config['database'] and 'demo' in name.lower()


def seed(customers_count: int = 28) -> dict:
    """Наполнить ТЕКУЩУЮ базу (active_database) демо-данными. Ждёт пустую базу заказов.

    Всё пишется одной транзакцией через одно подключение: демо пересоздаётся при входе
    посетителя, и через crm.create_* (десяток подключений на заказ) это заняло бы минуту.
    """
    rng = random.Random(42)
    crm.ensure_crm_schema()
    assistant.ensure_assistant_schema()
    crm.update_settings({'presses_count': 2, 'press_batches_per_day': 3, 'settle_days': 1,
                         'work_days': [1, 2, 3, 4, 5, 6]})
    statuses = {row['id']: row for row in crm.list_statuses()}
    done = crm.status_ids('done')[0]
    cancelled = crm.status_ids('cancelled')[0]
    open_statuses = [status_id for status_id, row in statuses.items() if row['role'] not in ('done', 'cancelled')]
    today = date.today()
    oils = list(PRICES)
    prices = {(oil, volume): price for oil, variants in PRICES.items() for volume, price in variants}

    def seed_kg(oil, volume):
        return volume / 1000 / (PROFILES[oil][1] / 100)

    with UseDatabase(config) as cursor:
        cursor.execute('SELECT COUNT(*) FROM price_list')
        if not cursor.fetchone()[0]:
            for (oil, volume), price in prices.items():
                cursor.execute(
                    'INSERT INTO price_list (oil_name, volume, price, seed_weight_kg, seed_price_per_kg) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (oil, volume, price, seed_kg(oil, volume), PROFILES[oil][3]),
                )
        for oil, (kg, yield_percent, limit, seed_price) in PROFILES.items():
            cursor.execute(
                """INSERT INTO production_profiles (oil_name, batch_seed_weight_kg, yield_percent, daily_batch_limit,
                       seed_price_per_kg)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE batch_seed_weight_kg = VALUES(batch_seed_weight_kg),
                       yield_percent = VALUES(yield_percent), daily_batch_limit = VALUES(daily_batch_limit),
                       seed_price_per_kg = VALUES(seed_price_per_kg)""",
                (oil, kg, yield_percent, limit, seed_price),
            )

        customers = []
        for index in range(customers_count):
            female = index % 3 != 2
            name = rng.choice(FIRST[:10] if female else FIRST[10:])
            cursor.execute(
                """INSERT INTO customers (name, surname, phone, address, source, tags, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    name,
                    rng.choice(LAST_F if female else LAST_M),
                    f'+7 900 {100 + index:03d}-{rng.randint(10, 99)}-{rng.randint(10, 99)}',
                    f'{rng.choice(STREETS)}, {rng.randint(1, 80)}',
                    rng.choice(SOURCES),
                    rng.choice(['постоянный', 'опт', None, None, 'новый']),
                    today - timedelta(days=rng.randint(30, 120)),
                ),
            )
            customers.append(cursor.lastrowid)

        def add_order(customer_id, ordered, shipping, status, items):
            products = [OrderItem(oil, volume, count, prices[(oil, volume)], seed_kg(oil, volume), PROFILES[oil][3])
                        for oil, volume, count in items]
            cursor.execute(
                """INSERT INTO orders (customer_id, date, shipping_date, total_price, status, note)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (customer_id, ordered, shipping, sum(p.total_revenue() for p in products), status, rng.choice(NOTES)),
            )
            order_id = cursor.lastrowid
            for product in products:
                cursor.execute(
                    """INSERT INTO order_details (order_id, oil_name, volume, count, price, seed_weight_kg,
                                                  seed_price_per_kg, seed_cost, revenue, profit)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (order_id, product.oil_name, product.volume, product.count, product.price,
                     product.seed_weight_kg, product.seed_price_per_kg, product.total_seed_cost(),
                     product.total_revenue(), product.total_profit()),
                )
            cursor.execute(
                "INSERT INTO statuses_list (order_id, order_status, name, datetime) VALUES (%s, %s, %s, %s)",
                (order_id, status, statuses[status]['name'], datetime.combine(ordered, datetime.min.time())),
            )

        def pick_items(max_oils, max_count):
            return [(oil, rng.choice(PRICES[oil])[0], rng.randint(1, max_count))
                    for oil in rng.sample(oils, rng.randint(1, max_oils))]

        # Прошлые заказы: три месяца истории, у постоянных клиентов — повторные покупки.
        regulars = customers[: max(8, len(customers) // 2)] * 2 + customers
        for _ in range(90):
            ordered = today - timedelta(days=rng.randint(3, 95))
            add_order(rng.choice(regulars), ordered, ordered + timedelta(days=rng.randint(1, 4)),
                      cancelled if rng.random() < 0.06 else done, pick_items(3, 4))
        # Открытые заказы на ближайшие дни — их видят «Сегодня», запись заказа и план прессов.
        for _ in range(16):
            add_order(rng.choice(customers), today, today + timedelta(days=rng.randint(-1, 9)),
                      rng.choice(open_statuses), pick_items(2, 6))

        # Партии: отжимы прошлых недель, чтобы были остатки и себестоимость.
        for _ in range(40):
            oil = rng.choice(oils)
            kg, yield_percent, _, seed_price = PROFILES[oil]
            cursor.execute(
                """INSERT INTO production_batches (batch_date, oil_name, seed_weight_kg, seed_price_per_kg,
                       yield_percent, output_volume_ml, labor_cost, packaging_cost, other_cost)
                   VALUES (%s, %s, %s, %s, %s, %s, 300, 150, 0)""",
                (today - timedelta(days=rng.randint(2, 90)), oil, kg, seed_price, yield_percent, kg * yield_percent * 10),
            )
        expense_sql = """INSERT INTO expense_entries (expense_date, item_name, weight_kg, price_per_kg, goods_total,
                             delivery_cost, carsharing_cost) VALUES (%s, %s, %s, %s, %s, %s, 0)"""
        for weeks_ago in range(12):
            oil = rng.choice(oils)
            kg = rng.choice([25, 50])
            cursor.execute(expense_sql, (today - timedelta(days=weeks_ago * 7 + 2), f'семена: {oil}', kg,
                                         PROFILES[oil][3], kg * PROFILES[oil][3], rng.choice([0, 500, 800])))
            cursor.execute(expense_sql, (today - timedelta(days=weeks_ago * 7 + 4), 'бутылки и крышки', 0, 0,
                                         rng.choice([1800, 2400, 3100]), 0))

        for customer_id in rng.sample(customers, 6):
            cursor.execute(
                "INSERT INTO customer_interactions (customer_id, kind, text, author) VALUES (%s, %s, %s, 'demo')",
                (customer_id, rng.choice(['call', 'message', 'note']), rng.choice([
                    'Спрашивала про опт от 10 бутылок — обещали скидку 10%',
                    'Просил напомнить, когда будет свежий тмин',
                    'Оставил отзыв на Avito, всё понравилось',
                    'Хочет подарочные наборы к Новому году',
                ])),
            )
        for title, days, customer_id in (
            ('Заказать бутылки 250 мл', 0, None),
            ('Перезвонить по оптовому заказу', 1, customers[0]),
            ('Выложить новое объявление на Avito', 2, None),
            ('Сверить остатки семян тыквы', -1, None),
        ):
            cursor.execute(
                """INSERT INTO tasks (title, due_date, priority, customer_id, created_by)
                   VALUES (%s, %s, %s, %s, 'demo')""",
                (title, today + timedelta(days=days), 2 if days < 0 else 1, customer_id),
            )
    return {'customers': len(customers), 'orders': 106, 'batches': 40}


def reset(database: str):
    """Очистить все таблицы демо-базы. Откажется работать с любой другой базой."""
    if not is_demo_database(database) or active_database() != database:
        raise RuntimeError(f'Сброс разрешён только для демо-базы, а не «{active_database()}»')
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT TABLE_NAME FROM information_schema.TABLES
               WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'""",
            (database,),
        )
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
        for table in tables:
            cursor.execute(f'TRUNCATE TABLE `{table}`')
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
    crm._status_cache.pop(database, None)


def _seeded_on():
    with UseDatabase(config) as cursor:
        cursor.execute('SELECT value FROM business_settings WHERE name = %s', (MARKER,))
        row = cursor.fetchone()
    return row[0] if row else None


def ensure_fresh(database: str):
    """Демо-база с данными «на сегодня»: если сегодня ещё не пересоздавали — пересоздать."""
    today = f'{date.today().isoformat()}:{SEED_VERSION}'
    if _fresh_on.get(database) == today:
        return
    with _lock:
        if _fresh_on.get(database) == today:
            return
        marker = current_database.set(database)
        try:
            crm.ensure_crm_schema()
            assistant.ensure_assistant_schema()
            if _seeded_on() != today:
                reset(database)
                seed()
                with UseDatabase(config) as cursor:
                    cursor.execute(
                        """INSERT INTO business_settings (name, value) VALUES (%s, %s)
                           ON DUPLICATE KEY UPDATE value = VALUES(value)""",
                        (MARKER, today),
                    )
            _fresh_on[database] = today
        finally:
            current_database.reset(marker)
