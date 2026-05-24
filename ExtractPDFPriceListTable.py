import csv
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz


SPREADSHEET_NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'office': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def parse_price_list_pdf(file_path):
    return parse_price_list_file(file_path)


def parse_price_list_file(file_path):
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == '.pdf':
        csv_path = str(path).replace('.pdf', '.csv').replace('\\', '/')
        if os.path.exists(csv_path):
            return read_csv_pricelist(csv_path)
        return read_pdf_pricelist(str(path))

    if extension == '.csv':
        return read_csv_pricelist(str(path))

    if extension == '.xlsx':
        return read_xlsx_pricelist(str(path))

    raise ValueError('Поддерживаются только PDF, CSV и XLSX файлы')


def read_pdf_pricelist(pdf_path):
    doc = fitz.open(pdf_path)
    words = []
    for page in doc:
        words.extend(page.get_text('words'))

    lines = _group_words_by_line(words)
    header = _find_header_line(lines)
    if not header:
        return {}

    volume_columns = _extract_volume_columns(header)
    if not volume_columns:
        return {}

    oil_dict = {}
    for line in lines[lines.index(header) + 1:]:
        name_tokens = []
        prices = {}

        for word in line:
            text = _cell_text(word[4])
            if not text:
                continue

            price = _parse_price(text)
            volume = _find_volume_by_range(word[0], volume_columns)
            if price and volume:
                prices[volume] = price
            else:
                name_tokens.append(text)

        oil_name = _normalize_oil_name(' '.join(name_tokens))
        if oil_name and prices:
            oil_dict[oil_name] = _ordered_prices(volume_columns, prices)

    return oil_dict


def read_csv_pricelist(csv_path):
    oil_dict = {}
    with open(csv_path, encoding='utf-8-sig', newline='') as table:
        rows = list(csv.reader(table))

    if not rows:
        return oil_dict

    header = rows[0]
    name_column, volume_columns = _extract_table_columns(header)
    if name_column is None or not volume_columns:
        return oil_dict

    for row in rows[1:]:
        if name_column >= len(row):
            continue

        oil_name = _normalize_oil_name(row[name_column])
        if not oil_name:
            continue

        prices = {}
        for volume, column_index in volume_columns:
            if column_index < len(row):
                price = _parse_price(row[column_index])
                if price:
                    prices[volume] = price

        if prices:
            oil_dict[oil_name] = [[volume, prices[volume]] for volume, _ in volume_columns if volume in prices]

    return oil_dict


def read_xlsx_pricelist(xlsx_path):
    rows = _read_xlsx_rows(xlsx_path)
    if not rows:
        return {}

    header_index = None
    name_column = None
    volume_columns = []

    for index, row in enumerate(rows[:30]):
        name_column, volume_columns = _extract_table_columns(row)
        if name_column is not None and volume_columns:
            header_index = index
            break

    if header_index is None:
        return {}

    oil_dict = {}
    data_started = False
    for row in rows[header_index + 1:]:
        if all(not _cell_text(value) for value in row):
            if data_started:
                break
            continue

        if name_column >= len(row):
            continue

        oil_name = _normalize_oil_name(row[name_column])
        if not oil_name:
            continue

        prices = {}
        for volume, column_index in volume_columns:
            if column_index < len(row):
                price = _parse_price(row[column_index])
                if price:
                    prices[volume] = price

        if prices:
            oil_dict[oil_name] = [[volume, prices[volume]] for volume, _ in volume_columns if volume in prices]
            data_started = True

    return oil_dict


def price_table_to_dict():
    return read_csv_pricelist('tmp/price-page-1-table-1.csv')


def _group_words_by_line(words, tolerance=2.5):
    sorted_words = sorted(words, key=lambda item: (round(item[1], 1), item[0]))
    lines = []

    for word in sorted_words:
        if not lines or abs(lines[-1][0][1] - word[1]) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)

    return [sorted(line, key=lambda item: item[0]) for line in lines]


def _find_header_line(lines):
    for line in lines[:10]:
        text = ' '.join(_cell_text(word[4]).lower() for word in line)
        if 'масло' in text and any(_parse_volume_from_tokens(word[4]) for word in line):
            return line
    return lines[0] if lines else None


def _extract_volume_columns(header_words):
    columns = []
    index = 0

    while index < len(header_words):
        current = header_words[index]
        current_text = _cell_text(current[4])
        next_word = header_words[index + 1] if index + 1 < len(header_words) else None
        next_text = _cell_text(next_word[4]) if next_word else ''

        volume = _parse_volume_from_tokens(current_text, next_text)
        if volume:
            columns.append((volume, current[0]))
            index += 2 if next_text else 1
            continue

        index += 1

    return sorted(columns, key=lambda item: item[1])


