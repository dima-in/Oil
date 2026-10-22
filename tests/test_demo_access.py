"""Демо-вход: работает только в демо-базе и никогда не видит рабочую."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import auth
import demo_data
import main
from UseDatabase import active_database, config, connection_config

DEMO_DB = 'oil_demo_test'


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setenv('OIL_DEMO_DB', DEMO_DB)
    calls = []
    monkeypatch.setattr(demo_data, 'ensure_fresh', lambda database: calls.append(database))
    return calls


def probe_app():
    """Мини-приложение с тем же middleware: показывает, в какую базу ушёл бы запрос."""
    app = FastAPI()
    app.add_middleware(auth.DemoDatabaseMiddleware)

    @app.get('/api/probe')
    def probe(user: dict = Depends(auth.get_current_user)):
        return {'user': user['username'], 'database': active_database(),
                'connection_db': connection_config()['database']}

    return TestClient(app)


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def test_demo_button_logs_in_and_refreshes_demo_data(demo_on):
    client = TestClient(main.app)
    assert client.get('/api/auth/demo').json() == {'enabled': True, 'username': 'demo'}

    resp = client.post('/api/auth/demo')
    assert resp.status_code == 200
    assert resp.json()['user']['is_demo'] is True
    assert demo_on == [DEMO_DB]  # данные проверены/пересозданы на сегодня
    assert auth.read_token_payload(resp.json()['token'])['demo'] is True


def test_demo_disabled_without_env():
    client = TestClient(main.app)
    assert client.get('/api/auth/demo').json() == {'enabled': False, 'username': None}
    assert client.post('/api/auth/demo').status_code == 404
    # и по паролю демо-пользователь без демо-базы не входит
    assert client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo'}).status_code == 403


def test_demo_token_routes_requests_to_demo_database(demo_on):
    client = probe_app()
    demo = client.get('/api/probe', headers=bearer(auth.issue_token(3, demo=True))).json()
    assert demo == {'user': 'demo', 'database': DEMO_DB, 'connection_db': DEMO_DB}

    owner = client.get('/api/probe', headers=bearer(auth.issue_token(1))).json()
    assert owner['database'] == config['database']
    assert active_database() == config['database']  # контекст запроса не протёк наружу


def test_demo_user_cannot_reach_main_database(demo_on):
    client = probe_app()
    # токен демо-пользователя без признака demo (подделать признак нельзя — токен подписан)
    assert client.get('/api/probe', headers=bearer(auth.issue_token(3))).status_code == 401
    # Basic не переключает базу — демо-пользователю закрыт
    assert client.get('/api/probe', auth=('demo', 'demo')).status_code == 401
    # обычный пользователь с поддельным признаком demo не пройдёт: признак не совпадает с учёткой
    assert client.get('/api/probe', headers=bearer(auth.issue_token(1, demo=True))).status_code == 401


def test_demo_user_restrictions(demo_on):
    client = TestClient(main.app)
    token = client.post('/api/auth/demo').json()['token']
    headers = bearer(token)
    assert client.post('/api/auth/password', json={'current_password': 'demo', 'new_password': '12345678'},
                       headers=headers).status_code == 403
    assert client.get('/api/users', headers=headers).status_code == 403
    assert client.patch('/api/crm/settings', json={'presses_count': 5}, headers=headers).status_code == 403


def test_reset_refuses_non_demo_database():
    assert demo_data.is_demo_database('oil_demo')
    assert not demo_data.is_demo_database(config['database'])
    assert not demo_data.is_demo_database('production')
    with pytest.raises(RuntimeError):
        demo_data.reset(config['database'])
