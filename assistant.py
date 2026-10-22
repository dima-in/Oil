"""ИИ-помощник CRM: агент с инструментами поверх базы.

Модель отвечает строго JSON — вызвать инструмент или дать ответ. Инструменты чтения
выполняются сразу. Изменяющие (заказ, задача, расход, партия…) не выполняются, а
сохраняются черновиком действия: человек подтверждает его кнопкой в чате. Удалять
ассистент не умеет вовсе — это остаётся за человеком в интерфейсе.

Протокол JSON, а не нативные tools: шлюз novpnai отдаёт сторонним клиентам голую
модель, и так агент работает с любым OpenAI-совместимым адресом (OIL_LLM_URL).
"""
import json
import logging
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import mysql.connector
import requests
from fastapi import APIRouter, Body, Depends, HTTPException

import crm
from auth import get_current_user
from Database import add_expense_entry, add_production_batch, list_expense_entries, list_production_profiles
from sql_safety import HIDDEN_TABLES, run_readonly_query, to_jsonable
from UseDatabase import UseDatabase, active_database, config

log = logging.getLogger('oilpress.assistant')

MAX_STEPS = 8
TURN_DEADLINE_SECONDS = 150
OBSERVATION_LIMIT = 7000
HISTORY_MESSAGES = 24
HISTORY_MESSAGE_CHARS = 6000
ACTION_TTL_HOURS = 24
WEEKDAYS = ('понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье')

DICTATION_RULES = """Текст мог быть надиктован голосом: без знаков препинания, числа словами, оговорки.
«пол-литра», «поллитровая», «0,5» = 500 мл; «литр», «литровая» = 1000 мл; «двести/двухсотка» = 200 мл;
«две бутылки» = 2; «пару» = 2. Телефон может быть сказан группами цифр — собери его целиком.
Названия масел сопоставляй с прайсом по смыслу: «лён/льняное» = «льняное», «тыквенное» = «тыквы штирийской»,
«тмин» = «черного тмина», «расторопша» = «расторопши», «кунжут» = «кунжут нешлифованный»."""


# «or», а не значение по умолчанию getenv: docker-compose передаёт незаданную переменную пустой строкой.
def llm_url() -> str:
    return os.getenv('OIL_LLM_URL') or 'https://novpnai.ru/v1/chat/completions'


def agent_model() -> str:
    return os.getenv('OIL_AGENT_MODEL') or 'google/gemini-2.5-flash'


def agent_protocol() -> str:
    """tools — нативный tool calling (OpenAI tools / tool_calls; шлюз novpnai пробрасывает их
    клиенту с gateway_tools=false); json — запасной протокол через текст {"tool": …}."""
    return 'json' if (os.getenv('OIL_AGENT_PROTOCOL') or '').strip().lower() == 'json' else 'tools'


class AssistantUnavailable(Exception):
    pass


# ── pending actions ──────────────────────────────────────────────────────────

_schema_ready: set = set()


def ensure_assistant_schema():
    database = active_database()
    if database in _schema_ready:
        return
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS assistant_actions (
                            id CHAR(32) PRIMARY KEY,
                            username VARCHAR(50) NOT NULL,
                            tool VARCHAR(50) NOT NULL,
                            args_json TEXT NOT NULL,
                            summary TEXT NOT NULL,
                            status VARCHAR(16) NOT NULL DEFAULT 'pending',
                            result_json TEXT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            resolved_at DATETIME NULL
                            )""")
    _schema_ready.add(database)


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=to_jsonable)


def save_pending_action(user: dict, tool: str, args: dict, summary: str) -> dict:
    ensure_assistant_schema()
    action_id = secrets.token_hex(16)
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO assistant_actions (id, username, tool, args_json, summary)
               VALUES (%s, %s, %s, %s, %s)""",
            (action_id, user['username'], tool, _dump(args), summary),
        )
    return {'id': action_id, 'tool': tool, 'summary': summary, 'status': 'pending',
            'title': TOOLS[tool]['title']}


