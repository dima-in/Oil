"""Вход в CRM: пользователи в БД, пароли в pbkdf2, подписанные токены.

Basic-авторизация по-прежнему принимается (старые страницы /view-all-orders и скрипты),
но веб-интерфейс ходит с Bearer-токеном и больше не держит пароль в коде страницы.

Демо-доступ: пользователь с is_demo работает в отдельной базе OIL_DEMO_DB. Признак демо
зашит в подписанный токен, DemoDatabaseMiddleware переключает на эту базу весь запрос,
а get_current_user ещё раз сверяет, что демо-пользователь не попал в рабочую базу.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from UseDatabase import UseDatabase, active_database, config, current_database

log = logging.getLogger('oilpress.auth')

TOKEN_TTL_SECONDS = 30 * 24 * 3600
DEMO_TOKEN_TTL_SECONDS = 24 * 3600
PBKDF2_ROUNDS = 200_000
ROLES = ('admin', 'manager')

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10
DEMO_LOGINS_PER_WINDOW = 30

_schema_ready = False
_secret_cache: Optional[bytes] = None
_login_attempts: Dict[str, List[float]] = {}
_demo_logins: Dict[str, List[float]] = {}


def demo_database() -> str:
    """Имя демо-базы; пусто — демо выключено."""
    return (os.getenv('OIL_DEMO_DB') or '').strip()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return f'pbkdf2${PBKDF2_ROUNDS}${salt}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, expected = stored.split('$')
        if scheme != 'pbkdf2':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(rounds))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def _main_db():
    # Пользователи и секреты — только в основной базе, даже посреди демо-запроса.
    return UseDatabase(config, use_override=False)


def ensure_auth_schema():
    global _schema_ready
    if _schema_ready:
        return
    with _main_db() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS app_users (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            username VARCHAR(50) NOT NULL UNIQUE,
                            password_hash VARCHAR(255) NOT NULL,
                            full_name VARCHAR(100) NULL,
                            role VARCHAR(20) NOT NULL DEFAULT 'manager',
                            is_active TINYINT(1) NOT NULL DEFAULT 1,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS app_settings (
                            name VARCHAR(64) PRIMARY KEY,
                            value TEXT NOT NULL
                            )""")
        cursor.execute(
            """SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'app_users' AND COLUMN_NAME = 'is_demo'""",
            (config['database'],),
        )
        if not cursor.fetchone()[0]:
            cursor.execute("ALTER TABLE app_users ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0")
        cursor.execute("SELECT COUNT(*) FROM app_users WHERE is_demo = 0")
        if cursor.fetchone()[0] == 0:
            # Первый владелец — из окружения; по умолчанию прежние логин/пароль,
            # чтобы обновление не заперло никого снаружи. Пароль меняется в «Настройках».
            cursor.execute(
                """INSERT IGNORE INTO app_users (username, password_hash, full_name, role)
                   VALUES (%s, %s, %s, 'admin')""",
                (
                    os.getenv('OIL_ADMIN_USER') or 'oilpress',
                    hash_password(os.getenv('OIL_ADMIN_PASSWORD') or 'MarshallJCM800'),
                    'Владелец',
                ),
            )
        if demo_database():
            # Демо-вход для показа (портфолио): логин и пароль публичные, видит только демо-базу.
            cursor.execute(
                """INSERT IGNORE INTO app_users (username, password_hash, full_name, role, is_demo)
                   VALUES (%s, %s, 'Демо-доступ', 'manager', 1)""",
                (os.getenv('OIL_DEMO_USER') or 'demo', hash_password(os.getenv('OIL_DEMO_PASSWORD') or 'demo')),
            )
    _schema_ready = True


