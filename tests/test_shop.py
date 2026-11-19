"""Витрина магазина: заказ с сайта, отзывы, страница. Без базы — данные CRM подменяются."""
import re
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
                        lambda name, context, **kwargs: HTMLResponse(f'{name} {context.get("shop_name")}'))
    monkeypatch.setattr(crm, 'get_settings', lambda: dict(SETTINGS))
    assert client.get('/shop').text == 'shop.html Выжимальня'
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
    assert body['shop_name'] == 'Выжимальня'
    assert body['avito_rating'] == 5.0 and body['avito_reviews_count'] == 278
    assert 'business_profile' not in body and 'tax_percent' not in body
    assert [method['id'] for method in body['delivery_methods']] == ['pickup', 'courier', 'cdek', 'post']
    # Пустые настройки — текст «о мастерской» и адрес самовывоза из data/shop_content.json.
    assert 'бочонке' in body['about'] and 'Сходненская' in body['pickup_address']


# ── карточки масел ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('name, slug, title', [
    ('льняное', 'lnyanoe', 'Льняное масло'),
    ('тыквы штирийской', 'tykvy-shtiriyskoy', 'Масло тыквы штирийской'),
    ('черного тмина', 'chernogo-tmina', 'Масло черного тмина'),
    ('кунжут черный', 'kunzhut-chernyy', 'Масло чёрного кунжута'),
])
def test_slug_and_default_title(name, slug, title):
    assert shop.slugify(name) == slug
    assert shop.default_title(name) == title


def test_product_image_prefers_styled_picture(tmp_path, monkeypatch):
    (tmp_path / 'products').mkdir()
    (tmp_path / 'льняное.jpg').write_bytes(b'x')
    (tmp_path / 'конопляное.jpg').write_bytes(b'x')
    (tmp_path / 'products' / 'konoplyanoe.webp').write_bytes(b'x')
    monkeypatch.setattr(shop, 'IMAGE_DIR', tmp_path)
    assert shop.product_image('льняное') == '/static/images/льняное.jpg'
    assert shop.product_image('конопляное') == '/static/images/products/konoplyanoe.webp'
    assert shop.product_image('кокосовое') is None


def test_text_from_outside_loses_emoji_only():
    assert crm.strip_astral('Спасибо 🙏 всё супер 👍') == 'Спасибо всё супер '
    assert crm.strip_astral('Строка\n\nвторая') == 'Строка\n\nвторая'
    assert reviews._clean('  Огонь 🔥 ') == 'Огонь'


def test_seed_cards_cover_price_list_and_avoid_medical_claims():
    seeds = shop._seed_products()
    assert len(seeds) == 16
    assert len({shop.slugify(seed['name']) for seed in seeds}) == 16
    for seed in seeds:
        assert not seed.get('avito_url') or crm.AVITO_URL_RE.match(seed['avito_url'])
        text = f'{seed.get("short_text") or ""} {seed.get("description") or ""}'.lower()
        # Пищевому продукту нельзя приписывать лечение болезней (закон «О рекламе»).
        assert not any(word in text for word in ('рак', 'цирроз', 'гепатит', 'простат', 'диабет', 'паразит',
                                                 'лечени', 'лечит'))
        # Латинские буквы-двойники из объявлений Авито (Сыродaвленноe) вычищены.
        assert not any(re.search(r'[а-яё][a-z]|[a-z][а-яё]', word) for word in text.split())


def test_reviews_about_product_match_by_name(monkeypatch):
    monkeypatch.setattr(reviews, 'public_reviews', lambda limit=30: [
        {'id': 1, 'item_title': 'Масло штирийской тыквы сыродавленное от 250 мл', 'text': 'Отличное'},
        {'id': 2, 'item_title': 'Сыродавленное масло', 'text': 'Тыквенное масло очень хорошее!'},
        {'id': 3, 'item_title': 'Масло черного кунжута сыродавленное', 'text': 'Нежное'},
        {'id': 4, 'item_title': 'Масло черного тмина 100 мл', 'text': 'Потрясающее'},
    ])
    assert [row['id'] for row in shop.reviews_about('тыквы штирийской')] == [1, 2]
    # «черного» не в счёт: тмин и кунжут — разные масла.
    assert [row['id'] for row in shop.reviews_about('черного тмина')] == [4]
    assert [row['id'] for row in shop.reviews_about('кунжут черный')] == [3]


def test_product_page_and_unknown_slug(monkeypatch):
    monkeypatch.setattr(shop, 'catalog', lambda: [{'name': 'льняное', 'slug': 'lnyanoe', 'title': 'Льняное масло',
                                                    'variants': []}])
    monkeypatch.setattr(shop, 'product_cards', lambda: {'льняное': {'description': 'Из семян льна.'}})
    monkeypatch.setattr(shop, 'reviews_about', lambda name, limit=12: [{'id': 9}])
    body = client.get('/api/shop/products/lnyanoe').json()
    assert body['description'] == 'Из семян льна.' and body['reviews'] == [{'id': 9}]
    assert client.get('/api/shop/products/nope').status_code == 404


def test_product_card_avito_link_must_be_avito(monkeypatch):
    monkeypatch.setattr(shop, 'list_product_cards', lambda: [{'name': 'льняное', 'slug': 'lnyanoe'}])
    with pytest.raises(crm.CrmError, match='avito.ru'):
        shop.update_product_card('lnyanoe', {'avito_url': 'https://evil.example/'})
    with pytest.raises(crm.NotFound):
        shop.update_product_card('nope', {})


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