def load_action(action_id: str) -> Optional[dict]:
    ensure_assistant_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, username, tool, args_json, summary, status, result_json, created_at,
                      created_at < NOW() - INTERVAL %s HOUR AS expired
               FROM assistant_actions WHERE id = %s""",
            (ACTION_TTL_HOURS, action_id),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    keys = ('id', 'username', 'tool', 'args_json', 'summary', 'status', 'result_json', 'created_at', 'expired')
    action = dict(zip(keys, row))
    action['args'] = json.loads(action.pop('args_json'))
    action['result'] = json.loads(action.pop('result_json')) if action['result_json'] else None
    return action


def _finish_action(action_id: str, status: str, result: dict):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """UPDATE assistant_actions SET status = %s, result_json = %s, resolved_at = NOW()
               WHERE id = %s""",
            (status, _dump(result), action_id),
        )


def public_action(action: dict) -> dict:
    tool = TOOLS.get(action['tool'], {})
    return {
        'id': action['id'],
        'tool': action['tool'],
        'title': tool.get('title', action['tool']),
        'summary': action['summary'],
        'status': action['status'],
        'result': action.get('result'),
    }


def confirm_action(action_id: str, user: dict) -> dict:
    action = load_action(action_id)
    if action is None:
        raise crm.NotFound('Действие не найдено')
    if action['username'] != user['username'] and user['role'] != 'admin':
        raise PermissionError('Это действие подготовлено для другого пользователя')
    if action['status'] != 'pending':
        raise crm.CrmError('Действие уже обработано')
    if action['expired']:
        _finish_action(action_id, 'expired', {'message': 'Черновик устарел — попросите ассистента заново'})
        raise crm.CrmError('Черновик устарел (старше суток) — попросите ассистента подготовить заново')

    with UseDatabase(config) as cursor:
        # Захват строки: двойной клик по «Подтвердить» не создаст два заказа.
        cursor.execute(
            "UPDATE assistant_actions SET status = 'running' WHERE id = %s AND status = 'pending'",
            (action_id,),
        )
        claimed = cursor.rowcount == 1
    if not claimed:
        raise crm.CrmError('Действие уже обработано')

    try:
        result = TOOLS[action['tool']]['execute'](action['args'], user)
        status = 'done'
    except (crm.CrmError, ValueError) as error:
        result, status = {'message': f'Не получилось: {error}'}, 'failed'
    except Exception as error:  # noqa: BLE001 — человеку нужен ответ, а не 500
        log.exception('assistant action %s failed', action_id)
        result, status = {'message': f'Ошибка при выполнении: {error}'}, 'failed'
    _finish_action(action_id, status, result)
    action.update(status=status, result=result)
    return public_action(action)


def cancel_action(action_id: str, user: dict) -> dict:
    action = load_action(action_id)
    if action is None:
        raise crm.NotFound('Действие не найдено')
    if action['username'] != user['username'] and user['role'] != 'admin':
        raise PermissionError('Это действие подготовлено для другого пользователя')
    if action['status'] != 'pending':
        return public_action(action)
    result = {'message': 'Отменено'}
    _finish_action(action_id, 'cancelled', result)
    action.update(status='cancelled', result=result)
    return public_action(action)


# ── compact views for the model ──────────────────────────────────────────────

def _money(value) -> str:
    return f"{float(value or 0):,.0f}".replace(',', ' ') + ' ₽'


def _order_brief(order: dict) -> dict:
    return {
        'id': order['id'],
        'customer_id': order['customer_id'],
        'customer': order.get('customer_full_name'),
        'phone': order.get('customer_phone'),
        'created': order.get('date'),
        'shipping_date': order.get('shipping_date'),
        'status': order.get('status'),
        'status_name': order.get('status_name'),
        'total': order.get('total_price'),
        'items': order.get('items_text'),
        'note': order.get('note'),
    }


def _customer_brief(customer: dict) -> dict:
    return {
        'id': customer['id'],
        'name': customer.get('full_name'),
        'phone': customer.get('phone'),
        'address': customer.get('address'),
        'email': customer.get('email'),
        'source': customer.get('source'),
        'tags': customer.get('tags'),
        'orders_count': customer.get('orders_count'),
        'total_spent': customer.get('total_spent'),
        'last_order_date': customer.get('last_order_date'),
        'open_orders': customer.get('open_orders'),
    }


def _task_brief(task: dict) -> dict:
    return {
        'id': task['id'],
        'title': task['title'],
        'due_date': task.get('due_date'),
        'priority': task.get('priority'),
        'is_done': task.get('is_done'),
        'is_overdue': task.get('is_overdue'),
        'customer_id': task.get('customer_id'),
        'order_id': task.get('order_id'),
        'details': task.get('details'),
    }


def _price_rows() -> List[dict]:
    with UseDatabase(config) as cursor:
        cursor.execute(
            "SELECT oil_name, volume, price FROM price_list WHERE price > 0 ORDER BY oil_name, volume"
        )
        return [{'oil_name': r[0], 'volume': int(r[1]), 'price': float(r[2])} for r in cursor.fetchall()]


def _arg_int(args: dict, key: str, required=True) -> Optional[int]:
    value = args.get(key)
    if value in (None, ''):
        if required:
            raise crm.CrmError(f'Не указан {key}')
        return None
    try:
        return int(str(value).lstrip('№#').strip())
    except ValueError:
        raise crm.CrmError(f'{key} должен быть числом, получено «{value}»')


def _arg_float(args: dict, key: str, default=0.0) -> float:
    value = args.get(key)
    if value in (None, ''):
        return default
    try:
        return float(str(value).replace(',', '.').replace(' ', ''))
    except ValueError:
        raise crm.CrmError(f'{key} должен быть числом, получено «{value}»')


def _fmt_date(value) -> str:
    parsed = crm.parse_date(value)
    return parsed.strftime('%d.%m.%Y') if parsed else '—'


def _status_label(status_id) -> str:
    statuses = {row['id']: row['name'] for row in crm.list_statuses()}
    if int(status_id) not in statuses:
        raise crm.CrmError(
            f'Нет статуса {status_id}. Есть: ' + ', '.join(f'{k} — {v}' for k, v in statuses.items())
        )
    return statuses[int(status_id)]


# ── read tools ───────────────────────────────────────────────────────────────

def tool_sql(args: dict) -> dict:
    query = (args.get('query') or args.get('sql') or '').strip().rstrip(';').strip()
    if not query:
        raise crm.CrmError('Пустой запрос')
    try:
        return run_readonly_query(query, max_rows=50)
    except mysql.connector.Error as error:
        # Текст ошибки MySQL нужен модели, чтобы она сама исправила запрос.
        raise crm.CrmError(f'MySQL: {getattr(error, "msg", error)}')


def tool_dashboard(args: dict) -> dict:
    data = crm.dashboard()
    return {
        'today': data['today'],
        'month': data['month'],
        'open_orders': data['open_orders'],
        'customers_total': data['customers_total'],
        'ship_today': [_order_brief(o) for o in data['ship_today']],
        'overdue': [_order_brief(o) for o in data['overdue'][:20]],
        'upcoming_7_days': [_order_brief(o) for o in data['upcoming'][:20]],
        'awaiting_payment': [_order_brief(o) for o in data['awaiting_payment'][:20]],
        'new_orders': [_order_brief(o) for o in data['new_orders'][:10]],
        'tasks_due': [_task_brief(t) for t in data['tasks_due']],
        'production_needs_14_days': data['production_needs'],
    }


def tool_find_customers(args: dict) -> dict:
    query = (args.get('query') or '').strip()
    customers = crm.list_customers(query or None, limit=15)
    return {'customers': [_customer_brief(c) for c in customers], 'count': len(customers)}


def tool_customer_card(args: dict) -> dict:
    card = crm.get_customer(_arg_int(args, 'customer_id'))
    return {
        'customer': {**_customer_brief(card), 'note': card.get('note'), 'created_at': card.get('created_at')},
        'favourite_products': card['favourite_products'],
        'orders': [_order_brief(o) for o in card['orders'][:15]],
        'interactions': [
            {'kind': i['kind_label'], 'text': i['text'], 'at': i['created_at'], 'author': i['author']}
            for i in card['interactions'][:15]
        ],
        'tasks': [_task_brief(t) for t in card['tasks'][:15]],
    }


def tool_orders(args: dict) -> dict:
    limit = min(_arg_int(args, 'limit', required=False) or 30, 50)
    # Модели присылают и true, и "true"/"false" строкой — "false" не должно стать True.
    open_only = args.get('open_only') in (True, 1) or str(args.get('open_only')).lower() in ('true', '1', 'yes', 'да')
    orders = crm.list_orders(
        status=args.get('status'),
        open_only=open_only,
        ship_from=args.get('ship_from'),
        ship_to=args.get('ship_to'),
        customer_id=_arg_int(args, 'customer_id', required=False),
        query=(args.get('query') or None),
        order_by='ship' if open_only else 'recent',
        limit=limit,
    )
    return {'orders': [_order_brief(o) for o in orders], 'count': len(orders)}


def tool_order(args: dict) -> dict:
    order = crm.get_order(_arg_int(args, 'order_id'))
    brief = _order_brief(order)
    brief['items'] = order['items']
    brief['history'] = order['history']
    brief['address'] = order.get('customer_address')
    return brief


def tool_price_list(args: dict) -> dict:
    return {'prices': _price_rows()}


def tool_stock(args: dict) -> dict:
    return {'stock': crm.stock_summary()}


def tool_production_needs(args: dict) -> dict:
    days = _arg_int(args, 'days', required=False) or 14
    return {'days': days, 'needs': crm.production_needs(days=max(1, min(days, 90)))}


def tool_production_plan(args: dict) -> dict:
    return crm.production_plan_for(args.get('oil_name'), args.get('volume') or args.get('volume_ml'))


def tool_production_schedule(args: dict) -> dict:
    days = _arg_int(args, 'days', required=False) or 14
    plan = crm.production_schedule(days=max(1, min(days, 60)))
    # Модели — только загруженные дни, иначе пустые даты съедают контекст.
    busy_days = [
        {'date': day['date'], 'weekday': day['weekday'], 'capacity': day['capacity'], 'used': day['used'],
         'presses': [{'press': press['press'], 'items': press['items']} for press in day['presses'] if press['items']]}
        for day in plan['days'] if day['used']
    ]
    return {
        'settings': plan['settings'],
        'load_percent': plan['load_percent'],
        'busy_days': busy_days,
        'items': plan['items'],
        'warnings': plan['warnings'],
        'seed_purchase': plan['seed_purchase'],
        'free_work_days': [day['date'] for day in plan['days'] if day['is_work_day'] and not day['used']][:10],
    }


def tool_tasks(args: dict) -> dict:
    status = args.get('status') if args.get('status') in ('open', 'done', 'all') else 'open'
    tasks = crm.list_tasks(status=status, limit=50)
    return {'tasks': [_task_brief(t) for t in tasks], 'count': len(tasks)}


def tool_expenses(args: dict) -> dict:
    entries = list_expense_entries(crm.parse_date(args.get('date_from')), crm.parse_date(args.get('date_to')))
    return {'expenses': entries[:40], 'count': len(entries),
            'total': sum(float(e['total_expense'] or 0) for e in entries)}


# ── write tools: prepare → (args, summary), execute → result ────────────────

def prepare_create_order(args: dict) -> Tuple[dict, str]:
    items = crm.resolve_order_items(args.get('items') or [])
    customer_id = _arg_int(args, 'customer_id', required=False)
    customer = args.get('customer') if isinstance(args.get('customer'), dict) else {}
    if customer_id is not None:
        row = crm.get_customer_row(customer_id)
        who = f"{row['full_name']} (клиент №{row['id']})"
        customer = {}
    else:
        existing = crm.find_customer_by_phone(customer.get('phone')) if customer.get('phone') else None
        if existing:
            customer_id = existing['id']
            who = f"{existing['name']} {existing.get('surname') or ''}".strip() + f" (уже есть, клиент №{existing['id']})"
            customer = {}
        else:
            if not (customer.get('name') or '').strip():
                raise crm.CrmError('Нужно имя клиента (или customer_id существующего)')
            customer = {key: customer.get(key) for key in ('name', 'surname', 'phone', 'address', 'email', 'source')
                        if customer.get(key)}
            who = ' '.join(filter(None, [customer.get('name'), customer.get('surname')]))
            who += f", {customer['phone']}" if customer.get('phone') else ''
            who += ' — новый клиент'

    shipping = crm.parse_date(args.get('shipping_date'), 'дата отгрузки') or date.today()
    status = _arg_int(args, 'status', required=False)
    status = crm.default_status_id() if status is None else status
    status_label = _status_label(status)
    note = (args.get('note') or '').strip() or None

    total = sum(item['price'] * item['count'] for item in items)
    lines = '; '.join(
        f"{item['oil_name']} {item['volume']} мл × {item['count']} по {_money(item['price'])}" for item in items
    )
    summary = (f"Заказ для {who}: {lines}. Итого {_money(total)}. "
               f"Отгрузка {shipping.strftime('%d.%m.%Y')}, статус «{status_label}»"
               + (f". Комментарий: {note}" if note else ''))
    prepared = {
        'customer_id': customer_id,
        'customer': customer,
        'items': items,
        'shipping_date': shipping.isoformat(),
        'status': status,
        'note': note,
    }
    return prepared, summary


def execute_create_order(args: dict, user: dict) -> dict:
    order = crm.create_order_record(
        args['items'],
        customer_id=args.get('customer_id'),
        customer=args.get('customer') or None,
        shipping_date=args.get('shipping_date'),
        status=args.get('status'),
        note=args.get('note'),
    )
    return {'message': f"Заказ №{order['id']} создан на {_money(order['total_price'])}",
            'order_id': order['id'], 'customer_id': order['customer_id'], 'link': f"/orders?focus={order['id']}"}


def prepare_update_order(args: dict) -> Tuple[dict, str]:
    order = crm.get_order(_arg_int(args, 'order_id'))
    changes, prepared = [], {'order_id': order['id']}
    status = _arg_int(args, 'status', required=False)
    if status is not None and status != order['status']:
        changes.append(f"статус «{order['status_name']}» → «{_status_label(status)}»")
        prepared['status'] = status
    if args.get('shipping_date'):
        shipping = crm.parse_date(args['shipping_date'], 'дата отгрузки')
        changes.append(f"отгрузка {_fmt_date(order['shipping_date'])} → {shipping.strftime('%d.%m.%Y')}")
        prepared['shipping_date'] = shipping.isoformat()
    if args.get('note') is not None and args.get('note') != order.get('note'):
        changes.append(f"комментарий: {args['note'] or '— (очистить)'}")
        prepared['note'] = args['note']
    if not changes:
        raise crm.CrmError('Нечего менять: укажите новый статус, дату отгрузки или комментарий')
    summary = f"Заказ №{order['id']} ({order['customer_full_name']}, {order['items_text']}): " + '; '.join(changes)
    return prepared, summary


def execute_update_order(args: dict, user: dict) -> dict:
    order = crm.update_order(args['order_id'], status=args.get('status'),
                             shipping_date=args.get('shipping_date'), note=args.get('note'))
    return {'message': f"Заказ №{order['id']} обновлён: {order['status_name']}, отгрузка {_fmt_date(order['shipping_date'])}",
            'order_id': order['id'], 'link': f"/orders?focus={order['id']}"}


def prepare_create_task(args: dict) -> Tuple[dict, str]:
    title = (args.get('title') or '').strip()
    if not title:
        raise crm.CrmError('Нужен заголовок задачи')
    due = crm.parse_date(args.get('due_date'), 'срок')
    customer_id = _arg_int(args, 'customer_id', required=False)
    order_id = _arg_int(args, 'order_id', required=False)
    extra = []
    if customer_id is not None:
        extra.append(f"клиент: {crm.get_customer_row(customer_id)['full_name']}")
    if order_id is not None:
        crm.get_order(order_id)
        extra.append(f"заказ №{order_id}")
    priority = _arg_int(args, 'priority', required=False)
    priority = 1 if priority is None else max(0, min(priority, 2))
    if priority == 2:
        extra.append('важная')
    summary = f"Задача «{title}», срок {due.strftime('%d.%m.%Y') if due else 'без срока'}"
    summary += f" ({', '.join(extra)})" if extra else ''
    prepared = {'title': title, 'details': (args.get('details') or '').strip() or None,
                'due_date': due.isoformat() if due else None, 'priority': priority,
                'customer_id': customer_id, 'order_id': order_id}
    return prepared, summary


def execute_create_task(args: dict, user: dict) -> dict:
    task = crm.create_task(created_by=user['username'], **args)
    return {'message': f"Задача №{task['id']} «{task['title']}» добавлена", 'task_id': task['id'], 'link': '/tasks'}


def prepare_complete_task(args: dict) -> Tuple[dict, str]:
    task = crm.get_task(_arg_int(args, 'task_id'))
    if task['is_done']:
        raise crm.CrmError(f"Задача №{task['id']} уже выполнена")
    return {'task_id': task['id']}, f"Отметить выполненной задачу №{task['id']} «{task['title']}»"


def execute_complete_task(args: dict, user: dict) -> dict:
    task = crm.update_task(args['task_id'], {'is_done': True})
    return {'message': f"Задача «{task['title']}» выполнена", 'task_id': task['id'], 'link': '/tasks'}


def prepare_create_customer(args: dict) -> Tuple[dict, str]:
    data = {key: args.get(key) for key in crm.CUSTOMER_FIELDS if args.get(key) not in (None, '')}
    if not (data.get('name') or '').strip():
        raise crm.CrmError('Нужно имя клиента')
    if data.get('phone'):
        existing = crm.find_customer_by_phone(data['phone'])
        if existing:
            raise crm.CrmError(f"Клиент с таким телефоном уже есть: №{existing['id']} {existing['name']}")
    parts = [' '.join(filter(None, [data.get('name'), data.get('surname')]))]
    parts += [data[key] for key in ('phone', 'address', 'email') if data.get(key)]
    if data.get('source'):
        parts.append(f"источник: {data['source']}")
    return data, 'Новый клиент: ' + ', '.join(parts)


def execute_create_customer(args: dict, user: dict) -> dict:
    customer = crm.create_customer(args)
    return {'message': f"Клиент №{customer['id']} {customer['full_name']} добавлен",
            'customer_id': customer['id'], 'link': f"/customers/{customer['id']}"}


def prepare_update_customer(args: dict) -> Tuple[dict, str]:
    customer = crm.get_customer_row(_arg_int(args, 'customer_id'))
    fields = args.get('fields') if isinstance(args.get('fields'), dict) else args
    data = {key: fields[key] for key in crm.CUSTOMER_FIELDS if key in fields and fields[key] != customer.get(key)}
    if not data:
        raise crm.CrmError('Нечего менять в карточке клиента')
    changes = '; '.join(f"{key}: {customer.get(key) or '—'} → {value or '—'}" for key, value in data.items())
    return {'customer_id': customer['id'], 'data': data}, f"Клиент №{customer['id']} {customer['full_name']}: {changes}"


def execute_update_customer(args: dict, user: dict) -> dict:
    customer = crm.update_customer(args['customer_id'], args['data'])
    return {'message': f"Карточка клиента {customer['full_name']} обновлена",
            'customer_id': customer['id'], 'link': f"/customers/{customer['id']}"}


def prepare_add_customer_note(args: dict) -> Tuple[dict, str]:
    customer = crm.get_customer_row(_arg_int(args, 'customer_id'))
    text = (args.get('text') or '').strip()
    if not text:
        raise crm.CrmError('Пустая заметка')
    kind = args.get('kind') if args.get('kind') in crm.INTERACTION_KINDS else 'note'
    summary = f"{crm.INTERACTION_KINDS[kind].capitalize()} в карточку {customer['full_name']}: {text}"
    return {'customer_id': customer['id'], 'text': text, 'kind': kind}, summary


def execute_add_customer_note(args: dict, user: dict) -> dict:
    crm.add_interaction(args['customer_id'], args['text'], args['kind'], user['username'])
    return {'message': 'Заметка добавлена в карточку клиента', 'customer_id': args['customer_id'],
            'link': f"/customers/{args['customer_id']}"}


def prepare_add_expense(args: dict) -> Tuple[dict, str]:
    item_name = (args.get('item_name') or '').strip()
    if not item_name:
        raise crm.CrmError('Нужно, на что потрачено (item_name)')
    expense_date = crm.parse_date(args.get('expense_date'), 'дата') or date.today()
    weight_kg = _arg_float(args, 'weight_kg')
    price_per_kg = _arg_float(args, 'price_per_kg')
    goods_total = _arg_float(args, 'goods_total', default=None)
    if goods_total is None:
        goods_total = weight_kg * price_per_kg
    delivery = _arg_float(args, 'delivery_cost')
    carsharing = _arg_float(args, 'carsharing_cost')
    total = goods_total + delivery + carsharing
    if total <= 0:
        raise crm.CrmError('Сумма расхода должна быть больше нуля')
    prepared = {
        'expense_date': expense_date.isoformat(), 'item_name': item_name[:200], 'weight_kg': weight_kg,
        'price_per_kg': price_per_kg, 'goods_total': goods_total, 'delivery_cost': delivery,
        'carsharing_cost': carsharing, 'note': (args.get('note') or '').strip()[:255] or None,
    }
    details = [f"товар {_money(goods_total)}"]
    if weight_kg:
        details.insert(0, f"{weight_kg:g} кг × {_money(price_per_kg)}")
    if delivery:
        details.append(f"доставка {_money(delivery)}")
    if carsharing:
        details.append(f"каршеринг {_money(carsharing)}")
    summary = f"Расход {expense_date.strftime('%d.%m.%Y')}: {item_name} — {', '.join(details)}. Всего {_money(total)}"
    return prepared, summary


def execute_add_expense(args: dict, user: dict) -> dict:
    expense_id = add_expense_entry(
        crm.parse_date(args['expense_date']), args['item_name'], args['weight_kg'], args['price_per_kg'],
        args['goods_total'], args['delivery_cost'], args['carsharing_cost'], args.get('note'),
    )
    return {'message': f"Расход «{args['item_name']}» записан", 'expense_id': expense_id, 'link': '/production'}


def prepare_add_production_batch(args: dict) -> Tuple[dict, str]:
    profiles = {row['oil_name']: row for row in list_production_profiles()}
    names = sorted(set(profiles) | {row['oil_name'] for row in _price_rows()})
    oil_name = crm.match_product_name(args.get('oil_name'), names)
    batch_date = crm.parse_date(args.get('batch_date'), 'дата') or date.today()
    profile = profiles.get(oil_name) or {}
    seed_weight = _arg_float(args, 'seed_weight_kg', default=float(profile.get('batch_seed_weight_kg') or 0))
    if seed_weight <= 0:
        raise crm.CrmError('Нужен вес семян в закладке (seed_weight_kg)')
    yield_percent = _arg_float(args, 'yield_percent', default=float(profile.get('yield_percent') or 0))
    output = _arg_float(args, 'output_volume_ml', default=None)
    if output is None:
        output = seed_weight * yield_percent * 10
    prepared = {
        'batch_date': batch_date.isoformat(), 'oil_name': oil_name, 'seed_weight_kg': seed_weight,
        'seed_price_per_kg': _arg_float(args, 'seed_price_per_kg'), 'yield_percent': yield_percent,
        'output_volume_ml': output, 'labor_cost': _arg_float(args, 'labor_cost'),
        'packaging_cost': _arg_float(args, 'packaging_cost'), 'other_cost': _arg_float(args, 'other_cost'),
        'note': (args.get('note') or '').strip()[:255] or None,
    }
    summary = (f"Закладка {batch_date.strftime('%d.%m.%Y')}: {oil_name}, семена {seed_weight:g} кг"
               + (f" по {_money(prepared['seed_price_per_kg'])}/кг" if prepared['seed_price_per_kg'] else '')
               + f", выход {yield_percent:g}% → {output:,.0f} мл масла".replace(',', ' '))
    return prepared, summary


def execute_add_production_batch(args: dict, user: dict) -> dict:
    batch_id = add_production_batch(
        crm.parse_date(args['batch_date']), args['oil_name'], args['seed_weight_kg'], args['seed_price_per_kg'],
        args['yield_percent'], args['output_volume_ml'], args['labor_cost'], args['packaging_cost'],
        args['other_cost'], args.get('note'),
    )
    return {'message': f"Закладка «{args['oil_name']}» записана", 'batch_id': batch_id, 'link': '/production'}


ToolSpec = Dict[str, object]

TOOLS: Dict[str, ToolSpec] = {
    'sql': {'kind': 'read', 'title': 'Запрос к базе', 'run': tool_sql,
            'params': '{"query": "один SELECT (MySQL 8) по схеме ниже"}',
            'help': 'любые вопросы с цифрами: выручка, топ клиентов/масел, динамика, сравнения'},
    'dashboard': {'kind': 'read', 'title': 'Сводка дня', 'run': tool_dashboard, 'params': '{}',
                  'help': 'что сегодня: отгрузки, просрочки, ждут оплаты, новые заказы, задачи, что отжимать'},
    'find_customers': {'kind': 'read', 'title': 'Поиск клиентов', 'run': tool_find_customers,
                       'params': '{"query": "имя, фамилия, телефон, тег или адрес"}', 'help': 'найти клиента'},
    'customer_card': {'kind': 'read', 'title': 'Карточка клиента', 'run': tool_customer_card,
                      'params': '{"customer_id": 12}', 'help': 'история заказов, заметки, задачи клиента'},
    'orders': {'kind': 'read', 'title': 'Заказы', 'run': tool_orders,
               'params': '{"status": 0, "open_only": true, "ship_from": "ГГГГ-ММ-ДД", "ship_to": "ГГГГ-ММ-ДД", '
                         '"customer_id": 1, "query": "текст", "limit": 30} — все поля необязательны',
               'help': 'список заказов с фильтрами (даты — по дате отгрузки)'},
    'order': {'kind': 'read', 'title': 'Заказ', 'run': tool_order, 'params': '{"order_id": 7}',
              'help': 'один заказ с позициями и историей статусов'},
    'price_list': {'kind': 'read', 'title': 'Прайс-лист', 'run': tool_price_list, 'params': '{}',
                   'help': 'актуальные цены'},
    'stock': {'kind': 'read', 'title': 'Остатки', 'run': tool_stock, 'params': '{}',
              'help': 'остатки готового масла: произведено, отгружено, в резерве, свободно'},
    'production_needs': {'kind': 'read', 'title': 'Потребность в отжиме', 'run': tool_production_needs,
                         'params': '{"days": 14}', 'help': 'сколько закладок нужно под открытые заказы'},
    'production_plan': {'kind': 'read', 'title': 'Расчёт закладок', 'run': tool_production_plan,
                        'params': '{"oil_name": "льняное", "volume": "5 л"}',
                        'help': 'сколько закладок/семян/дней нужно на объём масла'},
    'production_schedule': {'kind': 'read', 'title': 'План прессов', 'run': tool_production_schedule,
                            'params': '{"days": 14}',
                            'help': 'раскладка закладок по прессам и дням под открытые заказы: загрузка, '
                                    'свободные дни, что не успеваем, сколько семян купить. Для вопросов '
                                    '«когда успеем», «что отжимать завтра», «возьмём ли ещё заказ»'},
    'tasks': {'kind': 'read', 'title': 'Задачи', 'run': tool_tasks, 'params': '{"status": "open|done|all"}',
              'help': 'список задач'},
    'expenses': {'kind': 'read', 'title': 'Расходы', 'run': tool_expenses,
                 'params': '{"date_from": "ГГГГ-ММ-ДД", "date_to": "ГГГГ-ММ-ДД"}', 'help': 'журнал расходов'},

    'create_order': {'kind': 'write', 'title': 'Новый заказ',
                     'prepare': prepare_create_order, 'execute': execute_create_order,
                     'params': '{"customer_id": 5} ИЛИ {"customer": {"name": "Иван", "surname": "Петров", '
                               '"phone": "+79991234567", "address": "…", "source": "Avito"}}, '
                               '"items": [{"oil_name": "точное имя из прайса", "volume": 500, "count": 2}], '
                               '"shipping_date": "ГГГГ-ММ-ДД", "status": 0, "note": "…"',
                     'help': 'оформить заказ (цена берётся из прайса, если не указана)'},
    'update_order': {'kind': 'write', 'title': 'Изменить заказ',
                     'prepare': prepare_update_order, 'execute': execute_update_order,
                     'params': '{"order_id": 7, "status": 4, "shipping_date": "ГГГГ-ММ-ДД", "note": "…"}',
                     'help': 'сменить статус / дату отгрузки / комментарий'},
    'create_task': {'kind': 'write', 'title': 'Новая задача',
                    'prepare': prepare_create_task, 'execute': execute_create_task,
                    'params': '{"title": "…", "due_date": "ГГГГ-ММ-ДД", "priority": 0|1|2, '
                              '"customer_id": 5, "order_id": 7, "details": "…"}',
                    'help': 'напоминание или дело'},
    'complete_task': {'kind': 'write', 'title': 'Закрыть задачу',
                      'prepare': prepare_complete_task, 'execute': execute_complete_task,
                      'params': '{"task_id": 3}', 'help': 'отметить задачу выполненной'},
    'create_customer': {'kind': 'write', 'title': 'Новый клиент',
                        'prepare': prepare_create_customer, 'execute': execute_create_customer,
                        'params': '{"name": "…", "surname": "…", "phone": "…", "address": "…", "email": "…", '
                                  '"source": "Avito|Ozon|сарафан|…", "tags": "опт, постоянный", "note": "…"}',
                        'help': 'добавить клиента без заказа'},
    'update_customer': {'kind': 'write', 'title': 'Изменить клиента',
                        'prepare': prepare_update_customer, 'execute': execute_update_customer,
                        'params': '{"customer_id": 5, "fields": {"phone": "…", "address": "…", "tags": "…"}}',
                        'help': 'поправить карточку клиента'},
    'add_customer_note': {'kind': 'write', 'title': 'Заметка о клиенте',
                          'prepare': prepare_add_customer_note, 'execute': execute_add_customer_note,
                          'params': '{"customer_id": 5, "text": "…", "kind": "note|call|message|meeting"}',
                          'help': 'записать звонок, переписку, договорённость'},
    'add_expense': {'kind': 'write', 'title': 'Расход',
                    'prepare': prepare_add_expense, 'execute': execute_add_expense,
                    'params': '{"expense_date": "ГГГГ-ММ-ДД", "item_name": "семена льна", "weight_kg": 25, '
                              '"price_per_kg": 120, "goods_total": 3000, "delivery_cost": 500, '
                              '"carsharing_cost": 0, "note": "…"}',
                    'help': 'закупка сырья, тары, доставка и прочие траты'},
    'add_production_batch': {'kind': 'write', 'title': 'Закладка (партия)',
                             'prepare': prepare_add_production_batch, 'execute': execute_add_production_batch,
                             'params': '{"batch_date": "ГГГГ-ММ-ДД", "oil_name": "…", "seed_weight_kg": 10, '
                                       '"seed_price_per_kg": 150, "yield_percent": 30, "output_volume_ml": 3000, '
                                       '"labor_cost": 0, "packaging_cost": 0, "other_cost": 0, "note": "…"}',
                             'help': 'записать отжим; выход и норма берутся из профиля, если не указаны'},
}


# ── tool schemas (native tool calling) ───────────────────────────────────────
# Подмножество JSON Schema, которое понимают все провайдеры (в т.ч. Gemini через OpenRouter):
# type / properties / required / items / enum / description, без oneOf и additionalProperties.

def _obj(required=(), **properties) -> dict:
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = list(required)
    return schema


def _s(description='') -> dict:
    return {'type': 'string', 'description': description} if description else {'type': 'string'}


def _i(description='') -> dict:
    return {'type': 'integer', 'description': description} if description else {'type': 'integer'}


def _n(description='') -> dict:
    return {'type': 'number', 'description': description} if description else {'type': 'number'}


DATE = 'дата ГГГГ-ММ-ДД'
CUSTOMER_FIELDS_SCHEMA = dict(
    name=_s('имя'), surname=_s('фамилия'), phone=_s('телефон'), address=_s('адрес'), email=_s(),
    source=_s('откуда клиент: Avito, Ozon, сарафан…'), tags=_s('теги через запятую'), note=_s('заметка'),
)

TOOL_SCHEMAS = {
    'sql': _obj(['query'], query=_s('один SELECT (MySQL 8) по схеме из системного сообщения, без «;»')),
    'dashboard': _obj(),
    'find_customers': _obj(['query'], query=_s('имя, фамилия, телефон, тег или адрес')),
    'customer_card': _obj(['customer_id'], customer_id=_i()),
    'orders': _obj(
        status=_i('код статуса'), open_only={'type': 'boolean', 'description': 'только открытые'},
        ship_from=_s(f'отгрузка с, {DATE}'),
        ship_to=_s(f'отгрузка по, {DATE}'), customer_id=_i(), query=_s('поиск по имени, телефону, комментарию'),
        limit=_i('сколько заказов вернуть, до 50'),
    ),
    'order': _obj(['order_id'], order_id=_i()),
    'price_list': _obj(),
    'stock': _obj(),
    'production_needs': _obj(days=_i('горизонт в днях, по умолчанию 14')),
    'production_plan': _obj(['oil_name', 'volume'], oil_name=_s('масло'), volume=_s('объём: «5 л», «750 мл»')),
    'production_schedule': _obj(days=_i('горизонт в днях, по умолчанию 14')),
    'tasks': _obj(status={'type': 'string', 'enum': ['open', 'done', 'all']}),
    'expenses': _obj(date_from=_s(DATE), date_to=_s(DATE)),
    'create_order': _obj(
        ['items'],
        customer_id=_i('id существующего клиента — если нашёлся через find_customers'),
        customer=_obj(['name'], **{key: CUSTOMER_FIELDS_SCHEMA[key]
                                   for key in ('name', 'surname', 'phone', 'address', 'email', 'source')}),
        items={'type': 'array', 'items': _obj(
            ['oil_name', 'volume', 'count'],
            oil_name=_s('название точно как в прайсе'), volume=_i('объём бутылки в мл, как в прайсе'),
            count=_i('сколько бутылок'), price=_n('цена бутылки, если отличается от прайса'),
        )},
        shipping_date=_s(f'дата отгрузки, {DATE}'), status=_i('код статуса, по умолчанию «новый»'),
        note=_s('комментарий: время, доставка, пожелания'),
    ),
    'update_order': _obj(['order_id'], order_id=_i(), status=_i('новый код статуса'),
                         shipping_date=_s(f'новая дата отгрузки, {DATE}'), note=_s('комментарий')),
    'create_task': _obj(['title'], title=_s(), due_date=_s(DATE), priority=_i('0 низкий, 1 обычный, 2 важный'),
                        customer_id=_i(), order_id=_i(), details=_s()),
    'complete_task': _obj(['task_id'], task_id=_i()),
    'create_customer': _obj(['name'], **CUSTOMER_FIELDS_SCHEMA),
    'update_customer': _obj(['customer_id', 'fields'], customer_id=_i(),
                            fields=_obj(**CUSTOMER_FIELDS_SCHEMA)),
    'add_customer_note': _obj(['customer_id', 'text'], customer_id=_i(), text=_s(),
                              kind={'type': 'string', 'enum': ['note', 'call', 'message', 'meeting']}),
    'add_expense': _obj(
        ['item_name'], expense_date=_s(DATE), item_name=_s('на что потрачено'), weight_kg=_n(),
        price_per_kg=_n(), goods_total=_n('сумма за товар'), delivery_cost=_n(), carsharing_cost=_n(), note=_s(),
    ),
    'add_production_batch': _obj(
        ['oil_name'], batch_date=_s(DATE), oil_name=_s(), seed_weight_kg=_n('кг семян в закладке'),
        seed_price_per_kg=_n(), yield_percent=_n(), output_volume_ml=_n(), labor_cost=_n(), packaging_cost=_n(),
        other_cost=_n(), note=_s(),
    ),
}


def tool_schemas() -> List[dict]:
    tools = []
    for name, spec in TOOLS.items():
        description = spec['help']
        if spec['kind'] == 'write':
            description += '. Не записывает сразу: создаёт черновик, пользователь подтверждает его кнопкой'
        tools.append({'type': 'function', 'function': {
            'name': name, 'description': description, 'parameters': TOOL_SCHEMAS.get(name, _obj()),
        }})
    return tools


# ── prompt ───────────────────────────────────────────────────────────────────

_schema_cache: Dict[str, dict] = {}

SCHEMA_NOTES = """Смысл данных:
- orders: date — когда создан, shipping_date — когда отгрузить/выдать, total_price — сумма заказа,
  status → order_statuses.id. {status_rules}
