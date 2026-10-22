"""CRM поверх данных маслобойни: клиенты, задачи, статусы заказов, сводка дня, остатки.

Функции модуля — обычный синхронный слой данных: их вызывают и HTTP-ручки ниже,
и инструменты ИИ-помощника (assistant.py), поэтому HTTPException здесь не бросаем —
только CrmError/NotFound, которые ручки переводят в 400/404.
"""
import math
import re
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import mysql.connector
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from auth import get_current_user, require_admin
from Database import _add_column_if_missing, create_tables_sync, list_production_profiles
from OrderItem import OrderItem
from sql_safety import to_jsonable
from UseDatabase import UseDatabase, config

# Номера статусов в разных базах разные (справочник сеялся разными версиями кода),
# поэтому смысл статуса определяем по названию, а не по id.
STATUS_ROLE_PATTERNS = {
    'new': ('нов',),
    'done': ('заверш', 'выполн', 'выдан', 'доставлен'),
    'cancelled': ('отмен',),
    'awaiting_payment': ('ожида',),
}
STATUS_CACHE_SECONDS = 60

WEEKDAYS_SHORT = ('пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс')
DEFAULT_BUSINESS_PROFILE = (
    'Небольшое производство масел холодного отжима (маслобойня). Масла продаются бутылками '
    'разного объёма частным клиентам напрямую, через Avito и Ozon. Под заказы делают закладки '
    'семян в пресс; у каждого масла своя норма закладки и выход.'
)
# Настройки производства: их видят планировщик и ИИ-помощник. Меняются в «Управлении».
DEFAULT_SETTINGS = {
    'company_name': 'OilPress',
    'business_profile': DEFAULT_BUSINESS_PROFILE,
    'presses_count': 2,
    'press_batches_per_day': 3,
    'work_days': '1,2,3,4,5,6',
    'settle_days': 1,
}
INT_SETTINGS = {'presses_count': (1, 20), 'press_batches_per_day': (1, 24), 'settle_days': (0, 14)}

INTERACTION_KINDS = {
    'note': 'заметка',
    'call': 'звонок',
    'message': 'сообщение',
    'meeting': 'встреча',
}
CUSTOMER_FIELDS = ('name', 'surname', 'phone', 'address', 'email', 'source', 'tags', 'note')

_schema_ready = False
_status_cache: Dict[str, object] = {'at': 0.0, 'rows': None}


class CrmError(Exception):
    """Ошибка входных данных — человеку или модели нужно поправить запрос."""


class NotFound(CrmError):
    pass


