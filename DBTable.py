from UseDatabase import UseDatabase, config


def create_table():
    with UseDatabase(config) as cursor:
        # Создание таблицы customers (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          name VARCHAR(50) NOT NULL,
                          surname VARCHAR(50) NOT NULL,
                          phone VARCHAR(20) NOT NULL,
                          address VARCHAR(20) NOT NULL
                          )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS order_statuses (
                                id INT PRIMARY KEY,
                                name VARCHAR(50) NOT NULL
                                )""")

        cursor.execute("""INSERT INTO order_statuses VALUES (0, 'new')
                                """)
        cursor.execute("""INSERT INTO order_statuses VALUES (1, 'in process')
                                """)
        cursor.execute("""INSERT INTO order_statuses VALUES (2, 'done')
                                """)
        cursor.execute("""INSERT INTO order_statuses VALUES (3, 'неоплачен')
                                """)
        cursor.execute("""INSERT INTO order_statuses VALUES (4, 'получена предоплата')
                                """)
        cursor.execute("""INSERT INTO order_statuses VALUES (2, 'оптачен')
                                """)

        cursor.execute("""CREATE TABLE IF NOT EXISTS statuses_list (
                                        id INT PRIMARY KEY,
                                        order_id INT NOT NULL,
                                        order_status INT NOT NULL,
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


#create_table()
