"""Демо-данные для показа CRM (портфолио, скриншоты): вымышленные клиенты, заказы, партии.

Работает только с ПУСТОЙ базой заказов — на рабочей базе откажется, чтобы не смешать
выдуманное с настоящим. Запуск (база из docker-compose проекта):

    DB_PORT=3307 python scripts/seed_demo.py --yes
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import crm  # noqa: E402
from Database import add_expense_entry, add_production_batch, upsert_production_profile  # noqa: E402
from UseDatabase import UseDatabase, config  # noqa: E402

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true', help='подтвердить запись демо-данных')
    parser.add_argument('--customers', type=int, default=28)
    args = parser.parse_args()
    if not args.yes:
        parser.error('добавьте --yes: скрипт пишет в базу')

    random.seed(42)
    auth.ensure_auth_schema()
    crm.ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute('SELECT COUNT(*) FROM orders')
        if cursor.fetchone()[0]:
            sys.exit('В базе уже есть заказы — демо-данные пишутся только в пустую базу.')
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
    for index in range(args.customers):
        female = index % 3 != 2
        customer = crm.create_customer({
            'name': random.choice(FIRST[:10] if female else FIRST[10:]),
            'surname': random.choice(LAST_F if female else LAST_M),
            'phone': f'+7 900 {100 + index:03d}-{random.randint(10, 99)}-{random.randint(10, 99)}',
            'address': f'{random.choice(STREETS)}, {random.randint(1, 80)}',
            'source': random.choice(SOURCES),
            'tags': random.choice(['постоянный', 'опт', '', '', 'новый']),
        })
        customers.append(customer)

    oils = list(PRICES)
    # Прошлые заказы: три месяца истории, у постоянных клиентов — повторные покупки.
    for _ in range(90):
        customer = random.choice(customers[: max(8, len(customers) // 2)] * 2 + customers)
        ordered = today - timedelta(days=random.randint(3, 95))
        items = []
        for oil in random.sample(oils, random.randint(1, 3)):
            volume, _price = random.choice(PRICES[oil])
            items.append({'oil_name': oil, 'volume': volume, 'count': random.randint(1, 4)})
        crm.create_order_record(
            crm.resolve_order_items(items), customer_id=customer['id'],
            shipping_date=ordered + timedelta(days=random.randint(1, 4)),
            status=cancelled if random.random() < 0.06 else done,
            note=random.choice(NOTES), order_date=datetime.combine(ordered, datetime.min.time()),
        )
    # Открытые заказы на ближайшие дни — их видят «Сегодня», запись заказа и план прессов.
    for _ in range(16):
        customer = random.choice(customers)
        items = []
        for oil in random.sample(oils, random.randint(1, 2)):
            volume, _price = random.choice(PRICES[oil])
            items.append({'oil_name': oil, 'volume': volume, 'count': random.randint(1, 6)})
        crm.create_order_record(
            crm.resolve_order_items(items), customer_id=customer['id'],
            shipping_date=today + timedelta(days=random.randint(-1, 9)),
            status=random.choice(open_statuses), note=random.choice(NOTES),
        )

    # Партии: отжимы прошлых недель, чтобы были остатки и себестоимость.
    for _ in range(40):
        oil = random.choice(oils)
        kg, yield_percent, _, seed_price = PROFILES[oil]
        add_production_batch(today - timedelta(days=random.randint(2, 90)), oil, kg, seed_price, yield_percent,
                             kg * yield_percent * 10, 300, 150, 0, None)
    for weeks_ago in range(12):
        oil = random.choice(oils)
        kg = random.choice([25, 50])
        add_expense_entry(today - timedelta(days=weeks_ago * 7 + 2), f'семена: {oil}', kg, PROFILES[oil][3],
                          kg * PROFILES[oil][3], random.choice([0, 500, 800]), 0, None)
        add_expense_entry(today - timedelta(days=weeks_ago * 7 + 4), 'бутылки и крышки', 0, 0,
                          random.choice([1800, 2400, 3100]), 0, 0, None)

    for customer in random.sample(customers, 6):
        crm.add_interaction(customer['id'], random.choice([
            'Спрашивала про опт от 10 бутылок — обещали скидку 10%',
            'Просил напомнить, когда будет свежий тмин',
            'Оставил отзыв на Avito, всё понравилось',
            'Хочет подарочные наборы к Новому году',
        ]), random.choice(['call', 'message', 'note']), 'demo')
    tasks = [
        ('Заказать бутылки 250 мл', 0, None),
        ('Перезвонить по оптовому заказу', 1, customers[0]['id']),
        ('Выложить новое объявление на Avito', 2, None),
        ('Сверить остатки семян тыквы', -1, None),
    ]
    for title, days, customer_id in tasks:
        crm.create_task(title, due_date=today + timedelta(days=days), customer_id=customer_id,
                        priority=2 if days < 0 else 1, created_by='demo')
    print(f'Готово: {len(customers)} клиентов, 106 заказов, 40 партий, расходы, задачи.')


if __name__ == '__main__':
    main()
