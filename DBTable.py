from UseDatabase import UseDatabase, config


def create_table():

    with UseDatabase(config) as cursor:
        # Создание таблицы orders (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          date DATE NOT NULL,
                          shipping_date DATE NOT NULL,
                          total_price FLOAT NOT NULL
                          )""")

        # Создание таблицы order_details (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS order_details (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          order_id INT NOT NULL,
                          oil_name VARCHAR(100) NOT NULL,
                          volume INT NOT NULL,
                          price FLOAT NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

        # Создание таблицы customers (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          order_id INT NOT NULL,
                          name VARCHAR(50) NOT NULL,
                          surname VARCHAR(50) NOT NULL,
                          phone VARCHAR(20) NOT NULL,
                          address VARCHAR(20) NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

create_table()
