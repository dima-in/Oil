import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def test_validate_sql_query_allows_select():
    assert main.validate_sql_query('SELECT * FROM customers') is True


def test_validate_sql_query_rejects_insert():
    assert main.validate_sql_query('INSERT INTO customers VALUES (...)') is False


def test_validate_sql_query_rejects_update():
    assert main.validate_sql_query('UPDATE customers SET name=...') is False


def test_validate_sql_query_rejects_delete():
    assert main.validate_sql_query('DELETE FROM customers WHERE id=1') is False


def test_validate_sql_query_rejects_drop():
    assert main.validate_sql_query('DROP TABLE customers') is False


def test_validate_sql_query_rejects_alter():
    assert main.validate_sql_query('ALTER TABLE customers ADD COLUMN test INT') is False


def test_validate_sql_query_rejects_multiple_statements():
    assert main.validate_sql_query('SELECT * FROM customers; DROP TABLE orders') is False


def test_validate_sql_query_allows_select_with_joins():
    assert main.validate_sql_query('SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id') is True