- order_details: позиции заказа; volume — мл в бутылке, count — бутылок, price — цена бутылки,
  revenue / seed_cost / profit — по позиции целиком.
- customers: клиенты; поиск телефона — по цифрам: REGEXP_REPLACE(phone, '[^0-9]', '').
- statuses_list: история смены статусов заказа.
- expense_entries: расходы, итого строки = goods_total + delivery_cost + carsharing_cost.
- production_batches: закладки (отжимы); output_volume_ml — сколько мл масла получено.
- production_profiles: нормы по маслу — batch_seed_weight_kg (кг семян в закладке), yield_percent,
  daily_batch_limit (закладок в день). Масло с закладки, мл = кг × выход% × 10.
- tasks: задачи (is_done, due_date, priority 0..2); customer_interactions: заметки/звонки по клиентам."""


def describe_schema() -> str:
    database = active_database()
    cached = _schema_cache.get(database)
    if cached and time.time() - cached['at'] < 300:
        return cached['text']
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION""",
            (database,),
        )
        tables: Dict[str, List[str]] = {}
        for table, column, column_type in cursor.fetchall():
            if table in HIDDEN_TABLES:
                continue
            tables.setdefault(table, []).append(f'{column} {column_type}')
    text = '\n'.join(f"- {table}({', '.join(columns)})" for table, columns in tables.items())
    _schema_cache[database] = {'at': time.time(), 'text': text}
    return text


