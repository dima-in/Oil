from ExtractPDFPriceListTable import extract_price

from UseDatabase import UseDatabase, config


def create_price_lict_table():
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS price_list
                        (id INT PRIMARY KEY AUTO_INCREMENT,
                        oil_name VARCHAR(100) NOT NULL,
                        volume INT NOT NULL,
                        price FLOAT NOT NULL
                        )""")


create_price_lict_table()


def price_table_to_dict():
    """

    :return:
    """
    table = extract_price()
    for product in table:
        oil_dict = {}
        for row in product[1:]:
            name = row[0]
            volumes = [50, 100, 180, 250, 500, 1000]
            prices = []
            for i, value in enumerate(row[1:]):
                if value == '':
                    prices.append(0)
                else:
                    prices.append(int(value))
            oil_dict[name] = dict(zip(volumes, prices))
            return oil_dict


def add_price_row():
    with UseDatabase(config) as cursor:
        oil_dict = price_table_to_dict()
        for name, prices in oil_dict.items():
            for volume, price in prices.items():
                # Вставка данных в таблицу
                sql = "INSERT INTO price_list (oil_name, volume, price) VALUES (%s, %s, %s)"
                val = (name, volume, price)
                cursor.execute(sql, val)


# add_price_row()


def get_oil_prices() -> list:
    with UseDatabase(config) as cursor:
        _SQL_select_oil_prices = """SELECT oil_name, volume, price FROM price_list WHERE price > 0"""
        cursor.execute(_SQL_select_oil_prices)
        oil_price_list = cursor.fetchall()
        return oil_price_list
