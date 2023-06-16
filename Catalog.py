from ExtractPDFPriceListTable import price_table_to_dict
from UseDatabase import UseDatabase, config


def create_catalog_table():
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS price_list
                        (id INT PRIMARY KEY AUTO_INCREMENT,
                        oil_name VARCHAR(100) NOT NULL,
                        volume INT NOT NULL,
                        price FLOAT NOT NULL
                        )""")


def add_price_row():
    with UseDatabase(config) as cursor:
        oil_dict = price_table_to_dict()  # TODO закончить функцию
        for name, prices in oil_dict.items():
            for volume, price in prices:

                if price or volume or price == '':
                    print(f'name, volume, price {name, volume.strip(" л"), price}')
                # Вставка данных в таблицу
                sql = "INSERT INTO price_list (oil_name, volume, price) VALUES (%s, %s, %s)"
                val = (name, volume, int(price))
                cursor.execute(sql, val)


def get_oil_catalog() -> list:
    """

    :rtype: object
    """
    with UseDatabase(config) as cursor:
        _SQL_select_oil_prices = """SELECT oil_name, volume, price FROM price_list WHERE price > 0"""
        cursor.execute(_SQL_select_oil_prices)
        if cursor.fetchone() is None:
            add_price_row()
        oil_price_list = cursor.fetchall()
        return oil_price_list
