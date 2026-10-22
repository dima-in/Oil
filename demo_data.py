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
from Database import add_expense_entry, add_production_batch, upsert_production_profile
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

_lock = threading.Lock()
_fresh_on: Dict[str, str] = {}


def is_demo_database(name: str) -> bool:
    """Сбрасывать можно только явно демо-базу и никогда — рабочую."""
    return bool(name) and name != config['database'] and 'demo' in name.lower()


def seed(customers_count: int = 28) -> dict:
    """Наполнить ТЕКУЩУЮ базу (active_database) демо-данными. Ждёт пустую базу заказов."""
    rng = random.Random(42)
    crm.ensure_crm_schema()
    assistant.ensure_assistant_schema()
    with UseDatabase(config) as cursor:
        cursor.execute('SELECT COUNT(*) FROM price_list')
        if not cursor.fetchone()[0]:
            for oil, variants in PRICES.items():
                for volume, price in variants:
                    cursor.execute(
                        'INSERT INTO price_list (oil_name, volume, price, seed_weight_kg, seed_price_per_kg) '
                        'VALUES (%s, %s, %s, %s, %s)',
                        (oil, volume, price, volume / 1000 / (PROFILES[oil][1] / 100), PROFILES[oil][3]),
                    )
    for oil, (kg, yield_percent, limit, _) in PROFILES.items():
        upsert_production_profile(oil, kg, yield_percent, limit, None)
    crm.update_settings({'presses_count': 2, 'press_batches_per_day': 3, 'settle_days': 1,
                         'work_days': [1, 2, 3, 4, 5, 6]})

    today = date.today()
    done = crm.status_ids('done')[0]
    cancelled = crm.status_ids('cancelled')[0]
    open_statuses = [row['id'] for row in crm.list_statuses() if row['role'] not in ('done', 'cancelled')]

    customers = []
    for index in range(customers_count):
        female = index % 3 != 2
        customers.append(crm.create_customer({
            'name': rng.choice(FIRST[:10] if female else FIRST[10:]),
            'surname': rng.choice(LAST_F if female else LAST_M),
            'phone': f'+7 900 {100 + index:03d}-{rng.randint(10, 99)}-{rng.randint(10, 99)}',
            'address': f'{rng.choice(STREETS)}, {rng.randint(1, 80)}',
            'source': rng.choice(SOURCES),
            'tags': rng.choice(['постоянный', 'опт', '', '', 'новый']),
        }))

    oils = list(PRICES)
    orders = 0
    # Прошлые заказы: три месяца истории, у постоянных клиентов — повторные покупки.
    for _ in range(90):
        customer = rng.choice(customers[: max(8, len(customers) // 2)] * 2 + customers)
        ordered = today - timedelta(days=rng.randint(3, 95))
        items = []
        for oil in rng.sample(oils, rng.randint(1, 3)):
            volume, _price = rng.choice(PRICES[oil])
            items.append({'oil_name': oil, 'volume': volume, 'count': rng.randint(1, 4)})
        crm.create_order_record(
            crm.resolve_order_items(items), customer_id=customer['id'],
            shipping_date=ordered + timedelta(days=rng.randint(1, 4)),
            status=cancelled if rng.random() < 0.06 else done,
            note=rng.choice(NOTES), order_date=datetime.combine(ordered, datetime.min.time()),
        )
        orders += 1
    # Открытые заказы на ближайшие дни — их видят «Сегодня», запись заказа и план прессов.
    for _ in range(16):
        customer = rng.choice(customers)
        items = []
        for oil in rng.sample(oils, rng.randint(1, 2)):
            volume, _price = rng.choice(PRICES[oil])
            items.append({'oil_name': oil, 'volume': volume, 'count': rng.randint(1, 6)})
        crm.create_order_record(
            crm.resolve_order_items(items), customer_id=customer['id'],
            shipping_date=today + timedelta(days=rng.randint(-1, 9)),
            status=rng.choice(open_statuses), note=rng.choice(NOTES),
        )
        orders += 1

    # Партии: отжимы прошлых недель, чтобы были остатки и себестоимость.
    for _ in range(40):
        oil = rng.choice(oils)
        kg, yield_percent, _, seed_price = PROFILES[oil]
        add_production_batch(today - timedelta(days=rng.randint(2, 90)), oil, kg, seed_price, yield_percent,
                             kg * yield_percent * 10, 300, 150, 0, None)
    for weeks_ago in range(12):
        oil = rng.choice(oils)
        kg = rng.choice([25, 50])
        add_expense_entry(today - timedelta(days=weeks_ago * 7 + 2), f'семена: {oil}', kg, PROFILES[oil][3],
                          kg * PROFILES[oil][3], rng.choice([0, 500, 800]), 0, None)
        add_expense_entry(today - timedelta(days=weeks_ago * 7 + 4), 'бутылки и крышки', 0, 0,
                          rng.choice([1800, 2400, 3100]), 0, 0, None)

    for customer in rng.sample(customers, 6):
        crm.add_interaction(customer['id'], rng.choice([
            'Спрашивала про опт от 10 бутылок — обещали скидку 10%',
            'Просил напомнить, когда будет свежий тмин',
            'Оставил отзыв на Avito, всё понравилось',
            'Хочет подарочные наборы к Новому году',
        ]), rng.choice(['call', 'message', 'note']), 'demo')
    for title, days, customer_id in (
        ('Заказать бутылки 250 мл', 0, None),
        ('Перезвонить по оптовому заказу', 1, customers[0]['id']),
        ('Выложить новое объявление на Avito', 2, None),
        ('Сверить остатки семян тыквы', -1, None),
    ):
        crm.create_task(title, due_date=today + timedelta(days=days), customer_id=customer_id,
                        priority=2 if days < 0 else 1, created_by='demo')
    return {'customers': len(customers), 'orders': orders, 'batches': 40}


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
    today = date.today().isoformat()
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
