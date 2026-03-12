

import csv
import os


def parse_price_list_pdf(pdf_path):
    """
    Парсит PDF прайс-лист и извлекает CSV файлы в папку tmp
    Затем читает CSV и возвращает данные
    """
    # Простая реализация - предполагаем, что PDF уже конвертирован в CSV
    # В будущем можно добавить pdfplumber для парсинга PDF
    csv_path = pdf_path.replace('.pdf', '.csv').replace('\\', '/')
    
    # Если CSV файл существует, читаем его
    if os.path.exists(csv_path):
        return read_csv_pricelist(csv_path)
    else:
        # Пытаемся найти стандартные файлы
        return price_table_to_dict()


def read_csv_pricelist(csv_path):
    """
    Читает CSV файл прайс-листа и возвращает словарь
    """
    oil_dict = {}
    with open(csv_path, encoding='utf-8') as table:
        volumes = table.readline().split(',')[1:]
        for product in table:
            product_list = product.split(',')
            prices = []
            for i, row in enumerate(product_list[1:]):
                name = product_list[0].strip('"')
                if row.endswith('""') or row.endswith('""\n'):
                    row = '0'
                prices.append([volumes[i].strip('\n').strip('"').replace('1 л', '1000').replace(' мл', ''), row.strip('\n').strip('"')])
            oil_dict[name] = prices
    return oil_dict


def price_table_to_dict():
    """
    конвертирует csv таблицу в словарь
    :return:
    """
    with open('tmp/price-page-1-table-1.csv', encoding='utf-8') as table:
        """
        читаем прайс-лист из csv файла
        получаем первую строку - header таблицы
        получаем объемы масел volumes
        """
        oil_dict = {}
        volumes = table.readline().split(',')[1:]
        for product in table:
            product_list = product.split(',')
            prices = []
            for i, row in enumerate(product_list[1:]):
                """
                получаем цены и их индексы,
                для сополставления с объемами масел
                игнорируем первый элемент - название масла
                """
                name = product_list[0].strip('"')
                if row.endswith('""') or row.endswith('""\n'):
                    row = '0'
                    #print(f'row 0 = {row}')
                prices.append([volumes[i].strip('\n').strip('"').replace('1 л', '1000').replace(' мл', ''), row.strip('\n').strip('"')])
            oil_dict[name] = prices
        print(f'oil_dict = {oil_dict}')
    return oil_dict

#price_table_to_dict()