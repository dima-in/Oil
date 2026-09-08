import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def _openai_reply(content: str):
    return mock.Mock(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": content}}]},
    )


def test_generate_sql_from_question_returns_string():
    with mock.patch("main.requests.post", return_value=_openai_reply("SELECT * FROM customers")):
        result = main.generate_sql_from_question("Сколько у нас клиентов?")
    assert isinstance(result, str)
    assert result.strip().upper().startswith("SELECT")


def test_generate_sql_from_question_calls_schema_and_validator():
    with mock.patch("main.requests.post", return_value=_openai_reply("SELECT * FROM customers")), \
         mock.patch("main.get_database_schema", return_value={"customers": {"columns": ["id"]}}) as mock_schema, \
         mock.patch("main.validate_sql_query", return_value=True) as mock_validate:
        result = main.generate_sql_from_question("Сколько у нас клиентов?")

    mock_schema.assert_called_once()
    mock_validate.assert_called_once()
    assert isinstance(result, str)


def test_generate_sql_from_question_rejects_invalid_sql():
    with mock.patch("main.requests.post", return_value=_openai_reply("DROP TABLE customers")):
        try:
            main.generate_sql_from_question("Удали всех клиентов")
            assert False, "Expected an exception to be raised for invalid SQL"
        except Exception as exc:
            assert isinstance(exc, ValueError)
