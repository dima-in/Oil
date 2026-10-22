"""Вход в CRM: пользователи в БД, пароли в pbkdf2, подписанные токены.

Basic-авторизация по-прежнему принимается (старые страницы /view-all-orders и скрипты),
но веб-интерфейс ходит с Bearer-токеном и больше не держит пароль в коде страницы.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from UseDatabase import UseDatabase, config

TOKEN_TTL_SECONDS = 30 * 24 * 3600
PBKDF2_ROUNDS = 200_000
ROLES = ('admin', 'manager')

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10

_schema_ready = False
_secret_cache: Optional[bytes] = None
_login_attempts: Dict[str, List[float]] = {}


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


def ensure_auth_schema():
    global _schema_ready
    if _schema_ready:
        return
    with UseDatabase(config) as cursor:
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
        cursor.execute("SELECT COUNT(*) FROM app_users")
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
    with UseDatabase(config) as cursor:
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


def issue_token(user_id: int) -> str:
    body = _b64(json.dumps({'uid': user_id, 'exp': int(time.time()) + TOKEN_TTL_SECONDS}).encode('utf-8'))
    signature = _b64(hmac.new(_secret_key(), body.encode('ascii'), hashlib.sha256).digest())
    return f'{body}.{signature}'


def read_token(token: str) -> Optional[int]:
    try:
        body, signature = token.split('.')
        expected = _b64(hmac.new(_secret_key(), body.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if int(payload.get('exp', 0)) < time.time():
        return None
    return int(payload['uid'])


_USER_COLUMNS = 'id, username, password_hash, full_name, role, is_active, created_at'


def _user_from_row(row) -> Optional[dict]:
    if row is None:
        return None
    keys = ('id', 'username', 'password_hash', 'full_name', 'role', 'is_active', 'created_at')
    user = dict(zip(keys, row))
    user['is_active'] = bool(user['is_active'])
    return user


def find_user(username: Optional[str] = None, user_id: Optional[int] = None) -> Optional[dict]:
    ensure_auth_schema()
    with UseDatabase(config) as cursor:
        if user_id is not None:
            cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users WHERE id = %s", (user_id,))
        else:
            cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users WHERE username = %s", (username,))
        return _user_from_row(cursor.fetchone())


def list_users() -> List[dict]:
    ensure_auth_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(f"SELECT {_USER_COLUMNS} FROM app_users ORDER BY id")
        return [public_user(_user_from_row(row)) for row in cursor.fetchall()]


def public_user(user: dict) -> dict:
    return {
        'id': user['id'],
        'username': user['username'],
        'full_name': user.get('full_name') or '',
        'role': user['role'],
        'is_active': bool(user['is_active']),
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
        user_id = read_token(value)
        user = find_user(user_id=user_id) if user_id else None
    elif scheme.lower() == 'basic' and value:
        try:
            username, _, password = base64.b64decode(value).decode('utf-8').partition(':')
        except (ValueError, UnicodeDecodeError):
            username, password = '', ''
        user = authenticate(username, password) if username else None

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
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='Доступно только администратору')
    return user


def _check_login_rate(client_key: str):
    now = time.time()
    attempts = [moment for moment in _login_attempts.get(client_key, []) if now - moment < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail='Слишком много попыток входа. Подождите пару минут.')
    attempts.append(now)
    _login_attempts[client_key] = attempts


router = APIRouter(prefix='/api')


@router.post('/auth/login')
def login(request: Request, payload: dict = Body(...)):
    client_key = request.headers.get('X-Real-IP') or (request.client.host if request.client else 'unknown')
    _check_login_rate(client_key)
    user = authenticate((payload.get('username') or '').strip(), payload.get('password') or '')
    if not user:
        raise HTTPException(status_code=401, detail='Неверный логин или пароль')
    _login_attempts.pop(client_key, None)
    return {'token': issue_token(user['id']), 'user': public_user(user)}


@router.get('/auth/me')
def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.post('/auth/password')
def change_password(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    if not verify_password(payload.get('current_password') or '', user['password_hash']):
        raise HTTPException(status_code=400, detail='Текущий пароль указан неверно')
    new_password = payload.get('new_password') or ''
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Новый пароль — не короче 8 символов')
    with UseDatabase(config) as cursor:
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
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO app_users (username, password_hash, full_name, role)
               VALUES (%s, %s, %s, %s)""",
            (username, hash_password(password), (payload.get('full_name') or '').strip() or None, role),
        )
    return public_user(find_user(username=username))


@router.patch('/users/{user_id}')
def api_update_user(user_id: int, payload: dict = Body(...), admin: dict = Depends(require_admin)):
    target = find_user(user_id=user_id)
    if not target:
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
        with UseDatabase(config) as cursor:
            cursor.execute(f"UPDATE app_users SET {', '.join(sets)} WHERE id = %s", (*params, user_id))
    return public_user(find_user(user_id=user_id))
