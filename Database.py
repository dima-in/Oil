"""
Модуль для работы с базой данных заказов масел.
Содержит функции для создания таблиц, вставки и получения данных.
"""
from UseDatabase import UseDatabase, config


async def create_tables() -> None:
    """
    Создание таблиц базы данных если они не существуют.
    
    Создает следующие таблицы:
    - customers: данные клиентов
    - price_list: прайс-лист на масла
    - statuses_list: история статусов заказов
    - orders: заказы
    - order_details: детали заказов
    - order_statuses: справочник статусов
    """
    with UseDatabase(config) as cursor:
        # Создание таблицы customers (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(50) NOT NULL,
                            surname VARCHAR(50) NOT NULL,
                            phone VARCHAR(20) NOT NULL,
                            address VARCHAR(100) NOT NULL
                            )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS price_list
                            (id INT PRIMARY KEY AUTO_INCREMENT,
                            oil_name VARCHAR(100) NOT NULL,
                            volume INT NOT NULL,
                            price FLOAT NOT NULL
                            )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS statuses_list (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            order_id INT NOT NULL,
                            order_status INT NOT NULL,
                            name VARCHAR(50) NOT NULL,
                            datetime DATETIME
                            )""")

        # Создание таблицы orders (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          customer_id INT NOT NULL,
                          date DATE NOT NULL,
                          shipping_date DATE NOT NULL,
                          total_price FLOAT NOT NULL,
                          status INT NOT NULL,
                          FOREIGN KEY (status) REFERENCES order_statuses(id),
                          FOREIGN KEY (customer_id) REFERENCES customers(id)
                          )""")

        # Создание таблицы order_details (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS order_details (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          order_id INT NOT NULL,
                          oil_name VARCHAR(100) NOT NULL,
                          volume INT NOT NULL,
                          count INT NOT NULL,
                          price FLOAT NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS order_statuses (
                                id INT PRIMARY KEY,
                                name VARCHAR(50) NOT NULL
                                )""")


async def insert_statuses_to_database() -> None:
    """
    Вставка начальных статусов заказов в базу данных.
    
    Заполняет таблицу order_statuses стандартными статусами,
    если таблица пуста.
    """
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT COUNT(*) FROM order_statuses")
        result = cursor.fetchone()
        count = result[0]

        # Если таблица пуста, выполняем вставку записей
        if count == 0:
            # Используем множественную вставку вместо отдельных INSERT
            statuses = [
                (0, 'новый'),
                (1, 'получена предоплата'),
                (2, 'Avito доставка'),
                (3, 'Ozon'),
                (4, 'завершен'),
                (5, 'готов к выдаче'),
                (6, 'отменен'),
                (7, 'ожидает предоплаты')
            ]
            cursor.executemany(
                "INSERT INTO order_statuses (id, name) VALUES (%s, %s)",
                statuses
            )


def insert_price_list_items(name: str, price: float, volume: int) -> None:
    """
    Вставка позиции в прайс-лист, если такая запись еще не существует.
    
    Args:
        name: Название масла
        price: Цена
        volume: Объем в мл
    """
    with UseDatabase(config) as cursor:
        _SQL_insert_where_not_exists = """INSERT INTO price_list (oil_name, volume, price) SELECT %s, %s, %s
                    WHERE NOT EXISTS (SELECT 1 FROM price_list WHERE oil_name=%s AND volume=%s)"""
        val = (name, volume, int(price), name, volume)
        cursor.execute(_SQL_insert_where_not_exists, val)


async def save_status(order_id: int, status: int, status_name: str) -> None:
    """
    Сохранение статуса заказа в историю статусов.
    
    Args:
        order_id: ID заказа
        status: Код статуса
        status_name: Название статуса
    """
    with UseDatabase(config) as cursor:
        _SQL_insert_statuses_list = """INSERT INTO statuses_list (order_id, order_status, name) 
                    VALUES (%s, %s, %s)"""
        cursor.execute(_SQL_insert_statuses_list, (order_id, status, status_name))


async def get_status_name(status: int) -> str:
    """
    Получение названия статуса по его коду.
    
    Args:
        status: Код статуса
        
    Returns:
        str: Название статуса
    """
    with UseDatabase(config) as cursor:
        _SQL_select_status_name = """SELECT name FROM order_statuses WHERE id = %s"""
        cursor.execute(_SQL_select_status_name, (status,))
        status_name = cursor.fetchone()[0]
        return status_name


async def save_order_details(order_id: int, product) -> None:
    """
    Сохранение деталей заказа (позиции товара).
    
    Args:
        order_id: ID заказа
        product: Объект OrderItem с данными о товаре
    """
    with UseDatabase(config) as cursor:
        _SQL_save_order_details = """INSERT INTO order_details (order_id, oil_name, volume, count, price)
                VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order_details,
                       (order_id, product.oil_name, product.volume, product.count, product.price))


