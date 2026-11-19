"""Отзывы для сайта: с Авито и вписанные вручную.

С Авито отзывы и рейтинг забираются официальным API (раздел «Рейтинги и отзывы»);
ключи AVITO_CLIENT_ID / AVITO_CLIENT_SECRET выдаёт Авито PRO. Страницы Авито не парсим:
Авито закрывает их от роботов, а вёрстка меняется.

На сайт попадают только отзывы с галочкой «на сайте». Новый отзыв с Авито получает её
сам, если он о масле (в профиле продаются и другие вещи). Дальше решает человек:
синхронизация галочку не трогает.
"""
import hashlib
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timezone
from typing import List, Optional

import mysql.connector
import requests
from fastapi import APIRouter, Body, Depends, HTTPException

import crm
from auth import get_current_user, require_admin
from crm import CrmError, NotFound, _clean, _norm_name, _rows, parse_date
from UseDatabase import UseDatabase, active_database, config

log = logging.getLogger('oilpress.reviews')

AVITO_API = 'https://api.avito.ru'
AVITO_PAGE_SIZE = 50
AVITO_MAX_REVIEWS = 2000
AVITO_TIMEOUT = 20
SYNC_INTERVAL_SECONDS = 6 * 3600
SOURCE_LABELS = {'avito': 'Авито', 'manual': 'отзыв клиента'}

_schema_ready: set = set()
_sync_lock = threading.Lock()


def ensure_reviews_schema():
    database = active_database()
    if database in _schema_ready:
        return
    crm.ensure_crm_schema()
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS reviews (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            source VARCHAR(20) NOT NULL,
                            external_id VARCHAR(64) NULL,
                            author VARCHAR(100) NOT NULL,
                            rating TINYINT NULL,
                            text TEXT NOT NULL,
                            item_title VARCHAR(255) NULL,
                            reply TEXT NULL,
                            review_date DATE NULL,
                            is_published TINYINT(1) NOT NULL DEFAULT 1,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE KEY uq_reviews_source (source, external_id),
                            INDEX idx_reviews_public (is_published, review_date)
                            )""")
    _schema_ready.add(database)


# ── что показывать ───────────────────────────────────────────────────────────

# Объявления, где «масло» — не товар: «Жмых … от сыродавленного масла», «Мешочек для маслопресса».
NOT_OIL_WORDS = ('жмых', 'мешоч', 'маслопресс', 'протеин', 'скраб')


def is_oil_review(item_title: Optional[str]) -> bool:
    """Отзыв о масле: в названии объявления есть слово «масло» и нет слов про жмых и прочее."""
    title = _norm_name(item_title)
    if not re.search(r'\bмасл[оа]\b', title):
        return False
    return not any(word in title for word in NOT_OIL_WORDS)


def public_author(name: Optional[str]) -> str:
    """«Анна Козлова» → «Анна К.»: фамилию покупателя на сайте целиком не показываем."""
    words = (name or '').split()
    if not words:
        return 'Покупатель'
    if len(words) == 1:
        return words[0]
    return f'{words[0]} {words[1][0]}.'


def _decorate(row: dict) -> dict:
    row['is_published'] = bool(row.get('is_published'))
    row['source_label'] = SOURCE_LABELS.get(row.get('source'), row.get('source'))
    return row


def list_reviews(limit=1000) -> List[dict]:
    ensure_reviews_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, source, external_id, author, rating, text, item_title, reply, review_date,
                      is_published, created_at
               FROM reviews ORDER BY review_date IS NULL, review_date DESC, id DESC LIMIT %s""",
            (int(limit),),
        )
        return [_decorate(row) for row in _rows(cursor)]


def public_reviews(limit=30) -> List[dict]:
    """Только опубликованные и с текстом; имя сокращено, служебных полей нет."""
    ensure_reviews_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, source, author, rating, text, item_title, reply, review_date
               FROM reviews WHERE is_published = 1 AND TRIM(text) <> ''
               ORDER BY review_date IS NULL, review_date DESC, id DESC LIMIT %s""",
            (int(limit),),
        )
        rows = _rows(cursor)
    for row in rows:
        row['author'] = public_author(row['author'])
        row['source_label'] = SOURCE_LABELS.get(row['source'], row['source'])
    return rows


def get_review(review_id) -> dict:
    ensure_reviews_schema()
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, source, external_id, author, rating, text, item_title, reply, review_date,
                      is_published, created_at
               FROM reviews WHERE id = %s""",
            (int(review_id),),
        )
        rows = _rows(cursor)
    if not rows:
        raise NotFound(f'Отзыв №{review_id} не найден')
    return _decorate(rows[0])


