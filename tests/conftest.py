import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import auth  # noqa: E402

# Пользователи для тестов без базы: тот же логин/пароль, что у первого владельца по умолчанию.
FAKE_USERS = {
    1: {
        'id': 1,
        'username': 'oilpress',
        'password_hash': auth.hash_password('MarshallJCM800'),
        'full_name': 'Владелец',
        'role': 'admin',
        'is_active': True,
        'created_at': None,
    },
    2: {
        'id': 2,
        'username': 'worker',
        'password_hash': auth.hash_password('worker-pass-1'),
        'full_name': 'Сотрудник',
        'role': 'manager',
        'is_active': True,
        'created_at': None,
    },
}


@pytest.fixture(autouse=True)
def fake_auth_users(monkeypatch):
    def find_user(username=None, user_id=None):
        if user_id is not None:
            return FAKE_USERS.get(int(user_id))
        return next((user for user in FAKE_USERS.values() if user['username'] == username), None)

    monkeypatch.setattr(auth, 'ensure_auth_schema', lambda: None)
    monkeypatch.setattr(auth, '_secret_key', lambda: b'test-secret')
    monkeypatch.setattr(auth, 'find_user', find_user)
    auth._login_attempts.clear()
    return FAKE_USERS
