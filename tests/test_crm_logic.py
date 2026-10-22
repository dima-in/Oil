from datetime import date

import pytest

import crm


@pytest.mark.parametrize('raw, expected', [
    (500, 500), ('500 мл', 500), ('0,5 л', 500), ('1 л', 1000), (1, 1000), ('250', 250), ('1.5l', 1500),
])
def test_parse_volume(raw, expected):
    assert crm.parse_volume(raw) == expected


def test_parse_volume_rejects_garbage():
    with pytest.raises(crm.CrmError):
        crm.parse_volume('много')


def test_match_product_name():
    names = ['льняное', 'тыквы штирийской', 'черного тмина', 'кунжут нешлифованный', 'кунжут черный']
    assert crm.match_product_name('Льняное', names) == 'льняное'
    assert crm.match_product_name('тыквенное', names) == 'тыквы штирийской'
    assert crm.match_product_name('чёрного тмина', names) == 'черного тмина'
    with pytest.raises(crm.CrmError, match='нескольким'):
        crm.match_product_name('кунжут', names)
    with pytest.raises(crm.CrmError, match='нет в прайс-листе'):
        crm.match_product_name('оливковое', names)


@pytest.mark.parametrize('name, role', [
    ('новый', 'new'), ('завершен', 'done'), ('Отменён', 'cancelled'), ('ожидает предоплаты', 'awaiting_payment'),
    ('получена предоплата', None), ('готов к выдаче', None), ('Avito доставка', None),
])
def test_status_role_by_name(name, role):
    assert crm._status_role(name) == role


def test_in_clause_handles_empty_lists():
    assert crm._in('o.status', []) == ('1=0', [])
    assert crm._in('o.status', [], negate=True) == ('1=1', [])
    assert crm._in('o.status', [4, 6], negate=True) == ('o.status NOT IN (%s, %s)', [4, 6])


def test_production_jobs_get_deadline_of_their_own_order(monkeypatch):
    """Дефицит режется по заказам: маленький ранний заказ не тянет к своей дате весь объём позднего."""
    orders = [
        {'id': 8, 'shipping_date': '2026-10-24', 'items': [{'oil_name': 'льняное', 'volume': 500, 'count': 1}]},
        {'id': 9, 'shipping_date': '2026-10-26', 'items': [{'oil_name': 'льняное', 'volume': 1000, 'count': 12}]},
    ]
    monkeypatch.setattr(crm, 'list_orders', lambda **kwargs: orders)
    needs = [{'oil_name': 'льняное', 'profile_ready': True, 'on_hand_ml': 0, 'shortage_ml': 12500}]
    profiles = {'льняное': {'batch_seed_weight_kg': 10, 'yield_percent': 30}}  # 3 л с закладки

    jobs = crm._production_jobs(needs, profiles, date(2026, 11, 5))
    assert [(job['deadline'], job['batches'], job['order_ids']) for job in jobs] == [
        (date(2026, 10, 24), 1, [8]),   # 0,5 л → одна закладка (3 л) к субботе
        (date(2026, 10, 26), 4, [9]),   # 12 л − 2,5 л остатка от первой закладки → ещё 4
    ]


def test_production_jobs_use_stock_on_hand(monkeypatch):
    orders = [{'id': 1, 'shipping_date': '2026-10-24', 'items': [{'oil_name': 'льняное', 'volume': 500, 'count': 4}]}]
    monkeypatch.setattr(crm, 'list_orders', lambda **kwargs: orders)
    needs = [{'oil_name': 'льняное', 'profile_ready': True, 'on_hand_ml': 5000, 'shortage_ml': 0}]
    profiles = {'льняное': {'batch_seed_weight_kg': 10, 'yield_percent': 30}}
    assert crm._production_jobs(needs, profiles, date(2026, 11, 5)) == []