def _tools_text() -> str:
    lines = []
    for kind, header in (('read', 'Чтение (выполняются сразу):'),
                         ('write', 'Изменения (НЕ выполняются сразу — пользователь подтверждает кнопкой):')):
        lines.append(header)
        for name, spec in TOOLS.items():
            if spec['kind'] == kind:
                lines.append(f"- {name}: {spec['help']}. args: {spec['params']}")
    return '\n'.join(lines)


def _context_text(context: Optional[dict]) -> str:
    if not isinstance(context, dict):
        return ''
    parts = []
    try:
        if context.get('customer_id'):
            customer = crm.get_customer_row(int(context['customer_id']))
            parts.append(f"Пользователь сейчас в карточке клиента №{customer['id']} «{customer['full_name']}» — "
                         f"«этот клиент» = customer_id {customer['id']}.")
        if context.get('order_id'):
            order = crm.get_order(int(context['order_id']))
            parts.append(f"Пользователь сейчас смотрит заказ №{order['id']} ({order['customer_full_name']}).")
    except (crm.CrmError, ValueError):
        return ''
    if context.get('page'):
        parts.append(f"Открытый раздел: {context['page']}.")
    return '\n'.join(parts)


def _protocol_text(protocol: str) -> str:
    if protocol == 'tools':
        return (
            'Инструменты подключены как функции (function calling) — вызывай их напрямую, они доступны '
            'всегда. Можно несколько вызовов подряд и несколько за один шаг. Чтение (sql, dashboard, '
            'find_customers, orders, stock, production_schedule…) выполняется сразу; изменения (create_*, '
            'update_*, add_*, complete_task) создают черновик, который пользователь подтверждает кнопкой. '
            'Когда данных достаточно — ответь пользователю обычным текстом.'
        )
    return f"""Инструменты:
{_tools_text()}

ФОРМАТ. Каждый твой ответ — РОВНО ОДИН JSON-объект без текста вокруг:
- вызвать инструмент: {{"tool": "имя", "args": {{...}}}}
- ответить пользователю: {{"reply": "текст ответа"}}
После вызова ты получишь «РЕЗУЛЬТАТ ИНСТРУМЕНТА» и сделаешь следующий шаг. Можно несколько шагов подряд."""


