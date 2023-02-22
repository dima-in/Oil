from datetime import datetime

from OilClient import OilClient
from Product import Product


class OilOrder(OilClient, Product):

    def __init__(self, data: datetime, name: str, surname: str, phone: str, address: str, oil_types: str, volume: int,
                 price: int, total_price: int):
        super().__init__(name, surname, phone, address, oil_types, volume, price)
        self.data = data
        self.bottle_list = []
        self.total_price = total_price

    def add_bottle(self, bottle_amount):
        for i in range(bottle_amount):
            return self.bottle_list.append()