def _rating(value) -> Optional[int]:
    if value in (None, ''):
        return None
    try:
        rating = int(round(float(value)))
    except (TypeError, ValueError):
        raise CrmError('Оценка — число от 1 до 5')
    if not 1 <= rating <= 5:
        raise CrmError('Оценка — число от 1 до 5')
    return rating


def create_review(data: dict) -> dict:
    """Отзыв, вписанный вручную (из переписки, с другой площадки, со слов клиента)."""
    ensure_reviews_schema()
    author = _clean(data.get('author'), 100)
    text = _clean(data.get('text'), 5000)
    if not author:
        raise CrmError('Укажите, кто оставил отзыв')
    if not text:
        raise CrmError('Нужен текст отзыва')
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO reviews (source, author, rating, text, item_title, review_date, is_published)
               VALUES ('manual', %s, %s, %s, %s, %s, %s)""",
            (
                author,
                _rating(data.get('rating')),
                text,
                _clean(data.get('item_title'), 255),
                parse_date(data.get('review_date'), 'дата отзыва') or date.today(),
                0 if data.get('is_published') is False else 1,
            ),
        )
        review_id = cursor.lastrowid
    return get_review(review_id)


def update_review(review_id, data: dict) -> dict:
    review = get_review(review_id)
    if 'is_published' in data:
        with UseDatabase(config) as cursor:
            cursor.execute("UPDATE reviews SET is_published = %s WHERE id = %s",
                           (1 if data['is_published'] else 0, review['id']))
    return get_review(review_id)


def delete_review(review_id):
    review = get_review(review_id)
    if review['source'] != 'manual':
        raise CrmError('Отзыв с Авито вернётся при следующей синхронизации — просто снимите галочку «на сайте»')
    with UseDatabase(config) as cursor:
        cursor.execute("DELETE FROM reviews WHERE id = %s", (review['id'],))


# ── синхронизация с Авито ────────────────────────────────────────────────────

def avito_credentials():
    client_id = (os.getenv('AVITO_CLIENT_ID') or '').strip()
    secret = (os.getenv('AVITO_CLIENT_SECRET') or '').strip()
    return (client_id, secret) if client_id and secret else None


def _state(names) -> dict:
    with UseDatabase(config) as cursor:
        cursor.execute(
            f"SELECT name, value FROM business_settings WHERE name IN ({', '.join(['%s'] * len(names))})",
            tuple(names),
        )
        return dict(cursor.fetchall())


def _set_state(values: dict):
    with UseDatabase(config) as cursor:
        for name, value in values.items():
            cursor.execute(
                """INSERT INTO business_settings (name, value) VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE value = VALUES(value)""",
                (name, value),
            )


def sync_status() -> dict:
    crm.ensure_crm_schema()
    state = _state(['avito_synced_at', 'avito_sync_error', 'avito_sync_result'])
    return {
        'configured': avito_credentials() is not None,
        'synced_at': state.get('avito_synced_at') or None,
        'error': state.get('avito_sync_error') or None,
        'result': state.get('avito_sync_result') or None,
    }


def parse_avito_review(raw: dict) -> Optional[dict]:
    """Отзыв из ответа /ratings/v1/reviews → строка таблицы. Незнакомые поля не роняют разбор."""
    if not isinstance(raw, dict) or raw.get('id') in (None, ''):
        return None
    created = raw.get('createdAt', raw.get('created_at'))
    review_date = None
    if isinstance(created, (int, float)) and not isinstance(created, bool) and created > 0:
        seconds = created / 1000 if created > 10 ** 11 else created  # бывает и в миллисекундах
        review_date = datetime.fromtimestamp(seconds, tz=timezone.utc).date()
    elif isinstance(created, str) and created:
        try:
            review_date = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
        except ValueError:
            review_date = None
    try:
        rating = _rating(raw.get('score', raw.get('rating')))
    except CrmError:
        rating = None
    sender = raw.get('sender') if isinstance(raw.get('sender'), dict) else {}
    item = raw.get('item') if isinstance(raw.get('item'), dict) else {}
    answer = raw.get('answer') if isinstance(raw.get('answer'), dict) else {}
    return {
        'external_id': str(raw['id'])[:64],
        'author': _clean(sender.get('name'), 100) or 'Покупатель',
        'rating': rating,
        'text': (raw.get('text') or '').strip()[:5000],
        'item_title': _clean(item.get('title'), 255),
        'reply': _clean(answer.get('text'), 5000),
        'review_date': review_date,
    }


def _avito_token(client_id, secret) -> str:
    response = requests.post(
        f'{AVITO_API}/token',
        data={'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': secret},
        timeout=AVITO_TIMEOUT,
    )
    if response.status_code in (400, 401, 403):
        raise CrmError('Авито не принял ключи: проверьте AVITO_CLIENT_ID и AVITO_CLIENT_SECRET')
    response.raise_for_status()
    token = (response.json() or {}).get('access_token')
    if not token:
        raise CrmError('Авито не выдал токен доступа')
    return token


def _avito_get(token, path, params=None) -> dict:
    response = requests.get(
        f'{AVITO_API}{path}',
        headers={'Authorization': f'Bearer {token}'},
        params=params,
        timeout=AVITO_TIMEOUT,
    )
    if response.status_code in (401, 403):
        raise CrmError(f'Авито не дал доступ к {path} (код {response.status_code}): '
                       'возможно, этот раздел API не входит в ваш тариф Авито PRO')
    response.raise_for_status()
    return response.json() or {}


def fetch_avito(client_id, secret) -> dict:
    token = _avito_token(client_id, secret)
    rating = (_avito_get(token, '/ratings/v1/info').get('rating') or {})
    reviews, offset = [], 0
    while offset < AVITO_MAX_REVIEWS:
        page = _avito_get(token, '/ratings/v1/reviews', {'offset': offset, 'limit': AVITO_PAGE_SIZE})
        batch = page.get('reviews') or []
        reviews.extend(row for row in map(parse_avito_review, batch) if row)
        offset += AVITO_PAGE_SIZE
        total = page.get('total')
        if len(batch) < AVITO_PAGE_SIZE or (isinstance(total, int) and offset >= total):
            break
    return {'score': rating.get('score'), 'count': rating.get('reviewsCount'), 'reviews': reviews}


def save_avito_reviews(reviews: List[dict]) -> int:
    """Вставить новые и обновить известные отзывы; галочку «на сайте» у известных не трогаем."""
    added = 0
    with UseDatabase(config) as cursor:
        for review in reviews:
            # Отзыв, перенесённый раньше со страницы (page:…), получает настоящий id Авито,
            # а не дублируется. Только если этого id ещё нет — иначе конфликт ключа.
            cursor.execute("SELECT 1 FROM reviews WHERE source = 'avito' AND external_id = %s",
                           (review['external_id'],))
            if cursor.fetchone() is None:
                cursor.execute(
                    """UPDATE reviews SET external_id = %s
                       WHERE source = 'avito' AND external_id LIKE 'page:%%' AND author = %s AND text = %s
                       LIMIT 1""",
                    (review['external_id'], review['author'], review['text']),
                )
            cursor.execute(
                """INSERT INTO reviews (source, external_id, author, rating, text, item_title, reply,
                                        review_date, is_published)
                   VALUES ('avito', %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE author = VALUES(author), rating = VALUES(rating),
                       text = VALUES(text), item_title = VALUES(item_title), reply = VALUES(reply),
                       review_date = VALUES(review_date)""",
                (
                    review['external_id'], review['author'], review['rating'], review['text'],
                    review['item_title'], review['reply'], review['review_date'],
                    1 if is_oil_review(review['item_title']) else 0,
                ),
            )
            if cursor.rowcount == 1:
                added += 1
    return added


def page_review_id(author, review_date, text) -> str:
    digest = hashlib.sha1(f'{author}|{review_date}|{text}'.encode('utf-8')).hexdigest()
    return f'page:{digest[:20]}'


def import_page_reviews(rows) -> dict:
    """Отзывы, перенесённые со страницы профиля Авито (пока не подключён API).

    Строка: author, rating, text, item_title, review_date. Повторный импорт того же файла
    ничего не дублирует, а снятую галочку «на сайте» не возвращает.
    """
    if not isinstance(rows, list) or not rows:
        raise CrmError('В файле нет отзывов')
    if len(rows) > 5000:
        raise CrmError('Слишком много отзывов в одном файле')
    ensure_reviews_schema()
    prepared = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise CrmError('Не понял формат файла: нужен список отзывов')
        text = (raw.get('text') or '').strip()[:5000]
        author = _clean(raw.get('author'), 100) or 'Покупатель'
        try:
            rating = _rating(raw.get('rating'))
        except CrmError:
            rating = None
        review_date = parse_date(raw.get('review_date'), 'дата отзыва')
        item_title = _clean(raw.get('item_title'), 255)
        prepared.append({
            'external_id': page_review_id(author, review_date, text),
            'author': author, 'rating': rating, 'text': text, 'item_title': item_title,
            'review_date': review_date, 'reply': _clean(raw.get('reply'), 5000),
        })
    added = 0
    with UseDatabase(config) as cursor:
        for review in prepared:
            cursor.execute(
                """INSERT IGNORE INTO reviews (source, external_id, author, rating, text, item_title, reply,
                                               review_date, is_published)
                   VALUES ('avito', %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    review['external_id'], review['author'], review['rating'], review['text'],
                    review['item_title'], review['reply'], review['review_date'],
                    1 if is_oil_review(review['item_title']) else 0,
                ),
            )
            added += cursor.rowcount
    published = sum(1 for review in prepared if is_oil_review(review['item_title']))
    return {'received': len(prepared), 'added': added, 'about_oil': published}