def build_system_prompt(context: Optional[dict] = None, today: Optional[date] = None,
                        protocol: Optional[str] = None) -> str:
    protocol = protocol or agent_protocol()
    today = today or date.today()
    days = ', '.join(
        f"{WEEKDAYS[(today + timedelta(days=i)).weekday()]} {(today + timedelta(days=i)).isoformat()}"
        for i in range(1, 8)
    )
    statuses = ', '.join(f"{row['id']} — {row['name']}" for row in crm.list_statuses())
    cancelled = crm.status_ids('cancelled')
    closed = crm.closed_status_ids()
    status_rules = (
        f"Закрытые статусы (завершён/отменён): {', '.join(map(str, closed)) or 'нет'}. "
        f"Выручку и продажи считай без отменённых (status NOT IN ({', '.join(map(str, cancelled)) or '-1'})), "
        f"«открытые» заказы — status NOT IN ({', '.join(map(str, closed)) or '-1'})."
    )
    prices = '; '.join(f"{row['oil_name']} {row['volume']} мл = {row['price']:g} ₽" for row in _price_rows())
    profiles = '; '.join(
        f"{row['oil_name']}: закладка {row['batch_seed_weight_kg']:g} кг, выход {row['yield_percent']:g}%, "
        f"до {row['daily_batch_limit']} в день"
        for row in list_production_profiles()
    ) or 'не заданы'
    settings = crm.get_settings()
    business = os.getenv('OIL_BUSINESS_PROFILE') or settings['business_profile']
    work_days = ', '.join(crm.WEEKDAYS_SHORT[day - 1] for day in settings['work_days_list'])
    production = (
        f"{settings['presses_count']} пресс(а), каждый — до {settings['press_batches_per_day']} закладок за рабочий "
        f"день, итого до {settings['presses_count'] * settings['press_batches_per_day']} закладок в день. "
        f"Рабочие дни: {work_days}. Масло отстаивается {settings['settle_days']} дн. между отжимом и отгрузкой. "
        "Мощность прессов — главное ограничение: обещая сроки, проверяй её инструментом production_schedule."
    )
    context_text = _context_text(context)

    return f"""Ты — бизнес-помощник владельца в CRM производства «{settings['company_name']}». Работаешь с реальной
базой через инструменты: отвечаешь на вопросы о бизнесе, разбираешь заявки клиентов, планируешь загрузку
прессов, готовишь заказы, задачи, расходы и записи о производстве. Цель — экономить владельцу время и не
дать сорвать сроки: если видишь риск (просрочка, нехватка мощности или сырья, клиент ждёт оплату), скажи об этом
одной строкой и предложи конкретный следующий шаг.

О бизнесе: {business}
Производство: {production}

Сегодня {WEEKDAYS[today.weekday()]} {today.isoformat()}. Ближайшие дни: {days}.
Статусы заказов: {statuses}.
Прайс-лист: {prices or 'пуст'}.
Профили производства: {profiles}.
{context_text}

Схема базы (MySQL 8):
{describe_schema()}
{SCHEMA_NOTES.format(status_rules=status_rules)}

{_protocol_text(protocol)}

ПРАВИЛА:
1. Любые цифры, имена, статусы — только из результатов инструментов. Не выдумывай. Нет данных — так и скажи.
2. Для вопросов с подсчётами пиши один SELECT в инструмент sql (без точки с запятой, с LIMIT для списков).
   Ошибка SQL — исправь запрос и попробуй ещё раз.
3. Изменения — только через инструменты изменений. Они создают черновик, а пользователь подтверждает
   его кнопкой, поэтому НЕ спрашивай «подтвердить?» текстом и не повторяй один и тот же черновик. В ответе
   коротко перечисли подготовленное и попроси проверить карточку. Удалять ничего не умеешь — скажи, где это
   сделать вручную.
4. Заявка от клиента (текст из Avito, WhatsApp, Telegram): вытащи имя, телефон, адрес, позиции, дату.
   Сначала найди клиента (find_customers по телефону/имени) — если есть, используй его customer_id.
   Названия масел — точно как в прайсе, объём в мл из прайса; если объёма нет в прайсе или позиция
   неоднозначна — спроси. Дата не указана — предложи ближайшую, к которой успевают прессы
   (production_schedule), и упомяни её в ответе.
   {DICTATION_RULES}
5. Относительные даты («завтра», «в пятницу») переводи по списку ближайших дней выше.
6. Отвечай по-русски, коротко и по делу; списки — с «- », важное — **жирным**. Суммы — в рублях.
   Упоминай номера: «заказ №12», «клиент №5».
7. Если вопрос не про бизнес и не про данные — ответь кратко сам, без инструментов."""


