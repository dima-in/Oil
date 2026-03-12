"""
Модуль для работы с клиентами.
Содержит класс Customer для представления данных клиента.
"""


class Customer:
    """
    Класс для представления клиента.
    
    Attributes:
        id (int): Уникальный идентификатор клиента
        name (str): Имя клиента
        surname (str): Фамилия клиента
        phone (str): Номер телефона
        address (str): Адрес доставки
    """
    
    def __init__(self, id: int, name: str, surname: str, phone: str, address: str):
        """
        Инициализация объекта клиента.
        
        Args:
            id: Уникальный идентификатор клиента
            name: Имя клиента
            surname: Фамилия клиента
            phone: Номер телефона
            address: Адрес доставки
        """
        self.id = id
        self.name = name
        self.surname = surname
        self.phone = phone
        self.address = address
