"""Демо-данные для показа CRM (портфолио, скриншоты): вымышленные клиенты, заказы, партии.

Работает только с ПУСТОЙ базой заказов — на рабочей базе откажется, чтобы не смешать
выдуманное с настоящим. Запуск (база из docker-compose проекта):

    DB_PORT=3307 DB_NAME=oil_demo python scripts/seed_demo.py --yes

Для демо-входа на сайте запускать не нужно: демо-база OIL_DEMO_DB пересоздаётся сама.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import crm  # noqa: E402
import demo_data  # noqa: E402
from UseDatabase import UseDatabase, config  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true', help='подтвердить запись демо-данных')
    parser.add_argument('--customers', type=int, default=28)
    args = parser.parse_args()
    if not args.yes:
        parser.error('добавьте --yes: скрипт пишет в базу')

    auth.ensure_auth_schema()
    crm.ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute('SELECT COUNT(*) FROM orders')
        if cursor.fetchone()[0]:
            sys.exit('В базе уже есть заказы — демо-данные пишутся только в пустую базу.')
    result = demo_data.seed(args.customers)
    print(f"Готово: {result['customers']} клиентов, {result['orders']} заказов, {result['batches']} партий, "
          'расходы, задачи.')


if __name__ == '__main__':
    main()
