from UseDatabase import UseDatabase


def create_table():
    config = {
        'host': '127.0.0.1',
        'user': 'oilorder_admin',
        'password': 'oilpasswd',
        'database': 'OilOrders'
    }
    with UseDatabase(config) as cursor:
        # Создание таблицы orders (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          customer_id INTEGER NOT NULL,
                          data DATE NOT NULL,
                          shipping_date DATE NOT NULL,
                          total_price REAL NOT NULL,
                          FOREIGN KEY (customer_id) REFERENCES customer(id)
                          )""")

        # Создание таблицы order_details (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS order_details (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          order_id INTEGER NOT NULL,
                          oil_name TEXT NOT NULL,
                          volume INTEGER NOT NULL,
                          price REAL NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

        # Создание таблицы customers (если она не существует)
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          order_id INTEGER NOT NULL,
                          name TEXT NOT NULL,
                          sur_name TEXT NOT NULL,
                          phone TEXT NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

create_table()
