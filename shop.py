"""Публичная витрина: каталог, отзывы и заказ с сайта. Ручки без входа — /api/shop/*.

Витрина живёт на данных CRM: цены — из прайса, заказ с сайта — обычный заказ CRM (клиент
находится по телефону, статус «новый», план прессов его видит), а менеджер получает задачу
перезвонить и подтвердить. Онлайн-оплаты пока нет: о предоплате договариваются при звонке.

Покупатель — посторонний человек из интернета, поэтому:
- цена и сумма считаются только по прайсу; что прислал браузер — не важно;
- данные уже известного клиента не меняются и обратно не отдаются;
- с одного адреса — не больше нескольких заказов за полчаса, ботов ловит скрытое поле.
"""
import json
import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import mysql.connector
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

import crm
import reviews
from auth import _client_key, get_current_user, require_admin
from crm import CrmError, _norm_name, _rows
from UseDatabase import UseDatabase, active_database, config

log = logging.getLogger('oilpress.shop')


def _clean(value, limit=None):
    """crm._clean без эмодзи: текст пишет посторонний человек или Авито (см. crm.strip_astral)."""
    return crm._clean(None if value is None else crm.strip_astral(value), limit)

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
SEED_FILE = Path(__file__).resolve().parent / 'data' / 'shop_products.json'
CONTENT_FILE = Path(__file__).resolve().parent / 'data' / 'shop_content.json'
# Фото лежат под старыми именами файлов.
IMAGE_ALIASES = {'кунжут нешлифованный': 'кунжут не шлифованый'}
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# Не ищем отзывы по цвету: «черного тмина» и «кунжут черный» — разные масла.
COMMON_STEMS = ('черн', 'черё', 'бел', 'масл', 'сыро')

_catalog_cache: Dict[str, tuple] = {}
_order_attempts: Dict[str, List[float]] = {}
_schema_ready: set = set()


# ── каталог ──────────────────────────────────────────────────────────────────

def product_image(oil_name) -> Optional[str]:
    """Оформленная картинка static/images/products/<slug>.webp|jpg, если есть, иначе фото бутылки."""
    slug = slugify(oil_name)
    for extension in ('webp', 'jpg', 'jpeg', 'png'):
        if (IMAGE_DIR / 'products' / f'{slug}.{extension}').is_file():
            return f'/static/images/products/{slug}.{extension}'
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


TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя', [
    'a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't', 'u', 'f',
    'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))
SPECIAL_TITLES = {
    'кунжут черный': 'Масло чёрного кунжута',
    'кунжут нешлифованный': 'Масло нешлифованного кунжута',
}


def slugify(name) -> str:
    """«тыквы штирийской» → «tykvy-shtiriyskoy»: адрес страницы масла."""
    text = ''.join(TRANSLIT.get(char, char) for char in _norm_name(name))
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-') or 'oil'


def default_title(name) -> str:
    """В прайсе коротко («льняное», «черного тмина») — покупателю пишем «масло»."""
    clean = str(name or '').strip()
    key = _norm_name(clean)
    if key in SPECIAL_TITLES:
        return SPECIAL_TITLES[key]
    if key.startswith('масло'):
        return clean[:1].upper() + clean[1:]
    if ' ' not in key and key.endswith(('ое', 'ее')):
        return f'{clean[:1].upper()}{clean[1:]} масло'
    return f'Масло {clean}'


