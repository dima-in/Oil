import csv
import os

import fitz


def parse_price_list_pdf(pdf_path):
    """
    Разбирает PDF прайс-лист в словарь формата:
    {
        "подсолнечное": [["500", "750"], ["1000", "1350"]],
    }
    """
    csv_path = pdf_path.replace('.pdf', '.csv').replace('\\', '/')
    if os.path.exists(csv_path):
        return read_csv_pricelist(csv_path)
    return read_pdf_pricelist(pdf_path)


def read_pdf_pricelist(pdf_path):
    doc = fitz.open(pdf_path)
    words = []
    for page in doc:
        words.extend(page.get_text('words'))

    lines = _group_words_by_line(words)
    if not lines:
        return {}

    volume_columns = _extract_volume_columns(lines[0])
    oil_dict = {}

    for line in lines[1:]:
        name_tokens = []
        prices = {}

        for word in line:
            text = word[4].strip()
            if not text:
                continue

            if text.isdigit():
                volume = _find_nearest_volume(word[0], volume_columns)
                if volume:
                    prices[volume] = text
            else:
                name_tokens.append(text)

        oil_name = ' '.join(name_tokens).strip()
        if not oil_name or not prices:
            continue

        oil_dict[oil_name] = [[volume, price] for volume, price in volume_columns if volume in prices for price in [prices[volume]]]

    return oil_dict


def _group_words_by_line(words, tolerance=2.5):
    sorted_words = sorted(words, key=lambda item: (round(item[1], 1), item[0]))
    lines = []

    for word in sorted_words:
        if not lines or abs(lines[-1][0][1] - word[1]) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)

    return [sorted(line, key=lambda item: item[0]) for line in lines]


def _extract_volume_columns(header_words):
    columns = []
    index = 1

    while index < len(header_words):
        current = header_words[index]
        text = current[4].strip()
        next_word = header_words[index + 1] if index + 1 < len(header_words) else None

        if text.isdigit() and next_word and next_word[4].strip() in {'мл', 'л'}:
            unit = next_word[4].strip()
            volume = int(text) * 1000 if unit == 'л' else int(text)
            columns.append((str(volume), current[0]))
            index += 2
            continue

        index += 1

    return columns


def _find_nearest_volume(word_x, volume_columns):
    nearest_volume = None
    nearest_distance = None

    for volume, column_x in volume_columns:
        distance = abs(word_x - column_x)
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_volume = volume

    return nearest_volume


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
    Конвертирует csv таблицу из tmp в словарь
    """
    with open('tmp/price-page-1-table-1.csv', encoding='utf-8') as table:
        oil_dict = {}
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
