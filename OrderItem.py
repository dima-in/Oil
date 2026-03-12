"""
Модуль для работы с элементами заказа.
Содержит класс OrderItem для представления позиции в заказе.
"""


class OrderItem:
    """
    Класс для представления позиции в заказе (товар + количество + цена).
    
    Attributes:
        oil_name (str): Название масла
        volume (int): Объем в мл
        count (int): Количество единиц товара
        price (float): Цена за единицу
    """

    def __init__(self, oil_name: str, volume: int, count: int, price: float):
        """
        Инициализация объекта позиции заказа.
        
        Args:
            oil_name: Название масла
            volume: Объем в мл
            count: Количество единиц товара
            price: Цена за единицу
        """
        self.oil_name = oil_name
        self.volume = volume
        self.count = count
        self.price = price