def ensure_crm_schema():
    global _schema_ready
    if _schema_ready:
        return
    create_tables_sync()
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS tasks (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            title VARCHAR(255) NOT NULL,
                            details TEXT NULL,
                            due_date DATE NULL,
                            priority TINYINT NOT NULL DEFAULT 1,
                            is_done TINYINT(1) NOT NULL DEFAULT 0,
                            customer_id INT NULL,
                            order_id INT NULL,
                            assignee VARCHAR(50) NULL,
                            created_by VARCHAR(50) NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            done_at DATETIME NULL,
                            INDEX idx_tasks_open (is_done, due_date)
                            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS business_settings (
                            name VARCHAR(64) PRIMARY KEY,
                            value TEXT NOT NULL
                            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS customer_interactions (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            customer_id INT NOT NULL,
                            kind VARCHAR(20) NOT NULL DEFAULT 'note',
                            text TEXT NOT NULL,
                            author VARCHAR(50) NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_interactions_customer (customer_id)
                            )""")
        _add_column_if_missing(cursor, 'customers', 'email', 'VARCHAR(120) NULL')
        _add_column_if_missing(cursor, 'customers', 'source', 'VARCHAR(50) NULL')
        _add_column_if_missing(cursor, 'customers', 'tags', 'VARCHAR(255) NULL')
        _add_column_if_missing(cursor, 'customers', 'note', 'TEXT NULL')
        _add_created_at_column(cursor)
        # Ранние версии создали address VARCHAR(20): реальный адрес туда не влезал.
        # Только расширяем — данные не трогаются.
        _widen_varchar(cursor, 'customers', 'address', 255, "NOT NULL DEFAULT ''")
        _widen_varchar(cursor, 'customers', 'phone', 32, "NOT NULL DEFAULT ''")
        _widen_varchar(cursor, 'customers', 'surname', 100, "NOT NULL DEFAULT ''")
    _schema_ready = True


def _widen_varchar(cursor, table, column, length, tail):
    cursor.execute(
        """SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (config['database'], table, column),
    )
    row = cursor.fetchone()
    if row and row[0] is not None and int(row[0]) < length:
        cursor.execute(f"ALTER TABLE {table} MODIFY {column} VARCHAR({length}) {tail}")


def _add_created_at_column(cursor):
    """customers.created_at; у старых клиентов датой появления считаем первый заказ."""
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'customers' AND COLUMN_NAME = 'created_at'""",
        (config['database'],),
    )
    if cursor.fetchone()[0]:
        return
    cursor.execute("ALTER TABLE customers ADD COLUMN created_at DATETIME NULL")
    cursor.execute(
        """UPDATE customers c
           SET c.created_at = (SELECT MIN(o.date) FROM orders o WHERE o.customer_id = c.id)"""
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _rows(cursor) -> List[dict]:
    columns = [column[0] for column in cursor.description]
    return [{c: to_jsonable(v) for c, v in zip(columns, row)} for row in cursor.fetchall()]


def parse_date(value, field='дата') -> Optional[date]:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        raise CrmError(f'{field}: ожидается дата в формате ГГГГ-ММ-ДД, получено «{value}»')


def _clean(value, limit=None) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if limit:
        text = text[:limit]
    return text or None


def normalize_phone(phone) -> str:
    return re.sub(r'\D', '', str(phone or ''))


def _norm_name(text) -> str:
    return re.sub(r'\s+', ' ', str(text or '').strip().lower().replace('ё', 'е'))


def parse_volume(value) -> int:
    """'500', '500 мл', '0.5 л', 1 (литр) → миллилитры."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number, unit = float(value), ''
    else:
        text = str(value or '').strip().lower().replace(',', '.')
        match = re.search(r'(\d+(?:\.\d+)?)\s*(мл|ml|л|l)?', text)
        if not match:
            raise CrmError(f'Не понял объём «{value}»')
        number, unit = float(match.group(1)), match.group(2) or ''
    if unit in ('л', 'l') or (not unit and number <= 5):
        number *= 1000
    return int(round(number))


def _status_role(name) -> Optional[str]:
    lowered = _norm_name(name)
    for role, patterns in STATUS_ROLE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return role
    return None


def list_statuses() -> List[dict]:
    """Справочник статусов с ролью каждого: new / done / cancelled / awaiting_payment / None."""
    if _status_cache['rows'] is not None and time.time() - float(_status_cache['at']) < STATUS_CACHE_SECONDS:
        return [dict(row) for row in _status_cache['rows']]
    ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT COUNT(*) FROM order_statuses")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """INSERT INTO order_statuses (id, name) VALUES
                   (0, 'новый'), (1, 'получена предоплата'), (2, 'Avito доставка'), (3, 'Ozon'),
                   (4, 'завершен'), (5, 'готов к выдаче'), (6, 'отменен'), (7, 'ожидает предоплаты')"""
            )
        cursor.execute("SELECT id, name FROM order_statuses ORDER BY id")
        rows = _rows(cursor)
    for row in rows:
        row['role'] = _status_role(row['name'])
        row['is_closed'] = row['role'] in ('done', 'cancelled')
    _status_cache.update(at=time.time(), rows=rows)
    return [dict(row) for row in rows]


def status_ids(*roles) -> List[int]:
    return [row['id'] for row in list_statuses() if row['role'] in roles]


def closed_status_ids() -> List[int]:
    return status_ids('done', 'cancelled')


def default_status_id() -> int:
    new = status_ids('new')
    if new:
        return new[0]
    statuses = list_statuses()
    return statuses[0]['id'] if statuses else 0


def _in(column, ids, negate=False):
    """SQL-фрагмент «column [NOT] IN (...)» с параметрами; пустой список — без падения."""
    if not ids:
        return ('1=1' if negate else '1=0'), []
    placeholders = ', '.join(['%s'] * len(ids))
    return f"{column} {'NOT IN' if negate else 'IN'} ({placeholders})", list(ids)


# ── orders ───────────────────────────────────────────────────────────────────

_ORDER_SELECT = """
    SELECT o.id, o.customer_id, o.date, o.shipping_date, o.total_price, o.status, o.note,
           s.name AS status_name,
           c.name AS customer_name, c.surname AS customer_surname,
           c.phone AS customer_phone, c.address AS customer_address
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    LEFT JOIN order_statuses s ON s.id = o.status
"""


def _attach_items(cursor, orders: List[dict]) -> List[dict]:
    if not orders:
        return orders
    ids = [order['id'] for order in orders]
    placeholders = ', '.join(['%s'] * len(ids))
    cursor.execute(
        f"""SELECT order_id, oil_name, volume, count, price, revenue, profit
            FROM order_details WHERE order_id IN ({placeholders}) ORDER BY id""",
        tuple(ids),
    )
    by_order: Dict[int, List[dict]] = {}
    for row in _rows(cursor):
        by_order.setdefault(row.pop('order_id'), []).append(row)
    roles = {row['id']: row['role'] for row in list_statuses()}
    for order in orders:
        order['status_role'] = roles.get(order['status'])
        order['items'] = by_order.get(order['id'], [])
        order['items_text'] = ', '.join(
            f"{item['oil_name']} {item['volume']} мл × {item['count']}" for item in order['items']
        )
        order['customer_full_name'] = ' '.join(
            part for part in (order.get('customer_name'), order.get('customer_surname')) if part
        ).strip()
    return orders


def list_orders(
    status=None,
    open_only=False,
    ship_from=None,
    ship_to=None,
    customer_id=None,
    order_id=None,
    query=None,
    order_by='ship',
    limit=200,
    statuses=None,
) -> List[dict]:
    ensure_crm_schema()
    filters, params = [], []
    if order_id is not None:
        filters.append('o.id = %s')
        params.append(int(order_id))
    if status not in (None, ''):
        filters.append('o.status = %s')
        params.append(int(status))
    if statuses is not None:
        clause, clause_params = _in('o.status', [int(value) for value in statuses])
        filters.append(clause)
        params.extend(clause_params)
    if open_only:
        clause, clause_params = _in('o.status', closed_status_ids(), negate=True)
        filters.append(clause)
        params.extend(clause_params)
    if ship_from:
        filters.append('o.shipping_date >= %s')
        params.append(parse_date(ship_from))
    if ship_to:
        filters.append('o.shipping_date <= %s')
        params.append(parse_date(ship_to))
    if customer_id is not None:
        filters.append('o.customer_id = %s')
        params.append(int(customer_id))
    if query:
        like = f'%{query.strip()}%'
        clause = ["c.name LIKE %s", "c.surname LIKE %s", "CONCAT(c.name, ' ', c.surname) LIKE %s",
                  "o.note LIKE %s", "CAST(o.id AS CHAR) = %s"]
        params.extend([like, like, like, like, query.strip().lstrip('№#')])
        digits = normalize_phone(query)
        if len(digits) >= 4:
            clause.append("REGEXP_REPLACE(c.phone, '[^0-9]', '') LIKE %s")
            params.append(f'%{digits}%')
        filters.append('(' + ' OR '.join(clause) + ')')

    where = f"WHERE {' AND '.join(filters)}" if filters else ''
    ordering = ('o.shipping_date ASC, o.id ASC' if order_by == 'ship' else 'o.date DESC, o.id DESC')
    with UseDatabase(config) as cursor:
        cursor.execute(f"{_ORDER_SELECT} {where} ORDER BY {ordering} LIMIT %s", (*params, int(limit)))
        orders = _rows(cursor)
        return _attach_items(cursor, orders)


def get_order(order_id) -> dict:
    orders = list_orders(order_id=order_id)
    if not orders:
        raise NotFound(f'Заказ №{order_id} не найден')
    order = orders[0]
    order['history'] = order_history(order_id)
    return order


def order_history(order_id) -> List[dict]:
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT order_status AS status, name, datetime
               FROM statuses_list WHERE order_id = %s ORDER BY datetime, id""",
            (int(order_id),),
        )
        return _rows(cursor)


def update_order(order_id, status=None, shipping_date=None, note=None) -> dict:
    ensure_crm_schema()
    order_id = int(order_id)
    new_shipping = parse_date(shipping_date, 'дата отгрузки') if shipping_date not in (None, '') else None
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        row = cursor.fetchone()
        if row is None:
            raise NotFound(f'Заказ №{order_id} не найден')
        status_row = None
        if status not in (None, '') and int(status) != int(row[0]):
            cursor.execute("SELECT id, name FROM order_statuses WHERE id = %s", (int(status),))
            status_row = cursor.fetchone()
            if status_row is None:
                raise CrmError(f'Неизвестный статус {status}')

        sets, params = [], []
        if status_row is not None:
            sets.append('status = %s')
            params.append(status_row[0])
        if new_shipping is not None:
            sets.append('shipping_date = %s')
            params.append(new_shipping)
        if note is not None:
            sets.append('note = %s')
            params.append(_clean(note, 255))
        if sets:
            cursor.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id = %s", (*params, order_id))
        if status_row is not None:
            cursor.execute(
                "INSERT INTO statuses_list (order_id, order_status, name, datetime) VALUES (%s, %s, %s, NOW())",
                (order_id, status_row[0], status_row[1]),
            )
    return get_order(order_id)


