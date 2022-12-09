from datetime import datetime

from OilClient import OilClient


class OilOrder(OilClient):

    def __init__(self, data: datetime, name: str, surname: str, phone: str, address: str, oil_types: str, volume: int,
                 price: int, total_price: int):
        super().__init__(name, surname, phone, address, oil_types, volume, price)
        self.data = data
        self.bottle_list = []
        self.total_price = total_price

    def add_bottle(self, bottle_amount):
        for i in range(bottle_amount):
            return self.bottle_list.append()

    #amount = input('Количество бутылок')

    def count_price(self, amount, price):
        self.total_price = amount * price
        return self.total_price

    price_list = {'ЧерныйТмин': {'50ml': 500,
                                 '100мл': 900,
                                 '250мл': 1800,
                                 '500мл': 3240,
                                 '1л': 5830},
                  'Тыква': {'100мл': 520,
                            '250мл': 1040,
                            '500мл': 1870,
                            '1л': 3370}
                  }
