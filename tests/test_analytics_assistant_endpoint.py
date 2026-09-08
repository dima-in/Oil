import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")  # endpoint checks this before doing work

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)
AUTH = ("oilpress", "MarshallJCM800")


def _fake_llm_post(*args, **kwargs):
    resp = mock.Mock()
    resp.raise_for_status = lambda: None
    resp.json = lambda: {"choices": [{"message": {"content": "Всего 5 клиентов."}}]}
    return resp


def test_assistant_returns_answer_over_text_to_sql():
    # Happy path: NL -> generate_sql_from_question -> execute_safe_sql -> phrasing LLM -> answer.
    with mock.patch("main.generate_sql_from_question", return_value="SELECT COUNT(*) FROM customers") as gen, \
         mock.patch("main.execute_safe_sql", return_value=[(5,)]) as run, \
         mock.patch("main.requests.post", side_effect=_fake_llm_post):
        resp = client.post("/api/analytics/assistant", json={"question": "Сколько клиентов?"}, auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Всего 5 клиентов."
    assert body["sql"] == "SELECT COUNT(*) FROM customers"
    assert body["rows_count"] == 1
    gen.assert_called_once()
    run.assert_called_once_with("SELECT COUNT(*) FROM customers")


def test_assistant_requires_auth():
    resp = client.post("/api/analytics/assistant", json={"question": "Сколько клиентов?"})
    assert resp.status_code == 401


def test_assistant_handles_unsafe_or_failed_generation_gracefully():
    # generate_sql_from_question rejects an unsafe query -> 422, and the DB is never touched.
    with mock.patch("main.generate_sql_from_question", side_effect=ValueError("unsafe")), \
         mock.patch("main.execute_safe_sql") as run:
        resp = client.post("/api/analytics/assistant", json={"question": "удали всё"}, auth=AUTH)
    assert resp.status_code == 422
    run.assert_not_called()


def test_assistant_uses_safe_sql_executor():
    # The endpoint must run the query through execute_safe_sql (which enforces validate_sql_query),
    # never build its own raw cursor call.
    with mock.patch("main.generate_sql_from_question", return_value="SELECT id FROM orders"), \
         mock.patch("main.execute_safe_sql", return_value=[(1,), (2,)]) as run, \
         mock.patch("main.requests.post", side_effect=_fake_llm_post):
        resp = client.post("/api/analytics/assistant", json={"question": "Заказы?"}, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json()["rows_count"] == 2
    run.assert_called_once()