def _price_index(cursor) -> Dict[tuple, dict]:
    cursor.execute(
        """SELECT id, oil_name, volume, price, seed_weight_kg, seed_price_per_kg
           FROM price_list WHERE price > 0 ORDER BY id"""
    )
    index: Dict[tuple, dict] = {}
    for row in _rows(cursor):
        index.setdefault((_norm_name(row['oil_name']), int(row['volume'])), row)
    return index


def match_product_name(name, known_names) -> str:
    """Точное совпадение без учёта регистра/«ё», иначе единственное частичное."""
    wanted = _norm_name(name)
    if not wanted:
        raise CrmError('Не указан товар')
    by_norm = {_norm_name(known): known for known in known_names}
    if wanted in by_norm:
        return by_norm[wanted]
    candidates = [known for norm, known in by_norm.items() if wanted in norm or norm in wanted]
    if not candidates and len(wanted) >= 4:
        stem = wanted[:4]
        candidates = [known for norm, known in by_norm.items() if any(word.startswith(stem) for word in norm.split())]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise CrmError(f'«{name}» подходит к нескольким товарам: {", ".join(sorted(candidates))}. Уточните.')
    raise CrmError(f'Товара «{name}» нет в прайс-листе')


def resolve_order_items(items) -> List[dict]:
    """Привести позиции к прайсу: точное имя, объём в мл, цена из прайса, если не задана."""
    if not items:
        raise CrmError('В заказе нет позиций')
    with UseDatabase(config) as cursor:
        index = _price_index(cursor)
    names = sorted({row['oil_name'] for row in index.values()})
    resolved = []
    for raw in items:
        oil_name = match_product_name(raw.get('oil_name') or raw.get('name'), names)
        volume = parse_volume(raw.get('volume'))
        try:
            count = int(raw.get('count') or raw.get('quantity') or 1)
        except (TypeError, ValueError):
            raise CrmError(f'Количество для «{oil_name}» должно быть числом')
        if count <= 0:
            raise CrmError(f'Количество для «{oil_name}» должно быть больше нуля')
        price_row = index.get((_norm_name(oil_name), volume))
        if raw.get('price') not in (None, ''):
            price = float(raw['price'])
        elif price_row:
            price = float(price_row['price'])
        else:
            volumes = sorted(volume_ for (norm, volume_) in index if norm == _norm_name(oil_name))
            raise CrmError(
                f'Нет цены на «{oil_name}» {volume} мл. В прайсе есть объёмы: '
                f'{", ".join(str(v) for v in volumes) or "—"} мл'
            )
        resolved.append({
            'oil_name': oil_name,
            'volume': volume,
            'count': count,
            'price': price,
            'seed_weight_kg': float(price_row['seed_weight_kg'] or 0) if price_row else 0.0,
            'seed_price_per_kg': float(price_row['seed_price_per_kg'] or 0) if price_row else 0.0,
        })
    return resolved


def find_customer_by_phone(phone) -> Optional[dict]:
    digits = normalize_phone(phone)
    if len(digits) < 6:
        return None
    with UseDatabase(config) as cursor:
        # Сравниваем по последним 10 цифрам: «8 926…» и «+7 926…» — один человек.
        cursor.execute(
            """SELECT id, name, surname, phone FROM customers
               WHERE RIGHT(REGEXP_REPLACE(phone, '[^0-9]', ''), 10) = %s
               ORDER BY id LIMIT 1""",
            (digits[-10:],),
        )
        rows = _rows(cursor)
    return rows[0] if rows else None


def create_order_record(items, customer_id=None, customer=None, shipping_date=None,
                        status=None, note=None, order_date=None) -> dict:
    """Создать заказ (и клиента, если нужно). Позиции — как из resolve_order_items."""
    ensure_crm_schema()
    customer = customer or {}
    if customer_id is None:
        existing = find_customer_by_phone(customer.get('phone')) if customer.get('phone') else None
        if existing:
            customer_id = existing['id']
        else:
            if not _clean(customer.get('name')):
                raise CrmError('Для нового клиента нужно имя')
            customer_id = create_customer(customer)['id']
    else:
        get_customer_row(customer_id)

    ship = parse_date(shipping_date, 'дата отгрузки') or date.today()
    status = int(status if status not in (None, '') else default_status_id())
    products = [OrderItem(
        oil_name=item['oil_name'],
        volume=int(item['volume']),
        count=int(item['count']),
        price=float(item['price']),
        seed_weight_kg=float(item.get('seed_weight_kg') or 0),
        seed_price_per_kg=float(item.get('seed_price_per_kg') or 0),
    ) for item in items]
    total = sum(product.total_revenue() for product in products)

    with UseDatabase(config) as cursor:
        cursor.execute("SELECT name FROM order_statuses WHERE id = %s", (status,))
        status_row = cursor.fetchone()
        if status_row is None:
            raise CrmError(f'Неизвестный статус {status}')
        cursor.execute(
            """INSERT INTO orders (customer_id, date, shipping_date, total_price, status, note)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (int(customer_id), order_date or datetime.now(), ship, total, status, _clean(note, 255)),
        )
        order_id = cursor.lastrowid
        for product in products:
            cursor.execute(
                """INSERT INTO order_details (
                        order_id, oil_name, volume, count, price,
                        seed_weight_kg, seed_price_per_kg, seed_cost, revenue, profit
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    order_id, product.oil_name, product.volume, product.count, product.price,
                    product.seed_weight_kg, product.seed_price_per_kg,
                    product.total_seed_cost(), product.total_revenue(), product.total_profit(),
                ),
            )
        cursor.execute(
            "INSERT INTO statuses_list (order_id, order_status, name, datetime) VALUES (%s, %s, %s, NOW())",
            (order_id, status, status_row[0]),
        )
    return get_order(order_id)


# ── customers ────────────────────────────────────────────────────────────────

def _decorate_customer(row: dict) -> dict:
    row['full_name'] = ' '.join(part for part in (row.get('name'), row.get('surname')) if part).strip()
    row['orders_count'] = int(row.get('orders_count') or 0)
    row['open_orders'] = int(row.get('open_orders') or 0)
    row['total_spent'] = float(row.get('total_spent') or 0)
    row['tags_list'] = [tag.strip() for tag in (row.get('tags') or '').split(',') if tag.strip()]
    return row


