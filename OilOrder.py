from datetime import datetime


class OilOrder:

    def __init__(self, customer, data: datetime, shipping_date: datetime):
        self.customer = customer
        self.data = data
        self.shipping_date = shipping_date
        self.order_details = []
        self.total_price = 0

    def add_bottle(self, product):
        return self.order_details.append(product)

    def calculate_total_price(self):
        self.total_price = sum([float(product.price*product.count) for product in self.order_details])
        return self.total_price
