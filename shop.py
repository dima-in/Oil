"""Публичная витрина: каталог, отзывы и заказ с сайта. Ручки без входа — /api/shop/*.

Витрина живёт на данных CRM: цены — из прайса, заказ с сайта — обычный заказ CRM (клиент
находится по телефону, статус «новый», план прессов его видит), а менеджер получает задачу
перезвонить и подтвердить. Онлайн-оплаты пока нет: о предоплате договариваются при звонке.

Покупатель — посторонний человек из интернета, поэтому:
- цена и сумма считаются только по прайсу; что прислал браузер — не важно;
- данные уже известного клиента не меняются и обратно не отдаются;
- с одного адреса — не больше нескольких заказов за полчаса, ботов ловит скрытое поле.
"""
import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import mysql.connector
from fastapi import APIRouter, Body, HTTPException, Query, Request

import crm
import reviews
from auth import _client_key
from crm import CrmError, _clean, _norm_name, _rows
from UseDatabase import UseDatabase, config

log = logging.getLogger('oilpress.shop')

DELIVERY_METHODS = {
    'pickup': {'label': 'Самовывоз', 'needs_address': False},
    'courier': {'label': 'Курьер по городу', 'needs_address': True},
    'cdek': {'label': 'СДЭК', 'needs_address': True},
    'post': {'label': 'Почта России', 'needs_address': True},
}
ORDER_LIMIT = 5
ORDER_WINDOW_SECONDS = 30 * 60
MAX_LINES = 30
MAX_COUNT = 50
CATALOG_CACHE_SECONDS = 60
IMAGE_DIR = Path(__file__).resolve().parent / 'static' / 'images'
# Фото лежат под старыми именами файлов.
IMAGE_ALIASES = {'кунжут нешлифованный': 'кунжут не шлифованый'}
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

_catalog_cache: Dict[str, tuple] = {}
_order_attempts: Dict[str, List[float]] = {}


# ── каталог ──────────────────────────────────────────────────────────────────

def product_image(oil_name) -> Optional[str]:
    name = _norm_name(oil_name)
    for candidate in (name, IMAGE_ALIASES.get(name)):
        if candidate and (IMAGE_DIR / f'{candidate}.jpg').is_file():
            return f'/static/images/{candidate}.jpg'
    return None


def _free_stock() -> Dict[str, float]:
    """Свободный остаток по маслам, где он известен (записаны партии)."""
    try:
        return {_norm_name(row['oil_name']): float(row['free_ml'] or 0)
                for row in crm.stock_summary() if row['tracked']}
    except Exception as error:  # noqa: BLE001 — без остатков каталог всё равно нужен
        log.warning('shop: stock is unavailable: %s', error)
        return {}


def catalog() -> List[dict]:
    cached = _catalog_cache.get('catalog')
    if cached and time.time() - cached[0] < CATALOG_CACHE_SECONDS:
        return cached[1]
    crm.ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT oil_name, volume, price FROM price_list WHERE price > 0 ORDER BY id")
        rows = _rows(cursor)
    free = _free_stock()
    products: Dict[str, dict] = {}
    for row in rows:
        key = _norm_name(row['oil_name'])
        product = products.setdefault(key, {
            'name': row['oil_name'],
            'image': product_image(row['oil_name']),
            'variants': [],
        })
        volume = int(row['volume'])
        # Дубли в прайсе: в заказе берётся первая цена (crm._price_index), здесь — та же.
        if any(variant['volume'] == volume for variant in product['variants']):
            continue
        product['variants'].append({
            'volume': volume,
            'price': float(row['price']),
            'in_stock': key in free and free[key] >= volume,
        })
    result = sorted(products.values(), key=lambda product: _norm_name(product['name']))
    for product in result:
        product['variants'].sort(key=lambda variant: variant['volume'])
    _catalog_cache['catalog'] = (time.time(), result)
    return result


def shop_info() -> dict:
    settings = crm.get_settings()
    return {
        'company_name': settings['company_name'],
        'phone': settings['shop_phone'] or None,
        'pickup_address': settings['shop_pickup_address'] or None,
        'avito_profile_url': settings['avito_profile_url'] or None,
        'avito_rating': settings['avito_rating'] or None,
        'avito_reviews_count': settings['avito_reviews_count'] or None,
        'delivery_methods': [{'id': key, **value} for key, value in DELIVERY_METHODS.items()],
    }


# ── заказ ────────────────────────────────────────────────────────────────────

def clean_items(raw_items) -> List[dict]:
    """Позиции из браузера: только масло, объём и количество — цену берём из прайса."""
    if not isinstance(raw_items, list) or not raw_items:
        raise CrmError('Корзина пуста')
    if len(raw_items) > MAX_LINES:
        raise CrmError('Слишком много позиций в одном заказе — позвоните нам')
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise CrmError('Не понял позицию заказа')
        try:
            count = int(raw.get('count'))
        except (TypeError, ValueError):
            raise CrmError('Количество должно быть числом')
        if not 1 <= count <= MAX_COUNT:
            raise CrmError(f'Количество одной позиции — от 1 до {MAX_COUNT}')
        items.append({'oil_name': raw.get('oil_name'), 'volume': raw.get('volume'), 'count': count})
    return crm.resolve_order_items(items)


