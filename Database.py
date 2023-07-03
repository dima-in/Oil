from UseDatabase import UseDatabase, config



async def create_tables():
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


async def insert_statuses_to_database():
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT COUNT(*) FROM order_statuses")
        result = cursor.fetchone()
        count = result[0]

        # Если таблица пуста, выполняем вставку записей
        if count == 0:
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (0, 'новый')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (1, 'получена предоплата')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (2, 'Avito доставка')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (3, 'Ozon')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (4, 'завершен')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (5, 'готов к выдаче')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (6, 'отменен')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (7, 'ожидает предоплаты')""")


def insert_price_list_items(name, price, volume):
    with UseDatabase(config) as cursor:
        _SQL_insert_where_not_exists = """INSERT INTO price_list (oil_name, volume, price) SELECT %s, %s, %s
                    FROM DUAL
                    WHERE NOT EXISTS (SELECT 1 FROM price_list LIMIT 1)"""
        val = (name, volume, int(price))
        cursor.execute(_SQL_insert_where_not_exists, val)


async def save_status(order_id, status, status_name):
    with UseDatabase(config) as cursor:
        _SQL_insert_statuses_list = """INSERT INTO statuses_list (order_id, order_status, name) 
                    VALUES (%s, %s, %s)"""
        cursor.execute(_SQL_insert_statuses_list, (order_id, status, status_name))


async def get_status_name(status):
    with UseDatabase(config) as cursor:
        _SQL_select_status_name = """SELECT name FROM order_statuses WHERE id = %s"""
        cursor.execute(_SQL_select_status_name, (status,))
        status_name = cursor.fetchone()[0]
        return status_name


async def save_order_details(order_id, product):
    with UseDatabase(config) as cursor:
        _SQL_save_order_details = """INSERT INTO order_details (order_id, oil_name, volume, count, price)
                VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order_details,
                       (order_id, product.oil_name, product.volume, product.count, product.price))


async def save_order(customer_id, date, order, shipping_date, status):
    with UseDatabase(config) as cursor:
        _SQL_save_order = """INSERT INTO orders (customer_id, date, shipping_date, total_price, status) 
                                        VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order, (customer_id, date, shipping_date, order.calculate_total_price(), status))
        order_id = cursor.lastrowid  # получаем ID заказа
        return order_id


async def save_customer(address, name, phone, surname):
    with UseDatabase(config) as cursor:
        _SQL_create_customer = """INSERT INTO customers (name, surname, phone, address)
                        VALUES (%s, %s, %s, %s)"""
        cursor.execute(_SQL_create_customer, (name, surname, phone, address))
        customer_id = cursor.lastrowid  # получаем ID нового клиента
        return customer_id


async def get_customer_by_phone(phone):
    with UseDatabase(config) as cursor:
        _SQL_select_customer = """ SELECT id, name, surname, phone FROM customers 
                            WHERE phone=%s"""
        cursor.execute(_SQL_select_customer, (phone,))
        existing_customer = cursor.fetchone()  # получаем следующую строку из запроса
        return existing_customer


def select_all_orders():
    with UseDatabase(config) as cursor:
        _SQL_select_all = """SELECT * FROM orders 
                                JOIN customers ON orders.customer_id = customers.id
                                JOIN order_details ON orders.id = order_details.order_id
                                JOIN statuses_list ON orders.id = statuses_list.order_id;
                                """
        cursor.execute(_SQL_select_all)
        order = cursor.fetchall()
        return order