def catalog() -> List[dict]:
    """Масла из прайса с карточкой для сайта; скрытые в «Сайт и отзывы» не показываются."""
    cached = _catalog_cache.get('catalog')
    if cached and time.time() - cached[0] < CATALOG_CACHE_SECONDS:
        return cached[1]
    ensure_products_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT oil_name, volume, price FROM price_list WHERE price > 0 ORDER BY id")
        rows = _rows(cursor)
    cards = product_cards()
    free = _free_stock()
    products: Dict[str, dict] = {}
    for row in rows:
        key = _norm_name(row['oil_name'])
        card = cards.get(key, {})
        if card.get('is_hidden'):
            continue
        product = products.setdefault(key, {
            'name': row['oil_name'],
            'slug': slugify(row['oil_name']),
            'title': card.get('title') or default_title(row['oil_name']),
            'short_text': card.get('short_text'),
            'avito_url': card.get('avito_url'),
            'image': product_image(row['oil_name']),
            'sort_order': int(card.get('sort_order') or 0),
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
    result = sorted(products.values(), key=lambda product: (product['sort_order'], _norm_name(product['title'])))
    for product in result:
        product['variants'].sort(key=lambda variant: variant['volume'])
    _catalog_cache['catalog'] = (time.time(), result)
    return result


# ── карточки масел: описание, ссылка на Авито ───────────────────────────────

def ensure_products_schema():
    database = active_database()
    if database in _schema_ready:
        return
    crm.ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS shop_products (
                            product_key VARCHAR(100) PRIMARY KEY,
                            title VARCHAR(150) NULL,
                            short_text VARCHAR(300) NULL,
                            description TEXT NULL,
                            avito_url VARCHAR(500) NULL,
                            is_hidden TINYINT(1) NOT NULL DEFAULT 0,
                            sort_order INT NOT NULL DEFAULT 0,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                            )""")
        # Стартовые описания (перенесены с объявлений Авито). Только для масел, которых в таблице
        # ещё нет: правки из CRM, даже пустые, повторный старт не затирает.
        for seed in _seed_products():
            cursor.execute(
                """INSERT IGNORE INTO shop_products (product_key, title, short_text, description, avito_url, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    _norm_name(seed.get('name'))[:100],
                    _clean(seed.get('title'), 150),
                    _clean(seed.get('short_text'), 300),
                    _clean(seed.get('description')),
                    _clean(seed.get('avito_url'), 500),
                    int(seed.get('sort_order') or 0),
                ),
            )
    _schema_ready.add(database)


def _seed_products() -> List[dict]:
    try:
        rows = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        log.warning('shop: seed products are unavailable: %s', error)
        return []
    return [row for row in rows if isinstance(row, dict) and _clean(row.get('name'))]


def product_cards() -> Dict[str, dict]:
    ensure_products_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT product_key, title, short_text, description, avito_url, is_hidden, sort_order
               FROM shop_products"""
        )
        return {row['product_key']: row for row in _rows(cursor)}


def review_stems(name) -> tuple:
    """Начала слов названия для поиска отзывов: «тыквы штирийской» → «тыкв», «штир»."""
    return tuple(word[:4] for word in _norm_name(name).split()
                 if len(word) >= 4 and word[:4] not in COMMON_STEMS)


def reviews_about(name, limit=12) -> List[dict]:
    """Опубликованные отзывы, где в названии объявления или в тексте упомянуто это масло."""
    stems = review_stems(name)
    if not stems:
        return []
    found = []
    for review in reviews.public_reviews(limit=1000):
        words = re.findall(r'\w+', _norm_name(f'{review.get("item_title") or ""} {review.get("text") or ""}'))
        if any(word.startswith(stem) for word in words for stem in stems):
            found.append(review)
            if len(found) >= limit:
                break
    return found


def product_page(slug) -> dict:
    product = next((item for item in catalog() if item['slug'] == slug), None)
    if product is None:
        raise crm.NotFound('Такого масла нет в каталоге')
    card = product_cards().get(_norm_name(product['name']), {})
    return {**product, 'description': card.get('description'), 'reviews': reviews_about(product['name'])}


def list_product_cards() -> List[dict]:
    """Для CRM: все масла прайса с их карточками, включая скрытые."""
    ensure_products_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT DISTINCT oil_name FROM price_list WHERE price > 0")
        names = {_norm_name(row[0]): row[0] for row in cursor.fetchall()}
    cards = product_cards()
    result = []
    for key, name in names.items():
        card = cards.get(key, {})
        result.append({
            'name': name,
            'slug': slugify(name),
            'default_title': default_title(name),
            'title': card.get('title'),
            'short_text': card.get('short_text'),
            'description': card.get('description'),
            'avito_url': card.get('avito_url'),
            'is_hidden': bool(card.get('is_hidden')),
            'sort_order': int(card.get('sort_order') or 0),
            'image': product_image(name),
        })
    return sorted(result, key=lambda row: (row['sort_order'], _norm_name(row['title'] or row['default_title'])))


def update_product_card(slug, data: dict) -> dict:
    product = next((row for row in list_product_cards() if row['slug'] == slug), None)
    if product is None:
        raise crm.NotFound('Такого масла нет в прайсе')
    avito_url = _clean(data.get('avito_url'), 500)
    if avito_url and not crm.AVITO_URL_RE.match(avito_url):
        raise CrmError('Ссылка на объявление должна начинаться с https://www.avito.ru/')
    try:
        sort_order = int(data.get('sort_order') or 0)
    except (TypeError, ValueError):
        raise CrmError('Порядок — целое число')
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO shop_products (product_key, title, short_text, description, avito_url, is_hidden, sort_order)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE title = VALUES(title), short_text = VALUES(short_text),
                   description = VALUES(description), avito_url = VALUES(avito_url),
                   is_hidden = VALUES(is_hidden), sort_order = VALUES(sort_order)""",
            (
                _norm_name(product['name'])[:100],
                _clean(data.get('title'), 150),
                _clean(data.get('short_text'), 300),
                _clean(data.get('description'), 20000),
                avito_url,
                1 if data.get('is_hidden') else 0,
                sort_order,
            ),
        )
    _catalog_cache.clear()
    return next(row for row in list_product_cards() if row['slug'] == slug)


