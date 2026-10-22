"""Проверка и безопасное выполнение read-only SQL, который пишет ИИ-помощник."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

import mysql.connector

from UseDatabase import connection_config

# Служебные таблицы (пароли, секрет токенов, журнал действий ИИ) модели не показываем
# и читать не даём: ответы ассистента видит любой вошедший пользователь.
HIDDEN_TABLES = ('app_users', 'app_settings', 'assistant_actions')

# Литералы MySQL с учётом обоих видов экранирования ('' и \'). Без обработки \'
# валидатор и MySQL по-разному видят границы строки, и в «строку» можно спрятать
# INTO OUTFILE.
_LITERAL_RE = re.compile(r"'(?:\\.|''|[^'\\])*'|\"(?:\\.|\"\"|[^\"\\])*\"", re.DOTALL)

_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "CALL", "LOAD",
    "INTO", "HANDLER", "LOCK", "UNLOCK", "SET", "DO",
)

# Функции, которые читают файлы сервера, держат соединение или берут блокировки.
_FORBIDDEN_FUNCTIONS = (
    "LOAD_FILE", "SLEEP", "BENCHMARK", "GET_LOCK", "RELEASE_LOCK",
    "RELEASE_ALL_LOCKS", "IS_FREE_LOCK", "IS_USED_LOCK",
)


def strip_literals(query: str) -> str:
    return _LITERAL_RE.sub(" ", query)


def validate_sql_query(query: str) -> bool:
    """Return whether *query* is a single, read-only SELECT statement."""
    if not isinstance(query, str):
        return False

    stripped_query = query.strip()
    # Requiring a word boundary prevents values such as ``SELECTED`` from
    # being treated as a SELECT statement.  Comments before the statement are
    # deliberately not accepted, so a second statement cannot be hidden in a
    # comment/prefix accepted by the validator.
    if not re.match(r"\A(?:SELECT|WITH)\b", stripped_query, re.IGNORECASE):
        return False
    if ";" in stripped_query:
        return False

    # Ignore quoted literals while looking for write/DDL keywords.  A value
    # such as 'drop' is data, not an instruction, and must not make a valid
    # SELECT fail validation.
    without_literals = strip_literals(stripped_query)
    # Reject MySQL comments so dangerous tokens cannot be hidden between
    # keywords (for example, INTO/**/OUTFILE or FOR/**/UPDATE).
    if re.search(r"--|#|/\*|\*/", without_literals):
        return False

    if any(
        re.search(r"\b" + keyword + r"\b", without_literals, re.IGNORECASE)
        for keyword in _FORBIDDEN_KEYWORDS
    ):
        return False
    if any(
        re.search(r"\b" + name + r"\s*\(", without_literals, re.IGNORECASE)
        for name in _FORBIDDEN_FUNCTIONS
    ):
        return False

    # Системные схемы и служебные таблицы приложения.
    if re.search(r"\b(?:information_schema|performance_schema)\b|\b(?:mysql|sys)\s*\.",
                 without_literals, re.IGNORECASE):
        return False
    if any(re.search(r"\b" + table + r"\b", without_literals, re.IGNORECASE) for table in HIDDEN_TABLES):
        return False

    # MySQL permits SELECT forms that can still mutate state or write files.
    # Treat those as non-read-only even though they start with SELECT.
    unsafe_select_clauses = (
        r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b",
        r"\bFOR\s+UPDATE\b",
        r"\bFOR\s+SHARE\b",
        r"\bLOCK\s+IN\s+SHARE\s+MODE\b",
    )
    return not any(
        re.search(pattern, without_literals, re.IGNORECASE)
        for pattern in unsafe_select_clauses
    )


def to_jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8', errors='replace')
    return value


def run_readonly_query(query: str, max_rows: int = 50, timeout_ms: int = 8000) -> dict:
    """Выполнить проверенный SELECT внутри READ ONLY транзакции.

    Второй рубеж после валидатора: даже если запрос как-то прошёл проверку, MySQL сам
    откажет в любой записи внутри read-only транзакции, а MAX_EXECUTION_TIME не даст
    тяжёлому запросу повесить базу.
    """
    if not validate_sql_query(query):
        raise ValueError("Разрешён только один read-only SELECT без служебных таблиц")

    conn = mysql.connector.connect(**connection_config())
    try:
        cursor = conn.cursor()
        cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_ms)}")
        cursor.execute("START TRANSACTION READ ONLY")
        cursor.execute(query)
        columns = [column[0] for column in cursor.description or []]
        rows = cursor.fetchmany(max_rows + 1)
        # Дочитываем остаток порциями, иначе коннектор ругается на непрочитанный результат.
        while cursor.fetchmany(1000):
            pass
        conn.rollback()
        cursor.close()
    finally:
        conn.close()

    truncated = len(rows) > max_rows
    return {
        'columns': columns,
        'rows': [[to_jsonable(value) for value in row] for row in rows[:max_rows]],
        'truncated': truncated,
    }