# ── agent loop ───────────────────────────────────────────────────────────────

def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(part.get('text', '') for part in content if isinstance(part, dict))
    return str(content or '')


def call_llm_message(messages: List[dict], tools: Optional[List[dict]] = None,
                     tool_choice: Optional[str] = None) -> dict:
    """Один вызов модели; возвращает message целиком (content и, если есть, tool_calls)."""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise AssistantUnavailable('ИИ-помощник выключен: на сервере не задан OPENROUTER_API_KEY')
    payload = {
        'model': agent_model(),
        'messages': messages,
        'temperature': 0.2,
        'max_tokens': 2000,
        'stream': False,
        # Поля шлюза novpnai (остальные провайдеры их игнорируют): без веб-поиска и
        # памяти чатов — у агента свои данные, чужой контекст только мешает.
        'use_web': False,
        'use_rag': False,
    }
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = tool_choice or 'auto'
        # Только наши инструменты: «сделать файл» и «нарисовать» шлюза здесь лишние и сбивают модель.
        payload['gateway_tools'] = False
    response = requests.post(
        llm_url(),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=(10, 90),
    )
    response.raise_for_status()
    data = response.json()
    return data['choices'][0].get('message') or {}


def call_llm(messages: List[dict]) -> str:
    return _content_text(call_llm_message(messages).get('content'))


