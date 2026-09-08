import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def test_get_database_schema_returns_dict():
    schema = main.get_database_schema()
    assert isinstance(schema, dict)


def test_schema_contains_all_tables():
    schema = main.get_database_schema()
    expected_tables = {
        'customers', 'orders', 'order_details', 'price_list',
        'expense_entries', 'production_batches', 'production_profiles',
        'order_statuses', 'statuses_list',
    }
    assert expected_tables.issubset(schema.keys())


def test_schema_contains_columns():
    schema = main.get_database_schema()
    expected_columns = {
        'customers': ['id', 'name', 'surname', 'phone', 'address'],
        'orders': ['id', 'customer_id', 'date', 'shipping_date', 'total_price', 'status'],
        'order_details': ['id', 'order_id', 'oil_name', 'volume', 'count', 'price'],
        'price_list': ['id', 'oil_name', 'volume', 'price'],
        'expense_entries': [
            'id', 'expense_date', 'item_name', 'weight_kg', 'price_per_kg',
            'goods_total', 'delivery_cost', 'carsharing_cost', 'note',
        ],
        'production_batches': [
            'id', 'batch_date', 'oil_name', 'seed_weight_kg', 'seed_price_per_kg',
            'yield_percent', 'output_volume_ml', 'labor_cost', 'packaging_cost',
            'other_cost', 'note',
        ],
        'production_profiles': ['id', 'oil_name', 'batch_seed_weight_kg', 'yield_percent', 'daily_batch_limit', 'note'],
        'order_statuses': ['id', 'name'],
        'statuses_list': ['id', 'order_id', 'order_status', 'name', 'datetime'],
    }
    for table_name, expected_cols in expected_columns.items():
        assert table_name in schema
        assert 'columns' in schema[table_name]
        assert schema[table_name]['columns'] == expected_cols


def test_schema_contains_relationships():
    schema = main.get_database_schema()
    assert 'relationships' in schema
    relationships = schema['relationships']
    assert isinstance(relationships, list)
    assert len(relationships) == 3
    expected_relationships = [
        {'from': 'orders.status', 'to': 'order_statuses.id'},
        {'from': 'orders.customer_id', 'to': 'customers.id'},
        {'from': 'order_details.order_id', 'to': 'orders.id'},
    ]
    for rel in expected_relationships:
        assert rel in relationships


def test_customers_columns():
    schema = main.get_database_schema()
    assert schema['customers']['columns'] == ['id', 'name', 'surname', 'phone', 'address']


def test_orders_columns():
    schema = main.get_database_schema()
    assert schema['orders']['columns'] == ['id', 'customer_id', 'date', 'shipping_date', 'total_price', 'status']
