import time

from fastapi.testclient import TestClient

import auth
import main

client = TestClient(main.app)


def test_password_hash_roundtrip():
    stored = auth.hash_password('secret-123')
    assert stored.startswith('pbkdf2$')
    assert auth.verify_password('secret-123', stored)
    assert not auth.verify_password('secret-124', stored)
    assert not auth.verify_password('x', 'garbage')


def test_login_returns_token_that_opens_api():
    resp = client.post('/api/auth/login', json={'username': 'oilpress', 'password': 'MarshallJCM800'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['user']['role'] == 'admin'
    assert 'password_hash' not in body['user']

    me = client.get('/api/auth/me', headers={'Authorization': f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()['username'] == 'oilpress'


def test_login_rejects_wrong_password():
    resp = client.post('/api/auth/login', json={'username': 'oilpress', 'password': 'nope'})
    assert resp.status_code == 401


def test_tampered_or_expired_token_is_rejected(monkeypatch):
    token = auth.issue_token(1)
    body, signature = token.split('.')
    assert auth.read_token(token) == 1
    assert auth.read_token(body + '.' + signature[::-1]) is None
    assert auth.read_token('not-a-token') is None

    later = time.time() + auth.TOKEN_TTL_SECONDS + 10
    monkeypatch.setattr(auth.time, 'time', lambda: later)
    assert auth.read_token(token) is None


def test_api_without_credentials_gets_bearer_challenge():
    resp = client.get('/api/crm/dashboard')
    assert resp.status_code == 401
    # Bearer, а не Basic: иначе браузер покажет системное окно логина поверх интерфейса.
    assert resp.headers['www-authenticate'] == 'Bearer'


def test_basic_auth_still_works_for_legacy_clients():
    resp = client.get('/api/auth/me', auth=('oilpress', 'MarshallJCM800'))
    assert resp.status_code == 200


def test_manager_cannot_manage_users():
    token = client.post('/api/auth/login', json={'username': 'worker', 'password': 'worker-pass-1'}).json()['token']
    resp = client.get('/api/users', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


def test_login_is_rate_limited():
    for _ in range(auth.LOGIN_MAX_ATTEMPTS):
        client.post('/api/auth/login', json={'username': 'oilpress', 'password': 'wrong'})
    resp = client.post('/api/auth/login', json={'username': 'oilpress', 'password': 'MarshallJCM800'})
    assert resp.status_code == 429


def test_legacy_endpoints_now_require_login():
    assert client.get('/api/analytics/summary').status_code == 401
    assert client.post('/delete-order', data={'id_to_delete': '1'}).status_code == 401
