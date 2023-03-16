from openpyxl import reader
import camelot
import ghostscript
from camelot.core import TableList


def extract_price() -> list:
    """
    получает значения цен на продукты из PDF файла
    :return: первая таблица: прайс-лист масла
    """
    tables = camelot.read_pdf('Temp/прайс 30.01.23.pdf')
    all_table_data = []
    for table in tables:
        table_data = table.data
        all_table_data.append(table_data)
    return all_table_data[0]


#extract_price()