def clean_contact(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    name = _clean(raw.get('name'), 100)
    if not name:
        raise CrmError('Укажите имя')
    phone = _clean(raw.get('phone'), 20)
    if not 10 <= len(crm.normalize_phone(phone)) <= 15:
        raise CrmError('Укажите телефон — по нему мы подтвердим заказ')
    email = _clean(raw.get('email'), 120)
    if email and not EMAIL_RE.match(email):
        raise CrmError('Проверьте email')
    first, _, last = name.partition(' ')
    return {'name': first[:50], 'surname': last.strip()[:50], 'phone': phone, 'email': email}


def clean_delivery(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    method = str(raw.get('method') or '')
    if method not in DELIVERY_METHODS:
        raise CrmError('Выберите способ доставки')
    address = _clean(raw.get('address'), 300)
    if DELIVERY_METHODS[method]['needs_address'] and len(address or '') < 5:
        raise CrmError('Укажите адрес доставки')
    if not DELIVERY_METHODS[method]['needs_address']:
        address = None
    label = DELIVERY_METHODS[method]['label']
    return {'method': method, 'address': address, 'text': f'{label}: {address}' if address else label}


def add_work_days(start: date, days: int, work_days: List[int]) -> date:
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.isoweekday() in work_days:
            left -= 1
    return current


def suggest_shipping_date(items: List[dict], today: Optional[date] = None) -> date:
    """Всё есть в остатке — ближайший рабочий день; иначе запас на отжим и отстаивание.

    Это ориентир для плана прессов: точную дату менеджер назовёт при звонке.
    """
    today = today or date.today()
    settings = crm.get_settings()
    stock = {_norm_name(product['name']): {v['volume']: v['in_stock'] for v in product['variants']}
             for product in catalog()}
    in_stock = all(stock.get(_norm_name(item['oil_name']), {}).get(int(item['volume'])) for item in items)
    lead = 1 if in_stock else 2 + int(settings['settle_days'])
    return add_work_days(today, lead, settings['work_days_list'])


def _check_order_rate(client_key: str):
    now = time.time()
    if len(_order_attempts) > 10000:
        _order_attempts.clear()
    recent = [moment for moment in _order_attempts.get(client_key, []) if now - moment < ORDER_WINDOW_SECONDS]
    if len(recent) >= ORDER_LIMIT:
        raise HTTPException(status_code=429, detail='Слишком много заказов подряд. Позвоните нам или попробуйте позже.')
    recent.append(now)
    _order_attempts[client_key] = recent


def place_order(payload: dict, client_key: str) -> dict:
    if payload.get('consent') is not True:
        raise CrmError('Для оформления нужно согласие на обработку персональных данных')
    contact = clean_contact(payload.get('customer'))
    delivery = clean_delivery(payload.get('delivery'))
    comment = _clean(payload.get('comment'), 1000)
    items = clean_items(payload.get('items'))
    _check_order_rate(client_key)

    total = sum(item['price'] * item['count'] for item in items)
    shipping_date = suggest_shipping_date(items)
    note = f'С сайта. {delivery["text"]}' + (f'. {comment}' if comment else '')
    order = crm.create_order_record(
        items,
        customer={**contact, 'address': delivery['address'], 'source': 'сайт'},
        shipping_date=shipping_date,
        note=note[:255],
    )

    lines = [f'— {item["oil_name"]}, {item["volume"]} мл × {item["count"]} = {item["price"] * item["count"]:.0f} ₽'
             for item in items]
    details = '\n'.join([
        f'Клиент: {contact["name"]} {contact["surname"]}'.strip() + f', {contact["phone"]}'
        + (f', {contact["email"]}' if contact['email'] else ''),
        f'Доставка: {delivery["text"]}',
        *([f'Комментарий: {comment}'] if comment else []),
        'Состав:',
        *lines,
        f'Итого без доставки: {total:.0f} ₽',
        'Позвоните клиенту: подтвердите состав, срок, стоимость доставки и предоплату.',
    ])
    try:
        crm.create_task(
            f'Заказ №{order["id"]} с сайта — перезвонить и подтвердить',
            details=details,
            due_date=date.today(),
            priority=2,
            customer_id=order['customer_id'],
            order_id=order['id'],
            created_by='сайт',
        )
    except Exception as error:  # noqa: BLE001 — заказ уже записан, задача — подсказка менеджеру
        log.warning('shop: task for order %s was not created: %s', order['id'], error)
    return {'ok': True, 'order_id': order['id'], 'total': total, 'shipping_date': shipping_date.isoformat()}


# ── HTTP ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix='/api/shop')


def _public(call, *args, **kwargs):
    try:
        return crm._http(call, *args, **kwargs)
    except mysql.connector.Error as error:
        log.error('shop: database error: %s', error)
        raise HTTPException(status_code=503, detail='Сайт временно недоступен — позвоните нам, пожалуйста')


@router.get('/info')
def api_info():
    return _public(shop_info)


@router.get('/catalog')
def api_catalog():
    return _public(catalog)


@router.get('/reviews')
def api_reviews(limit: int = Query(30, ge=1, le=100)):
    return _public(reviews.public_reviews, limit)


@router.post('/orders')
def api_place_order(request: Request, payload: dict = Body(...)):
    # Скрытое поле: человек его не видит, бот заполняет. Отвечаем «успехом» и ничего не пишем.
    if _clean(payload.get('website')):
        return {'ok': True, 'order_id': None}
    return _public(place_order, payload, _client_key(request))
