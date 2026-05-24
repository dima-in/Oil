from Database import insert_price_list_items
from ExtractPDFPriceListTable import parse_price_list_file, price_table_to_dict
from UseDatabase import UseDatabase, config


async def add_price_data_to_table():
    oil_dict = price_table_to_dict()
    for name, prices in oil_dict.items():
        for volume, price in prices:
            insert_price_list_items(name, price, volume)


def load_pricelist_from_pdf(file_path):
    """Загрузка прайс-листа из PDF, CSV или XLSX файла."""
    oil_dict = parse_price_list_file(file_path)
    loaded_count = 0
    for name, prices in oil_dict.items():
        for volume, price in prices:
            if price and float(price) > 0:
                insert_price_list_items(name, price, volume)
                loaded_count += 1
    return loaded_count


def get_oil_catalog() -> list:
    with UseDatabase(config) as cursor:
        _SQL_select_oil_prices = """SELECT oil_name, volume, price FROM price_list WHERE price > 0"""
        cursor.execute(_SQL_select_oil_prices)
        if cursor.fetchone() is None:
            add_price_data_to_table()
        oil_price_list = cursor.fetchall()
        return oil_price_list
