"""
Модуль для подключения и работы с базой данных MySQL.
Содержит класс UseDatabase для управления контекстом подключения
и пользовательские исключения для обработки ошибок.
"""
import mysql.connector
import socket


class ConnectionError(Exception):
    """
    Ошибка соединения с базой данных.
    
    Возникает при проблемах с сетевым подключением или
    недоступности сервера базы данных.
    """
    pass


class CredentialError(Exception):
    """
    Ошибка ввода учетных данных базы данных.
    
    Приводит к появлению ProgrammingError.
    Может возникать в ходе выполнения метода __enter__.
    """
    pass


class SQLError(Exception):
    """
    Ошибка SQL-запроса.
    
    Возникает при некорректном синтаксисе SQL
    или ошибках выполнения запроса.
    """
    pass


HOST_NAME = socket.gethostname()
print(f'HOST_NAME = {HOST_NAME}')

config = {
    'host': '127.0.0.1' if HOST_NAME == 'DESKTOP-E6O7AMM' else 'mysql_DB2',
    'user': 'oilorder_admin',
    'password': 'oilpasswd',
    'database': 'oilordersDB',
    'charset': 'utf8'
}

class UseDatabase:
    """
    Класс для управления контекстом подключения к базе данных.
    
    Используется как менеджер контекста (with statement) для
    автоматического открытия и закрытия соединения с БД.
    
    Example:
        with UseDatabase(config) as cursor:
            cursor.execute("SELECT * FROM table")
    """

    def __init__(self, config: dict) -> None:
        """
        Инициализация менеджера контекста базы данных.
        
        Args:
            config: Словарь с параметрами подключения к БД
                   (host, user, password, database, charset)
        """
        self.configuration = config

    def __enter__(self) -> 'cursor':
        """
        Вход в контекст: создание соединения с базой данных.
        
        Returns:
            cursor: Объект курсора для выполнения SQL-запросов
            
        Raises:
            ConnectionError: При ошибках подключения или неверных учетных данных
        """
        try:
            self.conn = mysql.connector.connect(**self.configuration)
            self.cursor = self.conn.cursor()
            return self.cursor
        except mysql.connector.errors.InterfaceError as err:
            raise ConnectionError(err)
        except mysql.connector.errors.ProgrammingError as err:
            raise CredentialError(err)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Выход из контекста: фиксация транзакции и закрытие соединения.
        
        Args:
            exc_type: Тип возникшего исключения (если было)
            exc_val: Значение исключения (если было)
            exc_tb: Трассировка исключения (если было)
            
        Raises:
            SQLError: При возникновении ProgrammingError во время выполнения
            exc_type: Другие исключения пробрасываются дальше
        """
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
        """
        Если возникло ProgrammingError - возбудить SQLError.
        Возбудить исключение после выполнения 
        кода метода __exit__ 
        """
        if exc_type is mysql.connector.errors.ProgrammingError:
            raise SQLError(exc_val)
        elif exc_type:
            raise exc_type(exc_val)