def _customer_select():
    """SELECT по клиентам со статистикой: сумма — без отменённых, «открытые» — не закрытые."""
    cancelled_sql, cancelled_params = _in('o.status', status_ids('cancelled'))
    closed_sql, closed_params = _in('o.status', closed_status_ids())
    sql = f"""
        SELECT c.id, c.name, c.surname, c.phone, c.address, c.email, c.source, c.tags, c.note, c.created_at,
               COUNT(o.id) AS orders_count,
               COALESCE(SUM(CASE WHEN o.id IS NOT NULL AND NOT ({cancelled_sql}) THEN o.total_price ELSE 0 END), 0)
                   AS total_spent,
               MAX(o.date) AS last_order_date,
               COALESCE(SUM(CASE WHEN o.id IS NOT NULL AND NOT ({closed_sql}) THEN 1 ELSE 0 END), 0) AS open_orders
        FROM customers c
        LEFT JOIN orders o ON o.customer_id = c.id
    """
    return sql, [*cancelled_params, *closed_params]


def list_customers(query=None, limit=300) -> List[dict]:
    ensure_crm_schema()
    customer_sql, params = _customer_select()
    where = ''
    if query and query.strip():
        like = f'%{query.strip()}%'
        clause = ["c.name LIKE %s", "c.surname LIKE %s", "CONCAT(c.name, ' ', c.surname) LIKE %s",
                  "c.email LIKE %s", "c.tags LIKE %s", "c.address LIKE %s", "c.note LIKE %s"]
        params.extend([like] * len(clause))
        digits = normalize_phone(query)
        if len(digits) >= 4:
            clause.append("REGEXP_REPLACE(c.phone, '[^0-9]', '') LIKE %s")
            params.append(f'%{digits}%')
        where = 'WHERE (' + ' OR '.join(clause) + ')'
    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""{customer_sql} {where}
                GROUP BY c.id
                ORDER BY last_order_date IS NULL, last_order_date DESC, c.id DESC
                LIMIT %s""",
            (*params, int(limit)),
        )
        return [_decorate_customer(row) for row in _rows(cursor)]


def get_customer_row(customer_id) -> dict:
    ensure_crm_schema()
    customer_sql, params = _customer_select()
    with UseDatabase(config) as cursor:
        cursor.execute(f"{customer_sql} WHERE c.id = %s GROUP BY c.id", (*params, int(customer_id)))
        rows = _rows(cursor)
    if not rows:
        raise NotFound(f'Клиент №{customer_id} не найден')
    return _decorate_customer(rows[0])


def get_customer(customer_id) -> dict:
    customer = get_customer_row(customer_id)
    customer['orders'] = list_orders(customer_id=customer_id, order_by='recent', limit=100)
    customer['interactions'] = list_interactions(customer_id)
    customer['tasks'] = list_tasks(status='all', customer_id=customer_id)
    favourite: Dict[str, int] = {}
    for order in customer['orders']:
        if order['status_role'] == 'cancelled':
            continue
        for item in order['items']:
            favourite[item['oil_name']] = favourite.get(item['oil_name'], 0) + int(item['count'])
    customer['favourite_products'] = [
        {'oil_name': name, 'count': count}
        for name, count in sorted(favourite.items(), key=lambda pair: -pair[1])[:5]
    ]
    return customer


def _customer_values(data: dict) -> dict:
    values = {}
    limits = {'name': 50, 'surname': 50, 'phone': 20, 'address': 100, 'email': 120, 'source': 50, 'tags': 255}
    for field in CUSTOMER_FIELDS:
        if field in data:
            value = data[field]
            if field == 'tags' and isinstance(value, (list, tuple)):
                value = ', '.join(str(tag).strip() for tag in value if str(tag).strip())
            values[field] = _clean(value, limits.get(field))
    return values


def create_customer(data: dict) -> dict:
    ensure_crm_schema()
    values = _customer_values(data)
    if not values.get('name'):
        raise CrmError('Нужно имя клиента')
    if values.get('phone'):
        existing = find_customer_by_phone(values['phone'])
        if existing:
            raise CrmError(f'Клиент с таким телефоном уже есть: №{existing["id"]} {existing["name"]}')
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO customers (name, surname, phone, address, email, source, tags, note, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (
                values['name'],
                values.get('surname') or '',
                values.get('phone') or '',
                values.get('address') or '',
                values.get('email'),
                values.get('source'),
                values.get('tags'),
                values.get('note'),
            ),
        )
        customer_id = cursor.lastrowid
    return get_customer_row(customer_id)


def update_customer(customer_id, data: dict) -> dict:
    get_customer_row(customer_id)
    values = _customer_values(data)
    if 'name' in values and not values['name']:
        raise CrmError('Имя клиента не может быть пустым')
    # В старой схеме эти колонки NOT NULL — пустое значение пишем пустой строкой.
    for required in ('surname', 'phone', 'address'):
        if required in values and values[required] is None:
            values[required] = ''
    if values:
        with UseDatabase(config) as cursor:
            cursor.execute(
                f"UPDATE customers SET {', '.join(f'{field} = %s' for field in values)} WHERE id = %s",
                (*values.values(), int(customer_id)),
            )
    return get_customer_row(customer_id)


def list_interactions(customer_id, limit=100) -> List[dict]:
    ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, customer_id, kind, text, author, created_at
               FROM customer_interactions WHERE customer_id = %s
               ORDER BY created_at DESC, id DESC LIMIT %s""",
            (int(customer_id), int(limit)),
        )
        rows = _rows(cursor)
    for row in rows:
        row['kind_label'] = INTERACTION_KINDS.get(row['kind'], row['kind'])
    return rows


def add_interaction(customer_id, text, kind='note', author=None) -> dict:
    get_customer_row(customer_id)
    text = _clean(text)
    if not text:
        raise CrmError('Пустая заметка')
    kind = kind if kind in INTERACTION_KINDS else 'note'
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO customer_interactions (customer_id, kind, text, author)
               VALUES (%s, %s, %s, %s)""",
            (int(customer_id), kind, text, author),
        )
        interaction_id = cursor.lastrowid
    return next(row for row in list_interactions(customer_id) if row['id'] == interaction_id)


# ── tasks ────────────────────────────────────────────────────────────────────

def list_tasks(status='open', customer_id=None, order_id=None, due_to=None, task_id=None,
               limit=300) -> List[dict]:
    ensure_crm_schema()
    filters, params = [], []
    if task_id is not None:
        filters.append('t.id = %s')
        params.append(int(task_id))
    if status == 'open':
        filters.append('t.is_done = 0')
    elif status == 'done':
        filters.append('t.is_done = 1')
    if customer_id is not None:
        filters.append('t.customer_id = %s')
        params.append(int(customer_id))
    if order_id is not None:
        filters.append('t.order_id = %s')
        params.append(int(order_id))
    if due_to:
        filters.append('t.due_date <= %s')
        params.append(parse_date(due_to))
    where = f"WHERE {' AND '.join(filters)}" if filters else ''
    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""SELECT t.id, t.title, t.details, t.due_date, t.priority, t.is_done, t.customer_id,
                       t.order_id, t.assignee, t.created_by, t.created_at, t.done_at,
                       c.name AS customer_name, c.surname AS customer_surname
                FROM tasks t
                LEFT JOIN customers c ON c.id = t.customer_id
                {where}
                ORDER BY t.is_done ASC, t.due_date IS NULL, t.due_date ASC, t.priority DESC, t.id DESC
                LIMIT %s""",
            (*params, int(limit)),
        )
        rows = _rows(cursor)
    today = date.today().isoformat()
    for row in rows:
        row['is_done'] = bool(row['is_done'])
        row['is_overdue'] = bool(not row['is_done'] and row['due_date'] and row['due_date'] < today)
    return rows