def first_json_object(raw: str, keys=None) -> Optional[dict]:
    """Первый JSON-объект в ответе модели (терпим к ```json и тексту вокруг); с keys — содержащий один из них."""
    text = re.sub(r'<think>.*?</think>', '', raw or '', flags=re.DOTALL).strip()
    decoder = json.JSONDecoder()
    position = text.find('{')
    while position != -1:
        try:
            value, _ = decoder.raw_decode(text, position)
        except ValueError:
            position = text.find('{', position + 1)
            continue
        if isinstance(value, dict) and (not keys or any(key in value for key in keys)):
            return value
        position = text.find('{', position + 1)
    return None


def parse_decision(raw: str) -> Optional[dict]:
    """Первый JSON-объект с ключом tool/reply из ответа модели."""
    return first_json_object(raw, ('tool', 'reply'))


# ── order from free text / voice ─────────────────────────────────────────────

def parse_order_text(text: str, today: Optional[date] = None) -> dict:
    """Свободный текст или диктовка → черновик заказа для формы (ничего не записывает).

    Один вызов модели вытаскивает клиента, позиции и дату; дальше всё проверяем по базе:
    позиции — по прайсу (с ценами), клиента — по телефону или имени.
    """
    text = (text or '').strip()
    if not text:
        raise crm.CrmError('Пустой текст заявки')
    today = today or date.today()
    days = ', '.join(
        f"{WEEKDAYS[(today + timedelta(days=i)).weekday()]} {(today + timedelta(days=i)).isoformat()}"
        for i in range(0, 8)
    )
    catalog = '; '.join(f"{row['oil_name']} {row['volume']} мл" for row in _price_rows())
    prompt = f"""Извлеки заказ из текста клиента или владельца. Верни ТОЛЬКО JSON:
{{"customer": {{"name": "", "surname": "", "phone": "", "address": ""}},
  "items": [{{"oil_name": "название ТОЧНО из каталога", "volume": 500, "count": 1}}],
  "shipping_date": "ГГГГ-ММ-ДД или пусто", "note": "всё прочее важное: время, доставка, пожелания"}}
Каталог (название объём): {catalog}
Дни: {days} (первый — сегодня).
{DICTATION_RULES}
Не выдумывай: чего нет в тексте — оставь пустым. Объём бери только из каталога для этого масла.

Текст: {text[:3000]}"""
    raw = call_llm([
        {'role': 'system', 'content': 'Ты извлекаешь данные заказа и отвечаешь только JSON.'},
        {'role': 'user', 'content': prompt},
    ])
    data = first_json_object(raw, ('items', 'customer')) or {}

    warnings, items = [], []
    for raw_item in data.get('items') or []:
        if not isinstance(raw_item, dict):
            continue
        try:
            items.extend(crm.resolve_order_items([raw_item]))
        except crm.CrmError as error:
            warnings.append(str(error))
    if not items and not warnings:
        warnings.append('Не нашёл в тексте ни одной позиции из прайса')

    customer = {key: str(value).strip() for key, value in (data.get('customer') or {}).items()
                if key in ('name', 'surname', 'phone', 'address') and value}
    match, candidates = None, []
    if customer.get('phone'):
        found = crm.find_customer_by_phone(customer['phone'])
        if found:
            match = crm.get_customer_row(found['id'])
    if match is None and customer.get('name'):
        query = ' '.join(filter(None, [customer.get('name'), customer.get('surname')]))
        candidates = crm.list_customers(query, limit=5) or crm.list_customers(customer['name'], limit=5)
        exact = [c for c in candidates if c['full_name'].lower() == query.lower()]
        if len(exact) == 1 and not customer.get('phone'):
            match = exact[0]

    shipping = None
    try:
        shipping = crm.parse_date(data.get('shipping_date'))
    except crm.CrmError:
        warnings.append(f"Не понял дату «{data.get('shipping_date')}»")

    def brief(row):
        return {'id': row['id'], 'full_name': row['full_name'], 'phone': row.get('phone'),
                'orders_count': row.get('orders_count'), 'last_order_date': row.get('last_order_date')}

    return {
        'customer': customer,
        'customer_match': brief(match) if match else None,
        'customer_candidates': [brief(row) for row in candidates if not match or row['id'] != match['id']][:5],
        'items': items,
        'shipping_date': shipping.isoformat() if shipping else None,
        'note': (data.get('note') or '').strip() or None,
        'warnings': warnings,
    }


def _history(messages) -> List[dict]:
    clean = []
    for message in (messages or [])[-HISTORY_MESSAGES:]:
        if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
            continue
        content = _content_text(message.get('content')).strip()
        if content:
            clean.append({'role': message['role'], 'content': content[:HISTORY_MESSAGE_CHARS]})
    if not clean or clean[-1]['role'] != 'user':
        raise crm.CrmError('Нет вопроса пользователя')
    return clean