def _secret_key() -> bytes:
    """Ключ подписи токенов: OIL_SECRET_KEY или случайный, сохранённый в БД один раз."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    env_key = os.getenv('OIL_SECRET_KEY')
    if env_key:
        _secret_cache = env_key.encode('utf-8')
        return _secret_cache
    ensure_auth_schema()
    with _main_db() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO app_settings (name, value) VALUES ('token_secret', %s)",
            (secrets.token_hex(32),),
        )
        cursor.execute("SELECT value FROM app_settings WHERE name = 'token_secret'")
        _secret_cache = cursor.fetchone()[0].encode('utf-8')
    return _secret_cache


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def issue_token(user_id: int, demo: bool = False) -> str:
    payload = {'uid': user_id, 'exp': int(time.time()) + (DEMO_TOKEN_TTL_SECONDS if demo else TOKEN_TTL_SECONDS)}
    if demo:
        payload['demo'] = True
    body = _b64(json.dumps(payload).encode('utf-8'))
    signature = _b64(hmac.new(_secret_key(), body.encode('ascii'), hashlib.sha256).digest())
    return f'{body}.{signature}'


def read_token_payload(token: str) -> Optional[dict]:
    try:
        body, signature = token.split('.')
        expected = _b64(hmac.new(_secret_key(), body.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or int(payload.get('exp', 0)) < time.time():
        return None
    return payload


def read_token(token: str) -> Optional[int]:
    payload = read_token_payload(token)
    return int(payload['uid']) if payload else None


_USER_COLUMNS = 'id, username, password_hash, full_name, role, is_active, created_at, is_demo'


def _user_from_row(row) -> Optional[dict]:
    if row is None:
        return None
    keys = ('id', 'username', 'password_hash', 'full_name', 'role', 'is_active', 'created_at', 'is_demo')
    user = dict(zip(keys, row))
    user['is_active'] = bool(user['is_active'])
    user['is_demo'] = bool(user['is_demo'])
    return user


def find_user(username: Optional[str] = None, user_id: Optional[int] = None) -> Optional[dict]:
    ensure_auth_schema()
    with _main_db() as cursor:
        if user_id is not None:
            cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users WHERE id = %s", (user_id,))
        else:
            cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users WHERE username = %s", (username,))
        return _user_from_row(cursor.fetchone())


def list_users() -> List[dict]:
    ensure_auth_schema()
    with _main_db() as cursor:
        cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users WHERE is_demo = 0 ORDER BY id")
        return [public_user(_user_from_row(row)) for row in cursor.fetchall()]


def public_user(user: dict) -> dict:
    return {
        'id': user['id'],
        'username': user['username'],
        'full_name': user.get('full_name') or '',
        'role': user['role'],
        'is_active': bool(user['is_active']),
        'is_demo': bool(user.get('is_demo')),
    }


def authenticate(username: str, password: str) -> Optional[dict]:
    user = find_user(username=username)
    if user and user['is_active'] and verify_password(password, user['password_hash']):
        return user
    return None


def get_current_user(request: Request) -> dict:
    header = request.headers.get('Authorization', '')
    scheme, _, value = header.partition(' ')
    value = value.strip()
    user = None
    if scheme.lower() == 'bearer' and value:
        payload = read_token_payload(value)
        user = find_user(user_id=int(payload['uid'])) if payload else None
        # Признак демо в токене и у пользователя должны совпадать, а демо-запрос обязан идти
        # в демо-базу: если middleware почему-то не переключил базу — отказ, а не рабочие данные.
        if user and (user['is_demo'] != bool(payload.get('demo'))
                     or (user['is_demo'] and active_database() != demo_database())):
            user = None
    elif scheme.lower() == 'basic' and value:
        try:
            username, _, password = base64.b64decode(value).decode('utf-8').partition(':')
        except (ValueError, UnicodeDecodeError):
            username, password = '', ''
        user = authenticate(username, password) if username else None
        if user and user['is_demo']:
            user = None  # Basic не переключает базу — демо только через токен

    if not user or not user['is_active']:
        # Для старых HTML-страниц оставляем браузерное окно Basic; API отвечает Bearer,
        # чтобы fetch из веб-интерфейса не вызывал системный диалог входа.
        challenge = 'Bearer' if request.url.path.startswith('/api/') else 'Basic'
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Требуется вход',
            headers={'WWW-Authenticate': challenge},
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user['role'] != 'admin' or user['is_demo']:
        raise HTTPException(status_code=403, detail='Доступно только администратору')
    return user


class DemoDatabaseMiddleware:
    """Запросы с демо-токеном целиком идут в демо-базу (через contextvar UseDatabase)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        database = demo_database()
        if scope.get('type') == 'http' and database:
            token = ''
            for name, raw in scope.get('headers') or []:
                if name == b'authorization':
                    scheme, _, rest = raw.decode('latin-1').partition(' ')
                    if scheme.lower() == 'bearer':
                        token = rest.strip()
                    break
            payload = read_token_payload(token) if token else None
            if payload and payload.get('demo'):
                marker = current_database.set(database)
                try:
                    await self.app(scope, receive, send)
                finally:
                    current_database.reset(marker)
                return
        await self.app(scope, receive, send)


def _client_key(request: Request) -> str:
    return request.headers.get('X-Real-IP') or (request.client.host if request.client else 'unknown')