def get_task(task_id) -> dict:
    tasks = list_tasks(status='all', task_id=task_id)
    if not tasks:
        raise NotFound(f'Задача №{task_id} не найдена')
    return tasks[0]


def create_task(title, details=None, due_date=None, priority=1, customer_id=None, order_id=None,
                assignee=None, created_by=None) -> dict:
    ensure_crm_schema()
    title = _clean(title, 255)
    if not title:
        raise CrmError('У задачи должен быть заголовок')
    if customer_id not in (None, ''):
        get_customer_row(customer_id)
    if order_id not in (None, '') and not list_orders(order_id=order_id):
        raise NotFound(f'Заказ №{order_id} не найден')
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO tasks (title, details, due_date, priority, customer_id, order_id, assignee, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                title,
                _clean(details),
                parse_date(due_date, 'срок'),
                max(0, min(int(priority if priority not in (None, '') else 1), 2)),
                int(customer_id) if customer_id not in (None, '') else None,
                int(order_id) if order_id not in (None, '') else None,
                _clean(assignee, 50),
                _clean(created_by, 50),
            ),
        )
        task_id = cursor.lastrowid
    return get_task(task_id)


def update_task(task_id, data: dict) -> dict:
    get_task(task_id)
    sets, params = [], []
    if 'title' in data:
        title = _clean(data['title'], 255)
        if not title:
            raise CrmError('У задачи должен быть заголовок')
        sets.append('title = %s')
        params.append(title)
    if 'details' in data:
        sets.append('details = %s')
        params.append(_clean(data['details']))
    if 'due_date' in data:
        sets.append('due_date = %s')
        params.append(parse_date(data['due_date'], 'срок'))
    if 'priority' in data:
        sets.append('priority = %s')
        params.append(max(0, min(int(data['priority']), 2)))
    if 'assignee' in data:
        sets.append('assignee = %s')
        params.append(_clean(data['assignee'], 50))
    if 'is_done' in data:
        sets.append('is_done = %s')
        params.append(1 if data['is_done'] else 0)
        sets.append('done_at = NOW()' if data['is_done'] else 'done_at = NULL')
    if sets:
        with UseDatabase(config) as cursor:
            cursor.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s", (*params, int(task_id)))
    return get_task(task_id)


def delete_task(task_id):
    get_task(task_id)
    with UseDatabase(config) as cursor:
        cursor.execute("DELETE FROM tasks WHERE id = %s", (int(task_id),))


# ── production & stock ───────────────────────────────────────────────────────

