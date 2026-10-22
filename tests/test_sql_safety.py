import pytest

from sql_safety import validate_sql_query


@pytest.mark.parametrize('query', [
    "SELECT COUNT(*) FROM orders WHERE status NOT IN (4, 6)",
    "WITH m AS (SELECT customer_id, SUM(total_price) s FROM orders GROUP BY customer_id) SELECT * FROM m",
    "SELECT name FROM customers WHERE note = 'drop table and delete'",
    "SELECT REGEXP_REPLACE(phone, '[^0-9]', '') FROM customers",
])
def test_allows_read_only_queries(query):
    assert validate_sql_query(query) is True


@pytest.mark.parametrize('query', [
    "SELECT LOAD_FILE('/etc/passwd')",
    "SELECT SLEEP(10)",
    "SELECT BENCHMARK(100000000, MD5('x'))",
    "SELECT GET_LOCK('a', 10)",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM mysql.user",
    "SELECT username, password_hash FROM app_users",
    "SELECT value FROM `app_settings`",
    "SELECT * FROM oilordersDB.assistant_actions",
    "SELECT 1 INTO @x",
    "SELECT * FROM orders FOR SHARE",
    # Литерал с \' : MySQL видит строку дальше, чем наивный разбор, — INTO OUTFILE не спрятать.
    "SELECT 'a\\' , ' INTO OUTFILE '/tmp/x'",
    "SELECT 1; DROP TABLE orders",
    "SELECT/**/1",
])
def test_rejects_unsafe_queries(query):
    assert validate_sql_query(query) is False