def _find_volume_by_range(word_x, volume_columns):
    for index, (volume, column_x) in enumerate(volume_columns):
        next_x = volume_columns[index + 1][1] if index + 1 < len(volume_columns) else None
        if word_x >= column_x and (next_x is None or word_x < next_x):
            return volume
    return None


def _ordered_prices(volume_columns, prices):
    return [[volume, prices[volume]] for volume, _ in volume_columns if volume in prices]


def _extract_table_columns(header_row):
    name_column = None
    volume_columns = []

    for index, value in enumerate(header_row):
        text = _cell_text(value).lower()
        if text in {'масло', 'наименование', 'название'}:
            name_column = index
            continue

        volume = _parse_volume_header(text)
        if volume:
            volume_columns.append((volume, index))

    if name_column is None and header_row:
        name_column = 0

    return name_column, volume_columns


def _read_xlsx_rows(xlsx_path):
    with zipfile.ZipFile(xlsx_path) as archive:
        names = archive.namelist()
        shared_strings = _read_shared_strings(archive, names)
        sheet_path = _find_pricelist_sheet_path(archive)
        if not sheet_path:
            return []

        root = ET.fromstring(archive.read(sheet_path))
        rows = []
        for row in root.findall('.//main:sheetData/main:row', SPREADSHEET_NS):
            cells = {}
            max_column = 0
            for cell in row.findall('main:c', SPREADSHEET_NS):
                column_index = _column_index(cell.attrib.get('r', 'A1'))
                max_column = max(max_column, column_index)
                cells[column_index] = _xlsx_cell_value(cell, shared_strings)

            rows.append([cells.get(column, '') for column in range(1, max_column + 1)])

        return rows


def _read_shared_strings(archive, names):
    if 'xl/sharedStrings.xml' not in names:
        return []

    root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    strings = []
    for item in root.findall('main:si', SPREADSHEET_NS):
        strings.append(''.join(text.text or '' for text in item.findall('.//main:t', SPREADSHEET_NS)))
    return strings


def _find_pricelist_sheet_path(archive):
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    relation_targets = {
        relation.attrib['Id']: relation.attrib['Target']
        for relation in relationships.findall('rel:Relationship', SPREADSHEET_NS)
    }

    fallback = None
    for sheet in workbook.findall('main:sheets/main:sheet', SPREADSHEET_NS):
        sheet_name = sheet.attrib.get('name', '').lower()
        relation_id = sheet.attrib.get(f'{{{SPREADSHEET_NS["office"]}}}id')
        target = relation_targets.get(relation_id)
        if not target:
            continue

        path = 'xl/' + target.lstrip('/')
        if fallback is None:
            fallback = path
        if 'прайс' in sheet_name:
            return path

    return fallback


def _xlsx_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get('t')

    if cell_type == 'inlineStr':
        return ''.join(text.text or '' for text in cell.findall('.//main:t', SPREADSHEET_NS))

    value = cell.find('main:v', SPREADSHEET_NS)
    if value is None or value.text is None:
        return ''

    raw_value = value.text
    if cell_type == 's':
        return shared_strings[int(raw_value)] if raw_value.isdigit() else ''

    return raw_value


def _column_index(cell_reference):
    letters = ''.join(character for character in cell_reference if character.isalpha()).upper()
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord('A') + 1
    return index


def _cell_text(value):
    return str(value or '').strip().replace('\xa0', ' ')


def _normalize_oil_name(value):
    return re.sub(r'\s+', ' ', _cell_text(value)).strip()


def _parse_price(value):
    text = _cell_text(value)
    if not text:
        return None

    match = re.search(r'\d+(?:[\s.,]\d+)*', text)
    if not match:
        return None

    number = match.group(0).replace(' ', '').replace(',', '.')
    try:
        parsed = float(number)
    except ValueError:
        return None

    if parsed <= 0:
        return None

    return str(int(round(parsed)))


def _parse_volume_header(value):
    text = _cell_text(value).lower()
    match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(мл|ml|л|l)', text)
    if not match:
        return None

    amount = float(match.group(1).replace(',', '.'))
    unit = match.group(2)
    volume = amount * 1000 if unit in {'л', 'l'} else amount
    return str(int(round(volume)))


def _parse_volume_from_tokens(current_text, next_text=''):
    joined = f'{_cell_text(current_text)} {_cell_text(next_text)}'.strip()
    return _parse_volume_header(joined) or _parse_volume_header(_cell_text(current_text))
