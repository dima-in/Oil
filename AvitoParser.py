"""
Модуль для парсинга цен с Avito.
Содержит функции для получения актуальных цен на масла с площадки Avito.
"""
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from aiohttp import ClientSession
from bs4 import BeautifulSoup


# Базовый URL для поиска масел на Avito
AVITO_SEARCH_URL = "https://www.avito.ru"


async def fetch_page(session: ClientSession, url: str) -> Optional[str]:
    """
    Получение HTML содержимого страницы.
    
    Args:
        session: Сессия aiohttp
        url: URL страницы
        
    Returns:
        str: HTML содержимое или None при ошибке
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                return await response.text()
            else:
                print(f"Ошибка при получении страницы {url}: статус {response.status}")
                return None
    except Exception as e:
        print(f"Исключение при получении страницы {url}: {e}")
        return None


def parse_price_from_text(text: str) -> Optional[int]:
    """
    Извлечение цены из текста.
    
    Args:
        text: Текст, содержащий цену
        
    Returns:
        int: Цена в рублях или None
    """
    # Удаляем лишние символы и ищем число
    cleaned = re.sub(r'[^\d]', '', text)
    if cleaned:
        return int(cleaned)
    return None


def extract_volume_from_title(title: str) -> Optional[int]:
    """
    Извлечение объема из названия товара.
    
    Args:
        title: Название товара
        
    Returns:
        int: Объем в мл или None
    """
    # Ищем паттерны типа "4л", "4 л", "4000мл", "4000 мл"
    patterns = [
        r'(\d+)\s*[лЛ]',  # литры
        r'(\d{4,})\s*[мМ][лЛ]',  # миллилитры (4 цифры и более)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            value = int(match.group(1))
            # Конвертируем литры в миллилитры
            if 'л' in pattern.lower():
                return value * 1000
            return value
    
    return None


async def search_avito_for_oil(session: ClientSession, oil_name: str, target_volume: int) -> List[Dict]:
    """
    Поиск масла на Avito по названию и объему.
    
    Args:
        session: Сессия aiohttp
        oil_name: Название масла для поиска
        target_volume: Целевой объем в мл
        
    Returns:
        List[Dict]: Список найденных предложений с ценами
    """
    # Формируем поисковый запрос
    search_query = f"{oil_name} {target_volume // 1000}л" if target_volume >= 1000 else f"{oil_name} {target_volume}мл"
    search_url = f"{AVITO_SEARCH_URL}/all?q={search_query.replace(' ', '+')}"
    
    html = await fetch_page(session, search_url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    # Ищем объявления (структура может меняться, это примерный парсинг)
    # Avito часто меняет верстку, поэтому используем несколько стратегий
    items = soup.find_all('div', {'data-item-id': True}) or \
            soup.find_all('article', {'data-automation': True}) or \
            soup.find_all('div', class_=lambda x: x and 'item' in x.lower())
    
    for item in items[:10]:  # Ограничиваем первыми 10 результатами
        try:
            # Извлекаем название
            title_elem = item.find(['a', 'h3', 'div'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()))
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            
            # Проверяем соответствие объема
            volume = extract_volume_from_title(title)
            if not volume or abs(volume - target_volume) > 500:  # Допускаем небольшую погрешность
                continue
            
            # Извлекаем цену
            price_elem = item.find(['div', 'span'], class_=lambda x: x and ('price' in x.lower() or 'cost' in x.lower()))
            if not price_elem:
                continue
            
            price_text = price_elem.get_text(strip=True)
            price = parse_price_from_text(price_text)
            
            if price and price > 0:
                results.append({
                    'title': title,
                    'volume': volume,
                    'price': price,
                    'source': 'avito'
                })
        except Exception as e:
            print(f"Ошибка при парсинге элемента: {e}")
            continue
    
    return results


async def get_prices_from_avito(oil_catalog: List[Tuple[str, int]]) -> Dict[Tuple[str, int], int]:
    """
    Получение актуальных цен с Avito для списка масел.
    
    Args:
        oil_catalog: Список кортежей (название масла, объем)
        
    Returns:
        Dict: Словарь {(название, объем): цена} с актуальными ценами
    """
    async with ClientSession() as session:
        tasks = []
        for oil_name, volume in oil_catalog:
            task = search_avito_for_oil(session, oil_name, volume)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for i, result in enumerate(results):
            oil_name, volume = oil_catalog[i]
            if isinstance(result, Exception):
                print(f"Ошибка при поиске {oil_name} {volume}мл: {result}")
                continue
            
            if result:
                # Берем среднюю цену из первых 3 результатов
                valid_prices = [item['price'] for item in result[:3] if item['price'] > 0]
                if valid_prices:
                    avg_price = sum(valid_prices) // len(valid_prices)
                    prices[(oil_name, volume)] = avg_price
                    print(f"Найдена цена для {oil_name} {volume}мл: {avg_price} руб.")
        
        return prices


async def update_prices_from_avito() -> int:
    """
    Обновление цен в базе данных из Avito.
    
    Returns:
        int: Количество обновленных записей
    """
    from Catalog import get_oil_catalog
    from Database import insert_price_list_items
    from UseDatabase import UseDatabase, config
    
    # Получаем текущий каталог
    catalog = get_oil_catalog()
    
    # Преобразуем в формат для поиска
    search_list = [(name, vol) for name, vol, _ in catalog]
    
    # Получаем цены с Avito
    avito_prices = await get_prices_from_avito(search_list)
    
    updated_count = 0
    with UseDatabase(config) as cursor:
        for (oil_name, volume), new_price in avito_prices.items():
            # Обновляем цену в базе данных
            _SQL_update_price = """UPDATE price_list SET price = %s WHERE oil_name = %s AND volume = %s"""
            cursor.execute(_SQL_update_price, (new_price, oil_name, volume))
            if cursor.rowcount > 0:
                updated_count += 1
                print(f"Обновлена цена: {oil_name} {volume}мл -> {new_price} руб.")
    
    return updated_count


if __name__ == "__main__":
    # Тестовый запуск
    print("Тест парсинга Avito...")
    test_catalog = [
        ("Motul 8100 X-cess", 5000),
        ("Shell Helix Ultra", 4000),
    ]
    
    async def test():
        prices = await get_prices_from_avito(test_catalog)
        print(f"\nНайдено цен: {len(prices)}")
        for key, price in prices.items():
            print(f"{key[0]} {key[1]}мл: {price} руб.")
    
    asyncio.run(test())
