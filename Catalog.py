from Database import insert_price_list_items
from ExtractPDFPriceListTable import price_table_to_dict
from UseDatabase import UseDatabase, config


async def add_price_data_to_table():
    oil_dict = price_table_to_dict()  # TODO закончить функцию
    for name, prices in oil_dict.items():
        for volume, price in prices:
            # Вставка данных в таблицу
            insert_price_list_items(name, price, volume)


def get_oil_catalog() -> list:
    with UseDatabase(config) as cursor:
        _SQL_select_oil_prices = """SELECT oil_name, volume, price FROM price_list WHERE price > 0"""
        cursor.execute(_SQL_select_oil_prices)
        if cursor.fetchone() is None:
            add_price_data_to_table()
        oil_price_list = cursor.fetchall()
        return oil_price_list