def sync_avito() -> dict:
    credentials = avito_credentials()
    if not credentials:
        raise CrmError('Синхронизация с Авито не настроена: впишите AVITO_CLIENT_ID и AVITO_CLIENT_SECRET в .env')
    if not _sync_lock.acquire(blocking=False):
        raise CrmError('Синхронизация уже идёт')
    try:
        ensure_reviews_schema()
        try:
            fetched = fetch_avito(*credentials)
            added = save_avito_reviews(fetched['reviews'])
            rating = {}
            if fetched['score'] is not None:
                rating['avito_rating'] = fetched['score']
            if fetched['count'] is not None:
                rating['avito_reviews_count'] = fetched['count']
            if rating:
                crm.update_settings(rating)
        except (CrmError, requests.RequestException, ValueError) as error:
            _set_state({'avito_sync_error': str(error)[:500]})
            raise
        result = f'получено {len(fetched["reviews"])}, новых {added}'
        _set_state({
            'avito_synced_at': datetime.now().isoformat(timespec='seconds'),
            'avito_sync_error': '',
            'avito_sync_result': result,
        })
        return {**sync_status(), 'fetched': len(fetched['reviews']), 'added': added}
    finally:
        _sync_lock.release()


def _sync_loop():
    time.sleep(60)  # пусть приложение и база поднимутся
    while True:
        try:
            sync_avito()
        except Exception as error:  # noqa: BLE001 — фоновая задача не должна умирать
            log.warning('avito reviews sync failed: %s', error)
        time.sleep(SYNC_INTERVAL_SECONDS)