def shop_content() -> dict:
    try:
        content = json.loads(CONTENT_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return content if isinstance(content, dict) else {}


def shop_info() -> dict:
    settings = crm.get_settings()
    content = shop_content()
    return {
        'shop_name': settings['shop_name'],
        'about': settings['shop_about'] or content.get('about') or None,
        'phone': settings['shop_phone'] or None,
        'pickup_address': settings['shop_pickup_address'] or content.get('pickup_address') or None,
        # Профиль на Авито — значки доверия на сайте. Что вписано в CRM, важнее стартовых данных.
        'avito_profile_url': settings['avito_profile_url'] or content.get('avito_profile_url') or None,
        'avito_rating': settings['avito_rating'] or content.get('avito_rating') or None,
        'avito_reviews_count': settings['avito_reviews_count'] or content.get('avito_reviews_count') or None,
        'avito_sales_count': settings['avito_sales_count'] or content.get('avito_sales_count') or None,
        'avito_since': content.get('avito_since') or None,
        'avito_trusted': bool(content.get('avito_trusted')),
        'workshop_photos': [photo for photo in content.get('workshop_photos') or []
                            if isinstance(photo, dict) and str(photo.get('src', '')).startswith('/static/')],
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


@router.get('/products/{slug}')
def api_product(slug: str):
    return _public(product_page, slug)


@router.get('/reviews')
def api_reviews(limit: int = Query(30, ge=1, le=100)):
    return _public(reviews.public_reviews, limit)


@router.post('/orders')
def api_place_order(request: Request, payload: dict = Body(...)):
    # Скрытое поле: человек его не видит, бот заполняет. Отвечаем «успехом» и ничего не пишем.
    if _clean(payload.get('website')):
        return {'ok': True, 'order_id': None}
    return _public(place_order, payload, _client_key(request))


# Карточки масел в CRM: «Управление → Сайт и отзывы».
admin_router = APIRouter(prefix='/api/crm/shop-products')


@admin_router.get('')
def api_product_cards(user: dict = Depends(get_current_user)):
    return _public(list_product_cards)


@admin_router.put('/{slug}')
def api_update_product_card(slug: str, payload: dict = Body(...), admin: dict = Depends(require_admin)):
    return _public(update_product_card, slug, payload)
