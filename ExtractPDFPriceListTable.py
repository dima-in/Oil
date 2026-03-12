
"""
Модуль для извлечения данных о ценах из PDF прайс-листа.
Содержит функцию конвертации CSV таблицы в словарь.
"""


def price_table_to_dict() -> dict:
    """
    Конвертирует CSV таблицу с прайс-листом в словарь.
    
    Читает файл tmp/price-page-1-table-1.csv и преобразует его в словарь,
    где ключи - названия масел, а значения - списки [объем, цена].
    
    Returns:
        dict: Словарь вида {название_масла: [[объем1, цена1], [объем2, цена2], ...]}
    """
    with open('tmp/price-page-1-table-1.csv', encoding='utf-8') as table:
        """
        Читаем прайс-лист из csv файла
        Получаем первую строку - header таблицы
        Получаем объемы масел volumes
        """
        oil_dict = {}
        volumes = table.readline().split(',')[1:]
        for product in table:
            product_list = product.split(',')
            prices = []
            for i, row in enumerate(product_list[1:]):
                """
                Получаем цены и их индексы, 
                для сопоставления с объемами масел 
                Игнорируем первый элемент - название масла
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