def start_background_sync():
    """Раз в 6 часов забирать отзывы с Авито — только если ключи заданы."""
    if avito_credentials():
        threading.Thread(target=_sync_loop, name='avito-reviews', daemon=True).start()


# ── HTTP (CRM) ───────────────────────────────────────────────────────────────

router = APIRouter(prefix='/api/crm/reviews')


def _http(call, *args, **kwargs):
    try:
        return crm._http(call, *args, **kwargs)
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f'Авито не ответил: {error.__class__.__name__}')
    except mysql.connector.Error as error:
        raise HTTPException(status_code=503, detail=f'База недоступна: {error.msg}')


@router.get('')
def api_reviews(user: dict = Depends(get_current_user)):
    return _http(lambda: {'reviews': list_reviews(), 'avito': sync_status()})


@router.post('')
def api_create_review(payload: dict = Body(...), admin: dict = Depends(require_admin)):
    return _http(create_review, payload)


@router.patch('/{review_id}')
def api_update_review(review_id: int, payload: dict = Body(...), admin: dict = Depends(require_admin)):
    return _http(update_review, review_id, payload)


@router.delete('/{review_id}')
def api_delete_review(review_id: int, admin: dict = Depends(require_admin)):
    _http(delete_review, review_id)
    return {'ok': True}


@router.post('/sync')
def api_sync(admin: dict = Depends(require_admin)):
    return _http(sync_avito)


@router.post('/import')
def api_import(payload: dict = Body(...), admin: dict = Depends(require_admin)):
    return _http(import_page_reviews, payload.get('reviews'))
