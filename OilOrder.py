from datetime import datetime
from Customer import Customer
from Product import Product


class OilOrder(Customer, Product):

    def __init__(self, data: datetime, shipping_date: datetime, customer_id):
        self.data = data
        self.shipping_date = shipping_date
        self.customer_id = customer_id
        self.product_basket = []
        self.total_price = 0

    def add_bottle(self, oil_name, volume, price):
        product = Product(oil_name=oil_name, volume=volume, price=price)
        return self.product_basket.append(product)

    def calculate_total_price(self):
        self.total_price = sum([product.price for product in self.product_basket])
        return self.total_price



def create_order(request: Request):
    config = {
        'host': 'localhost',
        'user': 'myuser',
        'password': 'mypassword',
        'database': 'mydatabase'
    }
    with UseDatabase(config) as cursor:
        # Получаем данные из формы
        form_data = request.form()
        name = form_data.get('name')
        surname = form_data.get('surname')
        phone = form_data.get('phone')
        address = form_data.get('address')
        data = datetime.now()  # Дата заказа
        shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')  # Дата доставки

        # Ищем клиента в базе данных
        _SQL_select_customer = """SELECT id FROM customer 
                                 WHERE name = ? AND surname = ? AND phone = ? AND address = ?"""
        cursor.execute(_SQL_select_customer, (name, surname, phone, address))
        row = cursor.fetchone()

        # Если клиент не найден, создаем нового
        if not row:
            _SQL_insert_customer = """INSERT INTO customer (name, surname, phone, address)
                                      VALUES (?, ?, ?, ?)"""
            cursor.execute(_SQL_insert_customer, (name, surname, phone, address))
            customer_id = cursor.lastrowid
        else:
            customer_id = row[0]

        # Создаем заказ
        order = OilOrder(data=data, shipping_date=shipping_date, customer_id=customer_id)

        # Извлекаем данные о продуктах из формы в список товаров
        for key in form_data.keys():
            if 'oil_name' in key:
                idx = key.split('_')[-1]
                oil_name = form_data.get(key)
                volume = form_data.get('volume_{}'.format(idx))
                price = form_data.get('price_{}'.format(idx))
                order.add_bottle(oil_name=oil_name, volume=volume, price=price)


        # Сохраняем заказ в базу данных
        _SQL_insert_order = """INSERT INTO orders (customer_id, data, shipping_date, total_price)
                              VALUES (?, ?, ?, ?)"""
        cursor.execute(_SQL_insert_order, (customer_id, data, shipping_date, order.calculate_total_price()))

        # Сохраняем каждый продукт из корзины в таблицу order_details
        order_id = cursor.lastrowid
        for product in order.product_basket:
            _SQL_insert_order_detail = """INSERT INTO order_details (order_id, oil_name, volume, price)
                                          VALUES (?, ?, ?, ?)"""
            cursor.execute(_SQL_insert_order_detail, (order_id, product.oil_name, product.volume, product.price))

    return f"Order created with ID: {order_id}"

