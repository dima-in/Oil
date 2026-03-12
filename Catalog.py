"""
Модуль для работы с каталогом масел.
Содержит функции для добавления данных прайс-листа и получения каталога.
"""
from Database import insert_price_list_items
from ExtractPDFPriceListTable import price_table_to_dict
from UseDatabase import UseDatabase, config


async def add_price_data_to_table() -> None:
    """
    Добавление данных из прайс-листа в таблицу базы данных.
    
    Функция читает CSV файл с прайс-листом, преобразует его в словарь
    и вставляет данные в таблицу price_list.
    """
    oil_dict = price_table_to_dict()  # TODO закончить функцию
    for name, prices in oil_dict.items():
        for volume, price in prices:
            # Вставка данных в таблицу
            insert_price_list_items(name, price, volume)


def get_oil_catalog() -> list:
    """
    Получение каталога масел из базы данных.
    
    Если таблица price_list пуста, автоматически заполняет её данными
    из прайс-листа.
    
    Returns:
        list: Список кортежей (название масла, объем, цена)
    """
    with UseDatabase(config) as cursor:
        _SQL_select_oil_prices = """SELECT oil_name, volume, price FROM price_list WHERE price > 0"""
        cursor.execute(_SQL_select_oil_prices)
        if cursor.fetchone() is None:
            add_price_data_to_table()
            # Повторное выполнение запроса после заполнения таблицы
            cursor.execute(_SQL_select_oil_prices)
        oil_price_list = cursor.fetchall()
        return oil_price_list
