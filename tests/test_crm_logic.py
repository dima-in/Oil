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
