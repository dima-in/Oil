from pathlib import Path

from Database import insert_price_list_items
from ExtractPDFPriceListTable import parse_price_list_file, price_table_to_dict
from UseDatabase import UseDatabase, config


def add_price_data_to_table():
    oil_dict = _load_default_pricelist()
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
        oil_price_list = cursor.fetchall()

    if oil_price_list:
        return oil_price_list

    add_price_data_to_table()

    with UseDatabase(config) as cursor:
        cursor.execute(_SQL_select_oil_prices)
        return cursor.fetchall()


def _load_default_pricelist():
    candidates = [
        Path('tmp/price-page-1-table-1.csv'),
        *Path('.').glob('*.xlsx'),
        *Path('.').glob('*.pdf'),
        *Path('.').glob('*.csv'),
    ]

    for candidate in candidates:
        if candidate.exists():
            data = parse_price_list_file(str(candidate))
            if data:
                return data

    return {}