def _check_rate(store: Dict[str, List[float]], client_key: str, limit: int, message: str):
    now = time.time()
    attempts = [moment for moment in store.get(client_key, []) if now - moment < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= limit:
        raise HTTPException(status_code=429, detail=message)
    attempts.append(now)
    store[client_key] = attempts


def _check_login_rate(client_key: str):
    _check_rate(_login_attempts, client_key, LOGIN_MAX_ATTEMPTS,
                'Слишком много попыток входа. Подождите пару минут.')


def _session(user: dict) -> dict:
    if user['is_demo']:
        if not demo_database():
            raise HTTPException(status_code=403, detail='Демо-доступ выключен')
        try:
            import demo_data  # лениво: модуль тянет crm, который сам импортирует auth
            demo_data.ensure_fresh(demo_database())
        except Exception as error:  # noqa: BLE001 — посетителю — понятный ответ, в лог — причина
            log.exception('demo database is not ready')
            raise HTTPException(status_code=503, detail='Демо временно недоступно') from error
    return {'token': issue_token(user['id'], demo=user['is_demo']), 'user': public_user(user)}


router = APIRouter(prefix='/api')


@router.post('/auth/login')
def login(request: Request, payload: dict = Body(...)):
    client_key = _client_key(request)
    _check_login_rate(client_key)
    user = authenticate((payload.get('username') or '').strip(), payload.get('password') or '')
    if not user:
        raise HTTPException(status_code=401, detail='Неверный логин или пароль')
    _login_attempts.pop(client_key, None)
    return _session(user)


@router.get('/auth/demo')
def demo_info():
    """Показывать ли на экране входа кнопку «Посмотреть демо»."""
    username = os.getenv('OIL_DEMO_USER') or 'demo'
    enabled = bool(demo_database())
    if enabled:
        user = find_user(username=username)
        enabled = bool(user and user['is_demo'] and user['is_active'])
    return {'enabled': enabled, 'username': username if enabled else None}


@router.post('/auth/demo')
def demo_login(request: Request):
    _check_rate(_demo_logins, _client_key(request), DEMO_LOGINS_PER_WINDOW,
                'Слишком много входов в демо. Подождите пару минут.')
    user = find_user(username=os.getenv('OIL_DEMO_USER') or 'demo') if demo_database() else None
    if not user or not user['is_demo'] or not user['is_active']:
        raise HTTPException(status_code=404, detail='Демо-доступ выключен')
    return _session(user)


@router.get('/auth/me')
def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.post('/auth/password')
def change_password(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    if user['is_demo']:
        raise HTTPException(status_code=403, detail='В демо-доступе пароль не меняется')
    if not verify_password(payload.get('current_password') or '', user['password_hash']):
        raise HTTPException(status_code=400, detail='Текущий пароль указан неверно')
    new_password = payload.get('new_password') or ''
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Новый пароль — не короче 8 символов')
    with _main_db() as cursor:
        cursor.execute("UPDATE app_users SET password_hash = %s WHERE id = %s", (hash_password(new_password), user['id']))
    return {'success': True}


@router.get('/users')
def api_list_users(admin: dict = Depends(require_admin)):
    return list_users()


@router.post('/users')
def api_create_user(payload: dict = Body(...), admin: dict = Depends(require_admin)):
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    role = payload.get('role') or 'manager'
    if not username or len(password) < 8:
        raise HTTPException(status_code=400, detail='Нужны логин и пароль не короче 8 символов')
    if role not in ROLES:
        raise HTTPException(status_code=400, detail='Роль: admin или manager')
    if find_user(username=username):
        raise HTTPException(status_code=400, detail='Такой логин уже есть')
    with _main_db() as cursor:
        cursor.execute(
            """INSERT INTO app_users (username, password_hash, full_name, role)
               VALUES (%s, %s, %s, %s)""",
            (username, hash_password(password), (payload.get('full_name') or '').strip() or None, role),
        )
    return public_user(find_user(username=username))


@router.patch('/users/{user_id}')
def api_update_user(user_id: int, payload: dict = Body(...), admin: dict = Depends(require_admin)):
    target = find_user(user_id=user_id)
    if not target or target['is_demo']:
        raise HTTPException(status_code=404, detail='Пользователь не найден')
    if user_id == admin['id'] and (payload.get('is_active') is False or payload.get('role') not in (None, 'admin')):
        raise HTTPException(status_code=400, detail='Нельзя отключить или понизить самого себя')

    sets, params = [], []
    if 'full_name' in payload:
        sets.append('full_name = %s')
        params.append((payload.get('full_name') or '').strip() or None)
    if payload.get('role') is not None:
        if payload['role'] not in ROLES:
            raise HTTPException(status_code=400, detail='Роль: admin или manager')
        sets.append('role = %s')
        params.append(payload['role'])
    if payload.get('is_active') is not None:
        sets.append('is_active = %s')
        params.append(1 if payload['is_active'] else 0)
    if payload.get('password'):
        if len(payload['password']) < 8:
            raise HTTPException(status_code=400, detail='Пароль — не короче 8 символов')
        sets.append('password_hash = %s')
        params.append(hash_password(payload['password']))
    if sets:
        with _main_db() as cursor:
            cursor.execute(f"UPDATE app_users SET {', '.join(sets)} WHERE id = %s", (*params, user_id))
    return public_user(find_user(user_id=user_id))