async def save_order(customer_id: int, date, order, shipping_date, status: int) -> int:
    """
    Сохранение заказа в базу данных.
    
    Args:
        customer_id: ID клиента
        date: Дата создания заказа
        order: Объект заказа OilOrder
        shipping_date: Дата доставки
        status: Код статуса заказа
        
    Returns:
        int: ID созданного заказа
    """
    with UseDatabase(config) as cursor:
        _SQL_save_order = """INSERT INTO orders (customer_id, date, shipping_date, total_price, status) 
                                        VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order, (customer_id, date, shipping_date, order.calculate_total_price(), status))
        order_id = cursor.lastrowid  # получаем ID заказа
        return order_id


async def save_customer(address: str, name: str, phone: str, surname: str) -> int:
    """
    Сохранение нового клиента в базу данных.
    
    Args:
        address: Адрес доставки
        name: Имя клиента
        phone: Номер телефона
        surname: Фамилия клиента
        
    Returns:
        int: ID созданного клиента
    """
    with UseDatabase(config) as cursor:
        _SQL_create_customer = """INSERT INTO customers (name, surname, phone, address)
                        VALUES (%s, %s, %s, %s)"""
        cursor.execute(_SQL_create_customer, (name, surname, phone, address))
        customer_id = cursor.lastrowid  # получаем ID нового клиента
        return customer_id


async def get_customer_by_phone(phone: str) -> tuple:
    """
    Поиск клиента по номеру телефона.
    
    Args:
        phone: Номер телефона для поиска
        
    Returns:
        tuple: Кортеж с данными клиента или None, если клиент не найден
    """
    with UseDatabase(config) as cursor:
        _SQL_select_customer = """ SELECT id, name, surname, phone FROM customers 
                            WHERE phone=%s"""
        cursor.execute(_SQL_select_customer, (phone,))
        existing_customer = cursor.fetchone()  # получаем следующую строку из запроса
        return existing_customer


def select_all_orders() -> list:
    """
    Получение всех заказов с информацией о клиентах и деталях.
    
    Returns:
        list: Список кортежей с данными заказов
    """
    with UseDatabase(config) as cursor:
        _SQL_select_all = """SELECT * FROM orders 
                                JOIN customers ON orders.customer_id = customers.id
                                JOIN order_details ON orders.id = order_details.order_id
                                JOIN statuses_list ON orders.id = statuses_list.order_id;
                                """
        cursor.execute(_SQL_select_all)
        order = cursor.fetchall()
        return order


def delete_order_by_id(order_id_to_delete: int) -> None:
    """
    Удаление заказа по ID (включая детали заказа).
    
    Args:
        order_id_to_delete: ID заказа для удаления
    """
    with UseDatabase(config) as cursor:
        _SQL_delete_from_order_details = """DELETE FROM order_details WHERE order_id = %s;"""
        _SQL_delete_from_orders = """DELETE FROM orders WHERE id = %s;"""
        cursor.execute(_SQL_delete_from_order_details, (order_id_to_delete, ))
        cursor.execute(_SQL_delete_from_orders, (order_id_to_delete, ))


async def get_all_prices() -> list:
    """
    Получение всего прайс-листа.
    
    Returns:
        list: Список кортежей с данными о товарах (id, oil_name, volume, price)
    """
    with UseDatabase(config) as cursor:
        _SQL_select_all = """SELECT id, oil_name, volume, price FROM price_list ORDER BY oil_name, volume"""
        cursor.execute(_SQL_select_all)
        return cursor.fetchall()


async def get_price_by_id(item_id: int) -> tuple:
    """
    Получение позиции прайс-листа по ID.
    
    Args:
        item_id: ID позиции в прайс-листе
        
    Returns:
        tuple: Кортеж с данными (id, oil_name, volume, price) или None
    """
    with UseDatabase(config) as cursor:
        _SQL_select = """SELECT id, oil_name, volume, price FROM price_list WHERE id = %s"""
        cursor.execute(_SQL_select, (item_id,))
        return cursor.fetchone()


async def update_price(item_id: int, price: float) -> bool:
    """
    Обновление цены в прайс-листе.
    
    Args:
        item_id: ID позиции в прайс-листе
        price: Новая цена
        
    Returns:
        bool: True, если обновлено, False если позиция не найдена
    """
    with UseDatabase(config) as cursor:
        _SQL_update = """UPDATE price_list SET price = %s WHERE id = %s"""
        cursor.execute(_SQL_update, (price, item_id))
        return cursor.rowcount > 0


async def add_price_item(oil_name: str, volume: int, price: float) -> int:
    """
    Добавление новой позиции в прайс-лист.
    
    Args:
        oil_name: Название масла
        volume: Объем в мл
        price: Цена
        
    Returns:
        int: ID созданной записи
    """
    with UseDatabase(config) as cursor:
        _SQL_insert = """INSERT INTO price_list (oil_name, volume, price) VALUES (%s, %s, %s)"""
        cursor.execute(_SQL_insert, (oil_name, volume, price))
        return cursor.lastrowid


async def delete_price_item(item_id: int) -> bool:
    """
    Удаление позиции из прайс-листа.
    
    Args:
        item_id: ID позиции для удаления
        
    Returns:
        bool: True, если удалено, False если позиция не найдена
    """
    with UseDatabase(config) as cursor:
        _SQL_delete = """DELETE FROM price_list WHERE id = %s"""
        cursor.execute(_SQL_delete, (item_id,))
        return cursor.rowcount > 0


def is_id_exist(order_id: int) -> bool:
    """
    Проверка существования заказа по ID.
    
    Args:
        order_id: ID заказа для проверки
        
    Returns:
        bool: True, если заказ существует, иначе False
    """
    with UseDatabase(config) as cursor:
        _SQL_select_id = """SELECT id FROM orders WHERE id = %s;"""
        cursor.execute(_SQL_select_id, (order_id, ))
        result = cursor.fetchone()
        if result:
            return True
        else:
            return False