def stock_summary() -> List[dict]:
    """Остатки готового масла: произведено партиями − отгружено (завершённые заказы).

    «В резерве» — открытые заказы, «свободно» — остаток минус резерв. Если по маслу не
    записано ни одной партии, остаток неизвестен (tracked = False), а не отрицательный.
    """
    ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT oil_name, COALESCE(SUM(output_volume_ml), 0) AS produced_ml,
                      COUNT(*) AS batches, MAX(batch_date) AS last_batch_date
               FROM production_batches GROUP BY oil_name"""
        )
        produced = {_norm_name(row['oil_name']): row for row in _rows(cursor)}
        done_sql, done_params = _in('o.status', status_ids('done'))
        open_sql, open_params = _in('o.status', closed_status_ids(), negate=True)
        cursor.execute(
            f"""SELECT d.oil_name,
                       COALESCE(SUM(CASE WHEN {done_sql} THEN d.volume * d.count ELSE 0 END), 0) AS shipped_ml,
                       COALESCE(SUM(CASE WHEN {open_sql} THEN d.volume * d.count ELSE 0 END), 0) AS reserved_ml
                FROM order_details d JOIN orders o ON o.id = d.order_id
                GROUP BY d.oil_name""",
            (*done_params, *open_params),
        )
        demand = {_norm_name(row['oil_name']): row for row in _rows(cursor)}
        cursor.execute("SELECT DISTINCT oil_name FROM price_list")
        catalog = {_norm_name(row[0]): row[0] for row in cursor.fetchall()}

    names = {}
    for source in (catalog, {k: v['oil_name'] for k, v in produced.items()},
                   {k: v['oil_name'] for k, v in demand.items()}):
        for key, display in source.items():
            names.setdefault(key, display)

    result = []
    for key in sorted(names):
        made = produced.get(key, {})
        sold = demand.get(key, {})
        produced_ml = float(made.get('produced_ml') or 0)
        shipped_ml = float(sold.get('shipped_ml') or 0)
        reserved_ml = float(sold.get('reserved_ml') or 0)
        tracked = bool(made)
        on_hand_ml = max(produced_ml - shipped_ml, 0) if tracked else None
        result.append({
            'oil_name': names[key],
            'tracked': tracked,
            'batches': int(made.get('batches') or 0),
            'last_batch_date': made.get('last_batch_date'),
            'produced_ml': produced_ml,
            'shipped_ml': shipped_ml,
            'reserved_ml': reserved_ml,
            'on_hand_ml': on_hand_ml,
            'free_ml': (on_hand_ml - reserved_ml) if tracked else None,
        })
    return result


def production_needs(days=14, today=None) -> List[dict]:
    """Сколько закладок нужно под открытые заказы с отгрузкой в ближайшие *days* дней."""
    today = today or date.today()
    horizon = today + timedelta(days=int(days))
    orders = list_orders(open_only=True, ship_to=horizon, limit=1000)
    demand: Dict[str, dict] = {}
    for order in orders:
        for item in order['items']:
            entry = demand.setdefault(_norm_name(item['oil_name']), {
                'oil_name': item['oil_name'],
                'needed_ml': 0.0,
                'orders': set(),
                'earliest_shipping': order['shipping_date'],
            })
            entry['needed_ml'] += float(item['volume']) * float(item['count'])
            entry['orders'].add(order['id'])
            if order['shipping_date'] and order['shipping_date'] < (entry['earliest_shipping'] or '9999'):
                entry['earliest_shipping'] = order['shipping_date']

    stock = {_norm_name(row['oil_name']): row for row in stock_summary()}
    profiles = {_norm_name(row['oil_name']): row for row in list_production_profiles()}
    result = []
    for key, entry in sorted(demand.items(), key=lambda pair: pair[1]['earliest_shipping'] or ''):
        stock_row = stock.get(key) or {}
        on_hand = stock_row.get('on_hand_ml') if stock_row.get('tracked') else None
        shortage = max(entry['needed_ml'] - (on_hand or 0), 0)
        profile = profiles.get(key)
        per_batch = 0.0
        if profile and float(profile.get('batch_seed_weight_kg') or 0) > 0 and float(profile.get('yield_percent') or 0) > 0:
            # Как в плане заказа: кг семян × выход % × 10 = мл масла с одной закладки.
            per_batch = float(profile['batch_seed_weight_kg']) * float(profile['yield_percent']) * 10
        result.append({
            'oil_name': entry['oil_name'],
            'needed_ml': entry['needed_ml'],
            'orders_count': len(entry['orders']),
            'order_ids': sorted(entry['orders']),
            'earliest_shipping': entry['earliest_shipping'],
            'on_hand_ml': on_hand,
            'stock_tracked': bool(stock_row.get('tracked')),
            'shortage_ml': shortage,
            'output_per_batch_ml': per_batch,
            'batches_needed': math.ceil(shortage / per_batch) if per_batch and shortage else 0,
            'seed_kg_needed': (math.ceil(shortage / per_batch) * float(profile['batch_seed_weight_kg'])
                               if per_batch and shortage else 0),
            'profile_ready': bool(per_batch),
            'daily_batch_limit': int(profile.get('daily_batch_limit') or 3) if profile else None,
        })
    return result


def production_plan_for(oil_name, volume_ml) -> dict:
    """Сколько закладок и семян нужно на заданный объём масла."""
    profiles = {row['oil_name']: row for row in list_production_profiles()}
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT DISTINCT oil_name FROM price_list")
        names = sorted({row[0] for row in cursor.fetchall()} | set(profiles))
    name = match_product_name(oil_name, names)
    volume_ml = parse_volume(volume_ml)
    profile = profiles.get(name)
    if not profile or not float(profile.get('batch_seed_weight_kg') or 0) or not float(profile.get('yield_percent') or 0):
        return {'oil_name': name, 'volume_ml': volume_ml, 'profile_ready': False,
                'hint': 'Нет профиля производства (закладка кг и выход %) — заполните в «Производстве».'}
    per_batch = float(profile['batch_seed_weight_kg']) * float(profile['yield_percent']) * 10
    batches = math.ceil(volume_ml / per_batch)
    return {
        'oil_name': name,
        'volume_ml': volume_ml,
        'profile_ready': True,
        'output_per_batch_ml': per_batch,
        'batches_needed': batches,
        'seed_kg_needed': batches * float(profile['batch_seed_weight_kg']),
        'daily_batch_limit': int(profile.get('daily_batch_limit') or 3),
        'days_needed': math.ceil(batches / max(int(profile.get('daily_batch_limit') or 3), 1)),
    }


# ── settings & press planner ─────────────────────────────────────────────────

def get_settings() -> dict:
    ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT name, value FROM business_settings")
        stored = dict(cursor.fetchall())
    settings = {**DEFAULT_SETTINGS, **{k: v for k, v in stored.items() if k in DEFAULT_SETTINGS}}
    for key, (low, high) in INT_SETTINGS.items():
        try:
            settings[key] = max(low, min(int(settings[key]), high))
        except (TypeError, ValueError):
            settings[key] = DEFAULT_SETTINGS[key]
    settings['work_days_list'] = _work_days(settings['work_days'])
    return settings


def _work_days(value) -> List[int]:
    days = sorted({int(part) for part in re.findall(r'[1-7]', str(value or ''))})
    return days or [1, 2, 3, 4, 5, 6]


def update_settings(data: dict) -> dict:
    values = {}
    for key in DEFAULT_SETTINGS:
        if key not in data:
            continue
        value = data[key]
        if key in INT_SETTINGS:
            low, high = INT_SETTINGS[key]
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise CrmError(f'{key}: нужно целое число')
            if not low <= value <= high:
                raise CrmError(f'{key}: от {low} до {high}')
        elif key == 'work_days':
            if isinstance(value, (list, tuple)):
                value = ','.join(str(day) for day in value)
            value = ','.join(str(day) for day in _work_days(value))
        else:
            value = (_clean(value) or DEFAULT_SETTINGS[key])[:4000]
        values[key] = str(value)
    if values:
        with UseDatabase(config) as cursor:
            for key, value in values.items():
                cursor.execute(
                    """INSERT INTO business_settings (name, value) VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE value = VALUES(value)""",
                    (key, value),
                )
    return get_settings()


def _production_jobs(needs, profiles, horizon) -> List[dict]:
    """Дефицит масла по срокам: заказы идут по дате отгрузки, остаток на складе покрывает
    первые, и каждая следующая порция закладок получает срок своего заказа — большой заказ
    на конец недели не тянет весь объём к самой ранней отгрузке."""
    orders = list_orders(open_only=True, ship_to=horizon, limit=1000)
    needs_by_oil = {_norm_name(need['oil_name']): need for need in needs}
    entries: Dict[str, List[tuple]] = {}
    for order in orders:
        ship = parse_date(order['shipping_date']) or horizon
        for item in order['items']:
            entries.setdefault(_norm_name(item['oil_name']), []).append(
                (ship, float(item['volume']) * float(item['count']), order['id'], item['oil_name'])
            )

    jobs = []
    for key, rows in entries.items():
        need = needs_by_oil.get(key)
        profile = profiles.get(key)
        if not need or not need['profile_ready'] or not profile:
            continue
        per_batch = float(profile['batch_seed_weight_kg']) * float(profile['yield_percent']) * 10
        covered = float(need['on_hand_ml'] or 0)
        cumulative = 0.0
        for ship, ml, order_id, oil_name in sorted(rows):
            cumulative += ml
            uncovered = cumulative - covered
            if uncovered <= 0:
                continue
            batches = math.ceil(uncovered / per_batch)
            covered += batches * per_batch
            jobs.append({
                'oil_name': need['oil_name'],
                'deadline': ship,
                'batches': batches,
                'shortage_ml': uncovered,
                'seed_kg': batches * float(profile['batch_seed_weight_kg']),
                'order_ids': [order_id],
            })
    return jobs


def production_schedule(days=14, today=None) -> dict:
    """Раскладка закладок по прессам и рабочим дням под сроки открытых заказов.

    Мощность дня = прессов × закладок на пресс; уже записанные на будущие даты партии
    занимают мощность первыми. Дефицит по каждому маслу ставится «как можно раньше»
    в порядке ближайшей отгрузки (EDF) и должен успеть за settle_days до неё; одно масло
    держим на одном прессе, чтобы не мыть пресс между сортами лишний раз.
    """
    settings = get_settings()
    today = today or date.today()
    presses = settings['presses_count']
    per_press = settings['press_batches_per_day']
    work_days = set(settings['work_days_list'])
    settle = settings['settle_days']
    horizon = today + timedelta(days=int(days))

    needs = production_needs(days=days, today=today)
    profiles = {_norm_name(row['oil_name']): row for row in list_production_profiles()}
    jobs = _production_jobs(needs, profiles, horizon)

    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT batch_date, oil_name, COUNT(*) FROM production_batches
               WHERE batch_date >= %s GROUP BY batch_date, oil_name""",
            (today,),
        )
        existing = [(row[0], row[1], int(row[2])) for row in cursor.fetchall()]

    plan_days: Dict[date, dict] = {}

    def day_entry(day: date) -> dict:
        if day not in plan_days:
            plan_days[day] = {
                'date': day,
                'is_work_day': day.isoweekday() in work_days,
                'capacity': presses * per_press if day.isoweekday() in work_days else 0,
                'oils': {},        # oil → {'planned': n, 'recorded': n}
            }
        return plan_days[day]

    for batch_day, oil_name, count in existing:
        entry = day_entry(batch_day)
        slot = entry['oils'].setdefault(oil_name, {'planned': 0, 'recorded': 0})
        slot['recorded'] += count

    def used(entry) -> int:
        return sum(slot['planned'] + slot['recorded'] for slot in entry['oils'].values())

    missing = [need['oil_name'] for need in needs if need['shortage_ml'] > 0 and not need['profile_ready']]
    warnings = [
        f"Нет нормы закладки (кг семян и выход %) для: {', '.join(missing)} — их закладки не посчитать. "
        "Заполните профили в «Управление → Аналитика»."
    ] if missing else []
    by_oil: Dict[str, dict] = {}
    for job in sorted(jobs, key=lambda item: item['deadline']):
        oil = job['oil_name']
        ready_by = job['deadline'] - timedelta(days=settle)
        oil_limit = int((profiles.get(_norm_name(oil)) or {}).get('daily_batch_limit') or presses * per_press)
        remaining = job['batches']
        scheduled: List[str] = []
        cursor_day = today
        # Ищем мощность до срока, а остаток — после (с пометкой «опоздаем»), не дальше 60 дней.
        while remaining > 0 and cursor_day <= max(horizon, ready_by) + timedelta(days=60):
            entry = day_entry(cursor_day)
            free = entry['capacity'] - used(entry)
            slot = entry['oils'].setdefault(oil, {'planned': 0, 'recorded': 0})
            free_for_oil = min(free, oil_limit - slot['planned'] - slot['recorded'])
            if free_for_oil > 0:
                take = min(free_for_oil, remaining)
                slot['planned'] += take
                remaining -= take
                scheduled.extend([cursor_day.isoformat()] * take)
            if not slot['planned'] and not slot['recorded']:
                entry['oils'].pop(oil, None)
            cursor_day += timedelta(days=1)
        finish = scheduled[-1] if scheduled else None
        orders_text = ', '.join(f'№{order_id}' for order_id in job['order_ids'])
        if job['deadline'] < today:
            warnings.append(f"{oil} для заказа {orders_text}: отгрузка была {job['deadline'].strftime('%d.%m')} — "
                            f"заказ просрочен, отжать в первую очередь")
        elif remaining > 0 or (finish and finish > ready_by.isoformat()):
            warnings.append(
                f"{oil} для заказа {orders_text}: не успеваем к {job['deadline'].strftime('%d.%m')} "
                f"(готово {'не раньше ' + parse_date(finish).strftime('%d.%m') if finish else '— нет мощности'})"
            )
        late = job['deadline'] < today or remaining > 0 or bool(finish and finish > ready_by.isoformat())
        item = by_oil.setdefault(oil, {
            'oil_name': oil, 'shortage_ml': 0.0, 'batches_needed': 0, 'seed_kg_needed': 0.0,
            'deadline': job['deadline'].isoformat(), 'scheduled_dates': [], 'finish_date': None,
            'late': False, 'order_ids': [],
        })
        item['shortage_ml'] += job['shortage_ml']
        item['batches_needed'] += job['batches']
        item['seed_kg_needed'] += job['seed_kg']
        item['scheduled_dates'] += scheduled
        item['finish_date'] = max(filter(None, [item['finish_date'], finish]), default=None)
        item['late'] = item['late'] or late
        item['order_ids'] = sorted(set(item['order_ids']) | set(job['order_ids']))
    items = list(by_oil.values())

    day_list = []
    total_capacity = total_used = 0
    last_day = max([horizon] + [day for day, entry in plan_days.items() if entry['oils']])
    cursor_day = today
    while cursor_day <= last_day:
        entry = day_entry(cursor_day)
        # Сорта по прессам: целиком на один пресс, пока помещается, — меньше перемывок.
        press_rows = [{'press': number + 1, 'capacity': per_press if entry['is_work_day'] else 0, 'used': 0,
                       'items': []} for number in range(presses)]
        for oil, slot in sorted(entry['oils'].items(), key=lambda pair: -(pair[1]['planned'] + pair[1]['recorded'])):
            for kind in ('recorded', 'planned'):
                left = slot[kind]
                while left > 0:
                    # Сначала пресс, где это масло уже идёт и есть место, иначе самый свободный.
                    press = max(press_rows, key=lambda row: (
                        row['capacity'] > row['used'] and any(i['oil_name'] == oil for i in row['items']),
                        row['capacity'] - row['used'],
                    ))
                    room = press['capacity'] - press['used']
                    if room <= 0:
                        press = press_rows[0]  # перегруз дня (записанных партий больше мощности)
                        room = left
                    take = min(room, left)
                    press['items'].append({'oil_name': oil, 'batches': take, 'kind': kind})
                    press['used'] += take
                    left -= take
        day_used = used(entry)
        if cursor_day <= horizon:
            total_capacity += entry['capacity']
            total_used += day_used
        day_list.append({
            'date': cursor_day.isoformat(),
            'weekday': WEEKDAYS_SHORT[cursor_day.weekday()],
            'is_work_day': entry['is_work_day'],
            'capacity': entry['capacity'],
            'used': day_used,
            'presses': press_rows,
        })
        cursor_day += timedelta(days=1)

    return {
        'settings': {key: settings[key] for key in ('presses_count', 'press_batches_per_day', 'work_days_list',
                                                     'settle_days')},
        'days': day_list,
        'items': items,
        'warnings': warnings,
        'load_percent': round(total_used / total_capacity * 100) if total_capacity else 0,
        'seed_purchase': [
            {'oil_name': item['oil_name'], 'seed_kg': item['seed_kg_needed']}
            for item in items if item['seed_kg_needed']
        ],
    }


