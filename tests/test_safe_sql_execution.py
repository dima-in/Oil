import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def _fake_db(fetchall_return=None):
    cursor = mock.MagicMock()
    cursor.fetchall.return_value = fetchall_return if fetchall_return is not None else []
    cm = mock.MagicMock()
    cm.__enter__.return_value = cursor
    cm.__exit__.return_value = False
    return cm, cursor


def test_execute_safe_sql_runs_select():
    expected_rows = [(1, "Ivanov"), (2, "Petrov")]
    cm, cursor = _fake_db(fetchall_return=expected_rows)

    with mock.patch("main.UseDatabase", return_value=cm) as use_db_mock:
        result = main.execute_safe_sql("SELECT * FROM customers", ("param1",))

    assert result == expected_rows
    use_db_mock.assert_called_once_with(main.config)
    cursor.execute.assert_called_once_with("SELECT * FROM customers", ("param1",))
    cursor.fetchall.assert_called_once()


def test_execute_safe_sql_rejects_non_select():
    cm, cursor = _fake_db()

    with mock.patch("main.UseDatabase", return_value=cm) as use_db_mock:
        with mock.patch.object(cursor, "execute") as execute_mock:
            with mock.patch("pytest.raises", create=False):
                pass
            import pytest
            with pytest.raises(ValueError):
                main.execute_safe_sql("DELETE FROM customers WHERE id=1")

    use_db_mock.assert_not_called()
    cursor.execute.assert_not_called()


def test_execute_safe_sql_handles_db_error():
    cm, cursor = _fake_db()
    cursor.execute.side_effect = main.DatabaseError("connection lost")

    import pytest
    with mock.patch("main.UseDatabase", return_value=cm):
        with pytest.raises(RuntimeError):
            main.execute_safe_sql("SELECT * FROM customers")