def run_tool(name: str, args, user: dict, turn: dict) -> dict:
    spec = TOOLS.get(name)
    if spec is None:
        return {'error': f'Нет инструмента «{name}». Доступны: {", ".join(TOOLS)}'}
    if not isinstance(args, dict):
        return {'error': 'args должен быть JSON-объектом'}
    try:
        if spec['kind'] == 'read':
            result = spec['run'](args)
            if name == 'sql':
                turn['tables'].append({'query': (args.get('query') or args.get('sql') or '').strip(), **result})
            return result
        prepared, summary = spec['prepare'](args)
        signature = (name, _dump(prepared))
        for action in turn['actions']:
            if action.get('_signature') == signature:
                return {'status': 'черновик уже создан', 'action_id': action['id'],
                        'note': 'Этот черновик уже ждёт подтверждения. Не создавай его снова.'}
        action = save_pending_action(user, name, prepared, summary)
        action['_signature'] = signature
        turn['actions'].append(action)
        return {'status': 'черновик создан, ждёт подтверждения пользователем', 'action_id': action['id'],
                'summary': summary,
                'note': 'Действие ещё НЕ выполнено — пользователь нажмёт «Подтвердить» в карточке.'}
    except (crm.CrmError, ValueError) as error:
        return {'error': str(error)}
    except Exception as error:  # noqa: BLE001 — модель должна увидеть сбой и ответить человеку
        log.exception('assistant tool %s failed', name)
        return {'error': f'Сбой инструмента: {str(error)[:300]}'}


def _preview(result: dict) -> str:
    if 'error' in result:
        return 'ошибка: ' + str(result['error'])[:160]
    if 'rows' in result:
        return f"{len(result['rows'])} строк" + (' (обрезано)' if result.get('truncated') else '')
    if 'summary' in result:
        return str(result['summary'])[:160]
    if 'count' in result:
        return f"найдено: {result['count']}"
    return 'готово'


def _execute(name: str, args, user: dict, turn: dict) -> str:
    """Выполнить инструмент, записать шаг в трассу и вернуть наблюдение для модели."""
    result = run_tool(name, args, user, turn)
    turn['trace'].append({'tool': name, 'title': TOOLS.get(name, {}).get('title', name),
                          'args': args, 'ok': 'error' not in result, 'preview': _preview(result)})
    observation = _dump(result)
    if len(observation) > OBSERVATION_LIMIT:
        observation = observation[:OBSERVATION_LIMIT] + '… (обрезано — сузь запрос, если нужно больше)'
    return observation


def _json_loop(convo: List[dict], user: dict, turn: dict, deadline: float) -> str:
    """Запасной протокол: модель пишет {"tool": …} / {"reply": …} текстом."""
    for _ in range(MAX_STEPS):
        raw = call_llm(convo)
        decision = parse_decision(raw)
        if decision is None:
            return raw.strip()
        if not decision.get('tool'):
            return str(decision.get('reply') or '').strip()
        name, args = str(decision['tool']), decision.get('args') or {}
        observation = _execute(name, args, user, turn)
        convo.append({'role': 'assistant', 'content': _dump({'tool': name, 'args': args})})
        convo.append({'role': 'user', 'content': f'РЕЗУЛЬТАТ ИНСТРУМЕНТА {name}:\n{observation}'})
        if time.time() > deadline:
            break
    convo.append({'role': 'user', 'content': 'Шаги закончились. Сейчас же дай итоговый ответ пользователю '
                                             'по уже полученным данным: {"reply": "..."}'})
    raw = call_llm(convo)
    decision = parse_decision(raw)
    return str(decision.get('reply') or '').strip() if decision and not decision.get('tool') else raw.strip()


def _native_loop(convo: List[dict], user: dict, turn: dict, deadline: float) -> str:
    """Нативный tool calling: модель возвращает tool_calls, мы отвечаем сообщениями role=tool."""
    tools = tool_schemas()
    for _ in range(MAX_STEPS):
        message = call_llm_message(convo, tools=tools)
        calls = [call for call in (message.get('tool_calls') or []) if isinstance(call, dict)]
        content = _content_text(message.get('content')).strip()
        if not calls:
            # Некоторые модели всё равно пишут вызов текстом — понимаем и такой.
            decision = parse_decision(content)
            if decision and decision.get('tool'):
                name, args = str(decision['tool']), decision.get('args') or {}
                observation = _execute(name, args, user, turn)
                convo.append({'role': 'assistant', 'content': content})
                convo.append({'role': 'user', 'content': f'РЕЗУЛЬТАТ ИНСТРУМЕНТА {name}:\n{observation}'})
                continue
            return str(decision.get('reply') or '').strip() if decision and 'reply' in decision else content

        assistant_message = {'role': 'assistant', 'content': content or None, 'tool_calls': calls}
        if message.get('reasoning_details'):
            # Gemini 3 без своих «подписей мысли» отвергает продолжение после вызова.
            assistant_message['reasoning_details'] = message['reasoning_details']
        convo.append(assistant_message)
        for call in calls:
            function = call.get('function') or {}
            name = str(function.get('name') or '')
            raw_args = function.get('arguments')
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})
            except ValueError:
                args = None
            observation = (_dump({'error': 'arguments — не JSON-объект, повтори вызов'}) if args is None
                           else _execute(name, args, user, turn))
            convo.append({'role': 'tool', 'tool_call_id': call.get('id') or name, 'name': name,
                          'content': observation})
        if time.time() > deadline:
            break
    convo.append({'role': 'user', 'content': 'Шаги закончились. Ответь пользователю текстом по уже '
                                             'полученным данным, без новых вызовов.'})
    message = call_llm_message(convo, tools=tools, tool_choice='none')
    return _content_text(message.get('content')).strip()


def run_agent(messages, user: dict, context: Optional[dict] = None) -> dict:
    protocol = agent_protocol()
    convo = [{'role': 'system', 'content': build_system_prompt(context, protocol=protocol)}] + _history(messages)
    turn = {'actions': [], 'tables': [], 'trace': []}
    deadline = time.time() + TURN_DEADLINE_SECONDS
    loop = _native_loop if protocol == 'tools' else _json_loop
    reply = loop(convo, user, turn, deadline)

    if not reply:
        reply = 'Подготовил черновики — проверьте карточки ниже.' if turn['actions'] else 'Не смог сформулировать ответ.'
    return {
        'reply': reply,
        'actions': [{key: value for key, value in action.items() if not key.startswith('_')}
                    for action in turn['actions']],
        'trace': turn['trace'],
        'tables': turn['tables'][-3:],
    }


# ── HTTP ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix='/api/assistant')

# Демо открыто всем, а вызовы модели стоят денег: общий лимит на демо-доступ в час.
_demo_calls: List[float] = []


def _check_demo_quota(user: dict):
    if not user.get('is_demo'):
        return
    limit = int(os.getenv('OIL_DEMO_AI_PER_HOUR') or 40)
    now = time.time()
    _demo_calls[:] = [moment for moment in _demo_calls if now - moment < 3600]
    if len(_demo_calls) >= limit:
        raise HTTPException(status_code=429, detail='Лимит вопросов к ИИ в демо на этот час исчерпан. '
                                                    'Загляните чуть позже.')
    _demo_calls.append(now)


def _action_http(call, action_id: str, user: dict):
    try:
        return call(action_id, user)
    except crm.NotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except crm.CrmError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get('/status')
def api_status(user: dict = Depends(get_current_user)):
    return {'enabled': bool(os.getenv('OPENROUTER_API_KEY')), 'model': agent_model()}


@router.post('/chat')
def api_chat(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    _check_demo_quota(user)
    try:
        return run_agent(payload.get('messages'), user, payload.get('context'))
    except AssistantUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))
    except crm.CrmError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except requests.exceptions.RequestException as error:
        log.warning('assistant LLM call failed: %s', error)
        raise HTTPException(status_code=502, detail='ИИ-сервис не ответил. Попробуйте ещё раз через минуту.')


@router.post('/parse-order')
def api_parse_order(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    _check_demo_quota(user)
    try:
        return parse_order_text(payload.get('text') or '')
    except AssistantUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))
    except crm.CrmError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except requests.exceptions.RequestException as error:
        log.warning('parse-order LLM call failed: %s', error)
        raise HTTPException(status_code=502, detail='ИИ-сервис не ответил. Попробуйте ещё раз через минуту.')


@router.post('/actions/{action_id}/confirm')
def api_confirm(action_id: str, user: dict = Depends(get_current_user)):
    return _action_http(confirm_action, action_id, user)


@router.post('/actions/{action_id}/cancel')
def api_cancel(action_id: str, user: dict = Depends(get_current_user)):
    return _action_http(cancel_action, action_id, user)