# ── dashboard ────────────────────────────────────────────────────────────────

def dashboard(today=None) -> dict:
    ensure_crm_schema()
    today = today or date.today()
    month_start = today.replace(day=1)
    not_cancelled_sql, not_cancelled_params = _in('o.status', status_ids('cancelled'), negate=True)
    open_sql, open_params = _in('status', closed_status_ids(), negate=True)
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT COUNT(*) FROM customers")
        customers_total = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM customers WHERE created_at >= %s", (month_start,))
        customers_new = int(cursor.fetchone()[0])
        cursor.execute(
            f"SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM orders WHERE {open_sql}", tuple(open_params)
        )
        open_count, open_sum = cursor.fetchone()
        # Выручка месяца — по ценам позиций без отменённых заказов (у старых строк
        # колонка revenue пустая, поэтому price × count, а не revenue).
        cursor.execute(
            f"""SELECT COUNT(DISTINCT o.id), COALESCE(SUM(d.price * d.count), 0), COALESCE(SUM(d.seed_cost), 0)
                FROM orders o JOIN order_details d ON d.order_id = o.id
                WHERE o.date >= %s AND o.date <= %s AND {not_cancelled_sql}""",
            (month_start, today, *not_cancelled_params),
        )
        month_orders, month_revenue, month_seed_cost = cursor.fetchone()
        cursor.execute(
            """SELECT COALESCE(SUM(goods_total + delivery_cost + carsharing_cost), 0)
               FROM expense_entries WHERE expense_date >= %s AND expense_date <= %s""",
            (month_start, today),
        )
        month_expenses = float(cursor.fetchone()[0] or 0)

    revenue = float(month_revenue or 0)
    gross_profit = revenue - float(month_seed_cost or 0)
    return {
        'today': today.isoformat(),
        'month': {
            'from': month_start.isoformat(),
            'orders_count': int(month_orders or 0),
            'revenue': revenue,
            'gross_profit': gross_profit,
            'expenses': month_expenses,
            'net_profit': gross_profit - month_expenses,
            'customers_new': customers_new,
        },
        'customers_total': customers_total,
        'open_orders': {'count': int(open_count or 0), 'sum': float(open_sum or 0)},
        'ship_today': list_orders(open_only=True, ship_from=today, ship_to=today),
        'overdue': list_orders(open_only=True, ship_to=today - timedelta(days=1)),
        'upcoming': list_orders(open_only=True, ship_from=today + timedelta(days=1),
                                ship_to=today + timedelta(days=7)),
        'awaiting_payment': list_orders(statuses=status_ids('awaiting_payment')),
        'new_orders': list_orders(statuses=status_ids('new'), order_by='recent', limit=20),
        'tasks_due': list_tasks(status='open', due_to=today),
        'tasks_open_count': len(list_tasks(status='open')),
        'production_needs': production_needs(days=14, today=today),
        'stock': stock_summary(),
    }


