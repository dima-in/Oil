



def price_table_to_dict():
    """
    конвертирует csv таблицу в словарь
    :return:
    """
    with open('tmp/price-page-1-table-1.csv') as table:
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
    return oil_dict

price_table_to_dict()