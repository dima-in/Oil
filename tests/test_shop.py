"""Витрина магазина: заказ с сайта, отзывы, страница. Без базы — данные CRM подменяются."""
from datetime import date

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import crm
import main
import reviews
import shop

client = TestClient(main.app)

PRICE = {('льняное', 250): 1560.0, ('льняное', 500): 2900.0, ('конопляное', 250): 1280.0}
SETTINGS = {**crm.DEFAULT_SETTINGS, 'work_days_list': [1, 2, 3, 4, 5, 6], 'settle_days': 1}


def order_payload(**overrides):
    payload = {
        'customer': {'name': 'Анна Козлова', 'phone': '+7 905 777-66-55', 'email': ''},
        'delivery': {'method': 'cdek', 'address': 'Москва, ПВЗ СДЭК на Тверской, 12'},
        'comment': 'позвоните после 18',
        'items': [{'oil_name': 'льняное', 'volume': 250, 'count': 2, 'price': 1}],
        'consent': True,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def fake_crm(monkeypatch):
    """Прайс, создание заказа и задачи — в памяти; запоминаем, что ушло в CRM."""
    calls = {'resolve': [], 'orders': [], 'tasks': []}

    def resolve(items):
        calls['resolve'].append(items)
        resolved = []
        for item in items:
            price = PRICE.get((item['oil_name'], int(item['volume'])))
            if price is None:
                raise crm.CrmError('Нет цены')
            resolved.append({**item, 'volume': int(item['volume']), 'price': price,
                             'seed_weight_kg': 0, 'seed_price_per_kg': 0})
        return resolved

    def create_order(items, customer=None, shipping_date=None, note=None, **kwargs):
        calls['orders'].append({'items': items, 'customer': customer, 'shipping_date': shipping_date, 'note': note})
        return {'id': 41 + len(calls['orders']), 'customer_id': 7}

    monkeypatch.setattr(crm, 'resolve_order_items', resolve)
    monkeypatch.setattr(crm, 'create_order_record', create_order)
    monkeypatch.setattr(crm, 'create_task', lambda title, **kwargs: calls['tasks'].append({'title': title, **kwargs}))
    monkeypatch.setattr(crm, 'get_settings', lambda: dict(SETTINGS))
    monkeypatch.setattr(shop, 'catalog', lambda: [
        {'name': 'льняное', 'variants': [{'volume': 250, 'price': 1560.0, 'in_stock': True}]},
    ])
    shop._order_attempts.clear()
    return calls


def test_order_price_comes_from_price_list_not_browser(fake_crm):
    resp = client.post('/api/shop/orders', json=order_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['order_id'] == 42
    assert body['total'] == 3120.0
    # В CRM не ушла цена из браузера, а клиент помечен как пришедший с сайта.
    assert all('price' not in item for item in fake_crm['resolve'][0])
    order = fake_crm['orders'][0]
    assert order['customer']['source'] == 'сайт'
    assert order['customer']['name'] == 'Анна' and order['customer']['surname'] == 'Козлова'
    assert order['note'].startswith('С сайта. СДЭК: Москва')
    task = fake_crm['tasks'][0]
    assert task['order_id'] == 42 and 'перезвонить' in task['title']
    assert '3120 ₽' in task['details']


def test_order_needs_consent_phone_and_address(fake_crm):
    assert client.post('/api/shop/orders', json=order_payload(consent=False)).status_code == 400
    bad_phone = order_payload(customer={'name': 'Анна', 'phone': '123'})
    assert 'телефон' in client.post('/api/shop/orders', json=bad_phone).json()['detail']
    no_address = order_payload(delivery={'method': 'courier', 'address': ''})
    assert 'адрес' in client.post('/api/shop/orders', json=no_address).json()['detail']
    pickup = order_payload(delivery={'method': 'pickup', 'address': 'что угодно'})
    assert client.post('/api/shop/orders', json=pickup).status_code == 200
    assert fake_crm['orders'][-1]['customer']['address'] is None
    assert len(fake_crm['orders']) == 1


def test_order_rejects_bad_counts_and_unknown_volume(fake_crm):
    too_many = order_payload(items=[{'oil_name': 'льняное', 'volume': 250, 'count': 500}])
    assert client.post('/api/shop/orders', json=too_many).status_code == 400
    unknown = order_payload(items=[{'oil_name': 'льняное', 'volume': 1000, 'count': 1}])
    assert client.post('/api/shop/orders', json=unknown).status_code == 400
    assert fake_crm['orders'] == []


def test_honeypot_pretends_success_and_writes_nothing(fake_crm):
    resp = client.post('/api/shop/orders', json=order_payload(website='http://spam'))
    assert resp.status_code == 200 and resp.json()['order_id'] is None
    assert fake_crm['orders'] == []


def test_order_rate_limit_counts_only_valid_orders(fake_crm):
    for _ in range(3):
        client.post('/api/shop/orders', json=order_payload(consent=False))  # ошибки не считаются
    for _ in range(shop.ORDER_LIMIT):
        assert client.post('/api/shop/orders', json=order_payload()).status_code == 200
    assert client.post('/api/shop/orders', json=order_payload()).status_code == 429


def test_shipping_date_waits_for_pressing_when_not_in_stock(fake_crm):
    friday = date(2026, 11, 20)
    in_stock = [{'oil_name': 'льняное', 'volume': 250, 'count': 1}]
    to_order = [{'oil_name': 'льняное', 'volume': 500, 'count': 1}]
    assert shop.suggest_shipping_date(in_stock, friday) == date(2026, 11, 21)    # суббота — рабочая
    assert shop.suggest_shipping_date(to_order, friday) == date(2026, 11, 24)    # +3 рабочих, без воскресенья


def test_shop_page_is_served_on_shop_path_and_shop_host(monkeypatch):
    # Шаблон подменяем: сигнатура TemplateResponse зависит от версии Starlette, а проверяем маршруты.
    monkeypatch.setattr(main.templates, 'TemplateResponse',
                        lambda name, context, **kwargs: HTMLResponse(f'{name} {context.get("company_name")}'))
    monkeypatch.setattr(crm, 'get_settings', lambda: dict(SETTINGS, company_name='Маслобойня'))
    assert client.get('/shop').text == 'shop.html Маслобойня'
    assert client.get('/shop/anything').text.startswith('shop.html')
    assert client.get('/').text.startswith('index.html')
    monkeypatch.setenv('OIL_SHOP_HOST', 'maslo.example, www.maslo.example')
    assert client.get('/', headers={'Host': 'www.maslo.example'}).text.startswith('shop.html')
    assert client.get('/orders', headers={'Host': 'maslo.example:443'}).text.startswith('shop.html')
    assert client.get('/', headers={'Host': 'crm.maslo.example'}).text.startswith('index.html')
    assert client.get('/api/nope', headers={'Host': 'maslo.example'}).status_code == 404


def test_info_exposes_only_public_settings(monkeypatch):
    monkeypatch.setattr(crm, 'get_settings', lambda: dict(
        SETTINGS, shop_phone='+7 900 000-00-00', avito_profile_url='https://www.avito.ru/brands/x',
        avito_rating=5.0, avito_reviews_count=278))
    body = client.get('/api/shop/info').json()
    assert body['avito_rating'] == 5.0 and body['avito_reviews_count'] == 278
    assert 'business_profile' not in body and 'tax_percent' not in body
    assert [method['id'] for method in body['delivery_methods']] == ['pickup', 'courier', 'cdek', 'post']


def test_avito_profile_url_must_be_avito():
    with pytest.raises(crm.CrmError, match='avito.ru'):
        crm.update_settings({'avito_profile_url': 'javascript:alert(1)'})


# ── отзывы ───────────────────────────────────────────────────────────────────

def test_parse_avito_review_handles_known_and_missing_fields():
    row = reviews.parse_avito_review({
        'id': 901, 'createdAt': 1763251200, 'score': 5, 'text': ' Отличное масло ',
        'sender': {'name': 'Ольга'}, 'item': {'id': 3, 'title': 'Льняное масло сыродавленное 250 мл'},
        'answer': {'id': 1, 'text': 'Спасибо!'},
    })
    assert row == {
        'external_id': '901', 'author': 'Ольга', 'rating': 5, 'text': 'Отличное масло',
        'item_title': 'Льняное масло сыродавленное 250 мл', 'reply': 'Спасибо!',
        'review_date': date(2025, 11, 16),
    }
    bare = reviews.parse_avito_review({'id': 'x1', 'createdAt': 1763251200000, 'score': 'bad'})
    assert bare['author'] == 'Покупатель' and bare['rating'] is None and bare['review_date'] == date(2025, 11, 16)
    assert reviews.parse_avito_review({'text': 'без id'}) is None


@pytest.mark.parametrize('title, oil', [
    ('Льняное масло сыродавленное 250 мл', True),
    ('Сыродавленное масло', True),
    ('Масло штирийской тыквы сыродавленное от 250 мл', True),
    ('Косметическое масло', True),
    ('Мешочек для маслопресса холодного отжима масла', False),
    ('Жмых штирийской тыквы от сыродавленного масла', False),
    ('Жмых амарантовый', False),
    ('Greco Jazz Bass JB600N Electric Bass', False),
    (None, False),
])
def test_only_oil_reviews_are_published_by_default(title, oil):
    assert reviews.is_oil_review(title) is oil


def test_page_review_id_is_stable():
    first = reviews.page_review_id('Ольга', date(2025, 10, 18), 'Спасибо!')
    assert first == reviews.page_review_id('Ольга', date(2025, 10, 18), 'Спасибо!')
    assert first.startswith('page:') and len(first) <= 64
    assert first != reviews.page_review_id('Ольга', date(2025, 10, 19), 'Спасибо!')


def test_import_rejects_wrong_file():
    with pytest.raises(crm.CrmError):
        reviews.import_page_reviews({'not': 'a list'})
    with pytest.raises(crm.CrmError):
        reviews.import_page_reviews([])


def test_public_author_hides_surname():
    assert reviews.public_author('Анна Козлова') == 'Анна К.'
    assert reviews.public_author('Ольга') == 'Ольга'
    assert reviews.public_author('  ') == 'Покупатель'


def test_reviews_admin_api_requires_admin(monkeypatch):
    monkeypatch.setattr(reviews, 'sync_avito', lambda: {'ok': True})
    assert client.post('/api/crm/reviews/sync').status_code == 401
    token = client.post('/api/auth/login', json={'username': 'worker', 'password': 'worker-pass-1'}).json()['token']
    resp = client.post('/api/crm/reviews/sync', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


def test_sync_without_keys_explains_what_to_do(monkeypatch):
    monkeypatch.delenv('AVITO_CLIENT_ID', raising=False)
    monkeypatch.delenv('AVITO_CLIENT_SECRET', raising=False)
    with pytest.raises(crm.CrmError, match='AVITO_CLIENT_ID'):
        reviews.sync_avito()
