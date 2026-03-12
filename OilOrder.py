"""
Модуль для работы с заказами масел.
Содержит класс OilOrder для представления заказа клиента.
"""
from datetime import datetime


class OilOrder:
    """
    Класс для представления заказа на масла.
    
    Attributes:
        customer (Customer): Объект клиента, сделавшего заказ
        data (datetime): Дата создания заказа
        shipping_date (datetime): Планируемая дата доставки
        order_details (list): Список позиций заказа
        total_price (float): Общая стоимость заказа
    """

    def __init__(self, customer, data: datetime, shipping_date: datetime):
        """
        Инициализация объекта заказа.
        
        Args:
            customer: Объект клиента
            data: Дата создания заказа
            shipping_date: Планируемая дата доставки
        """
        self.customer = customer
        self.data = data
        self.shipping_date = shipping_date
        self.order_details = []
        self.total_price = 0

    def add_bottle(self, product) -> None:
        """
        Добавление позиции товара в заказ.
        
        Args:
            product: Объект OrderItem для добавления в заказ
        """
        return self.order_details.append(product)

    def calculate_total_price(self) -> float:
        """
        Расчет общей стоимости заказа.
        
        Returns:
            float: Общая стоимость всех позиций в заказе
        """
        self.total_price = sum([float(product.price * product.count) for product in self.order_details])
        return self.total_price