# ── HTTP ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix='/api/crm')


def _http(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
    except (CrmError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error))
    except mysql.connector.errors.DataError as error:
        raise HTTPException(status_code=400, detail=f'Значение не подходит для базы: {error.msg}')


@router.get('/dashboard')
def api_dashboard(user: dict = Depends(get_current_user)):
    return _http(dashboard)


@router.get('/statuses')
def api_statuses(user: dict = Depends(get_current_user)):
    return list_statuses()


@router.get('/orders')
def api_orders(
    status: Optional[int] = None,
    open_only: bool = False,
    ship_from: Optional[str] = None,
    ship_to: Optional[str] = None,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    return _http(list_orders, status=status, open_only=open_only, ship_from=ship_from, ship_to=ship_to,
                 query=q, order_by='recent', limit=500)


@router.get('/orders/{order_id}')
def api_order(order_id: int, user: dict = Depends(get_current_user)):
    return _http(get_order, order_id)


@router.patch('/orders/{order_id}')
def api_update_order(order_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(update_order, order_id, status=payload.get('status'),
                 shipping_date=payload.get('shipping_date'), note=payload.get('note'))


@router.get('/customers')
def api_customers(q: Optional[str] = None, user: dict = Depends(get_current_user)):
    return _http(list_customers, q)


@router.post('/customers')
def api_create_customer(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(create_customer, payload)


@router.get('/customers/{customer_id}')
def api_customer(customer_id: int, user: dict = Depends(get_current_user)):
    return _http(get_customer, customer_id)


@router.patch('/customers/{customer_id}')
def api_update_customer(customer_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(update_customer, customer_id, payload)


@router.post('/customers/{customer_id}/interactions')
def api_add_interaction(customer_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(add_interaction, customer_id, payload.get('text'), payload.get('kind') or 'note',
                 user['username'])


@router.get('/tasks')
def api_tasks(
    status: str = Query('open', pattern='^(open|done|all)$'),
    customer_id: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    return _http(list_tasks, status=status, customer_id=customer_id)


@router.post('/tasks')
def api_create_task(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(
        create_task,
        payload.get('title'),
        details=payload.get('details'),
        due_date=payload.get('due_date'),
        priority=payload.get('priority', 1),
        customer_id=payload.get('customer_id'),
        order_id=payload.get('order_id'),
        assignee=payload.get('assignee'),
        created_by=user['username'],
    )


@router.patch('/tasks/{task_id}')
def api_update_task(task_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    return _http(update_task, task_id, payload)


@router.delete('/tasks/{task_id}')
def api_delete_task(task_id: int, user: dict = Depends(get_current_user)):
    _http(delete_task, task_id)
    return {'success': True}


@router.post('/orders')
def api_create_order(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    def create():
        customer_id = payload.get('customer_id')
        return create_order_record(
            resolve_order_items(payload.get('items') or []),
            customer_id=int(customer_id) if customer_id not in (None, '') else None,
            customer=payload.get('customer') if isinstance(payload.get('customer'), dict) else None,
            shipping_date=payload.get('shipping_date'),
            status=payload.get('status'),
            note=payload.get('note'),
        )
    return _http(create)


@router.get('/settings')
def api_settings(user: dict = Depends(get_current_user)):
    return _http(get_settings)


@router.patch('/settings')
def api_update_settings(payload: dict = Body(...), admin: dict = Depends(require_admin)):
    return _http(update_settings, payload)


@router.get('/production-schedule')
def api_production_schedule(days: int = Query(14, ge=1, le=60), user: dict = Depends(get_current_user)):
    return _http(production_schedule, days=days)


@router.get('/stock')
def api_stock(user: dict = Depends(get_current_user)):
    return _http(stock_summary)


@router.get('/production-needs')
def api_production_needs(days: int = Query(14, ge=1, le=90), user: dict = Depends(get_current_user)):
    return _http(production_needs, days=days)