def test_line_variable_cost_spreads_delivery_per_ml():
    import crm as crm_module
    norm = {'seeds_per_ml': 2 * 149 / 1000, 'delivery_per_ml': 50 * 2 / 1000}
    settings = {'bottle_cost': 23, 'tax_percent': 6}
    cost = crm_module.line_variable_cost(norm, 250, 2, 750, settings)
    assert round(cost['seeds'], 2) == 149.0       # 2 × 250 мл × 0,298 ₽/мл
    assert round(cost['delivery'], 2) == 50.0     # доставка на мл, а не на каждую бутылку целиком
    assert cost['bottle'] == 46
    assert round(cost['tax'], 2) == 90.0          # 6% от 1500
    assert round(cost['total'], 2) == 335.0


def test_unit_economics_hides_margin_without_seed_price(monkeypatch):
    class FakeCursor:
        def execute(self, *args):
            pass

        def fetchall(self):
            return [('кедровое', 100, 820), ('льняное', 500, 870)]

    class FakeDatabase:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return FakeCursor()

        def __exit__(self, *args):
            return False

    profiles = [
        {'oil_name': 'кедровое', 'batch_seed_weight_kg': 5, 'yield_percent': 25, 'seed_price_per_kg': 1300,
         'labor_per_batch': None},
        {'oil_name': 'льняное', 'batch_seed_weight_kg': 10, 'yield_percent': 30, 'seed_price_per_kg': None,
         'labor_per_batch': None},
    ]
    monkeypatch.setattr(crm, 'UseDatabase', FakeDatabase)
    monkeypatch.setattr(crm, 'list_production_profiles', lambda: profiles)
    monkeypatch.setattr(crm, 'get_settings', lambda: {'bottle_cost': 23, 'seed_delivery_per_kg': 50, 'tax_percent': 6})
    monkeypatch.setattr(crm, '_sold_ml_by_size', lambda today: {})

    data = crm.unit_economics()
    cedar, flax = data['items']
    assert cedar['seeds'] == 520.0 and cedar['low']   # 0,4 кг × 1300 ₽ съедают бóльшую часть цены
    assert flax['margin'] is None and flax['margin_percent'] is None and not flax['low']
    assert flax['batch_pay'] is None
    assert any('Не указана цена семян для: льняное' in warning for warning in data['warnings'])
    oils = {oil['oil_name']: oil for oil in data['oils']}
    # Закладка кедрового: 5 кг × 25% = 1250 мл; маржа 100 мл = 820 − 520 − 20 − 23 − 49,2 = 207,8 ₽
    assert oils['кедровое']['batch_pay'] == {'value': 2597.5, 'revenue': 10250.0, 'cost': 7652.5, 'min': 2597.5,
                                             'max': 2597.5, 'basis': 'price_list', 'sold_ml': 0}
    assert oils['льняное']['batch_pay'] is None


def test_batch_pay_follows_sales_mix():
    items = [{'volume': 250, 'price': 750.0, 'cost': 250.0, 'margin': 500.0},      # 2 ₽ с мл
             {'volume': 1000, 'price': 2000.0, 'cost': 1000.0, 'margin': 1000.0}]  # 1 ₽ с мл
    # Продали поровну по мл → 1,5 ₽ с мл × 3000 мл; выручка 2,5 ₽/мл, затраты 1 ₽/мл
    pay = crm.batch_pay(items, 3000, {250: 5000, 1000: 5000, 170: 340})
    assert pay == {'value': 4500.0, 'revenue': 7500.0, 'cost': 3000.0, 'min': 3000.0, 'max': 6000.0,
                   'basis': 'sales', 'sold_ml': 10340}
    # Брали только литры → получка как у литра
    assert crm.batch_pay(items, 3000, {1000: 4000})['value'] == 3000.0
    # Продаж нет → поровну по объёмам прайса
    assert crm.batch_pay(items, 3000, {})['basis'] == 'price_list'
    assert crm.batch_pay([{'volume': 250, 'price': 750.0, 'cost': 0, 'margin': None}], 3000, {}) is None
