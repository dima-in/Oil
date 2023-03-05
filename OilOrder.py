from datetime import datetime
from Customer import Customer
from Product import Product


class OilOrder(Customer, Product):

    def __init__(self, data: datetime, shipping_date: datetime):
        self.data = data
        self.shipping_date = shipping_date
        self.product_basket = []
        self.total_price = 0

    def add_bottle(self, oil_name, volume, price):
        product = Product(oil_name=oil_name, volume=volume, price=price)
        return self.product_basket.append(product)

    def calculate_total_price(self):
        self.total_price = sum([product.price for product in self.product_basket])
        return self.total_price
