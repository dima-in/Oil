from UseDatabase import UseDatabase, config

def create_oil_statuses():
    with UseDatabase(config) as cursor:

        cursor.execute("""CREATE TABLE IF NOT EXISTS order_statuses (
                        id INT PRIMARY KEY,
                        name VARCHAR(50) NOT NULL
                        )""")

        cursor.execute("""INSERT INTO order_statuses VALUES (0, 'новый')""")
        cursor.execute("""INSERT INTO order_statuses VALUES (1, 'получена предоплата')""")
        cursor.execute("""INSERT INTO order_statuses VALUES (2, 'готов к выдаче')""")
        cursor.execute("""INSERT INTO order_statuses VALUES (3, 'завершен')""")
        cursor.execute("""INSERT INTO order_statuses VALUES (4, 'отменен')""")
        cursor.execute("""INSERT INTO order_statuses VALUES (5, 'ожидает предоплаты')""")

def create_tables():
    with UseDatabase(config) as cursor:
        # Создание таблицы customers (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          name VARCHAR(50) NOT NULL,
                          surname VARCHAR(50) NOT NULL,
                          phone VARCHAR(20) NOT NULL,
                          address VARCHAR(20) NOT NULL
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


