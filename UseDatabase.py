import mysql.connector
import socket
import os


class ConnectionError(Exception):
    """
    ошибка соеенения с БД
    """
    pass


class CredentialError(Exception):
    """
    ошибка ввода учетных данных БД,
    приводит к появлению ProgrammingError
    может возникать в ходе выполнения __enter__

    """
    pass


class SQLError(Exception):
    """
    ошибка SQL-запроса
    """
    pass


HOST_NAME = socket.gethostname()
print(f'HOST_NAME = {HOST_NAME}')

config = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'oilorder_admin'),
    'password': os.environ.get('DB_PASSWORD', 'oilpasswd'),
    'database': os.environ.get('DB_NAME', 'oilordersDB'),
    'charset': 'utf8'
}

class UseDatabase:

    def __init__(self, config: dict) -> None:
        self.configuration = config

    def __enter__(self) -> 'cursor':
        try:
            self.conn = mysql.connector.connect(**self.configuration)
            self.cursor = self.conn.cursor()
            return self.cursor
        except mysql.connector.errors.InterfaceError as err:
            raise ConnectionError(err)
        except mysql.connector.errors.ProgrammingError as err:
            raise ConnectionError(err)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # При ошибке откатываем: половина заказа без позиций хуже, чем ничего.
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.cursor.close()
        self.conn.close()
        """
        Если возникло ProgrammingError-возбудить SQLError.
        Остальные исключения пробрасываются как есть — с исходным текстом и трассировкой
        (пересоздание exc_type(exc_val) теряло сообщение у ошибок MySQL).
        """
        if exc_type is mysql.connector.errors.ProgrammingError:
            raise SQLError(exc_val)
        return False
