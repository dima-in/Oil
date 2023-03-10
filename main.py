from datetime import datetime
from OilOrder import OilOrder
from Catalog import get_oil_prices
from OrderItem import OrderItem
from UseDatabase import config
from Customer import Customer
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Form
import requests
from fastapi import Request
from fastapi import FastAPI
from UseDatabase import UseDatabase

app = FastAPI()
templates = Jinja2Templates(directory='templates')


@app.get('/entry', response_class=HTMLResponse)
def view(request: Request):
    """
    entry() - обработчик GET-запроса для вывода начального шаблона
    """
    oil_price_list = get_oil_prices()
    for item in oil_price_list:
        print(f'item oil_price_list in view = {item}')
    context = {"request": request, 'title': "Начальная страница", 'oil_price_list': oil_price_list}
    return templates.TemplateResponse('inputdata.html', context)


@app.post('/createorder')
async def create_order(request: Request):
    with UseDatabase(config) as cursor:
        form_data = await request.form()

        date = datetime.now()
        name = form_data.get('name')
        surname = form_data.get('surname')
        phone = form_data.get('phone')
        address = form_data.get('address')
        products = form_data.getlist('select_products')
        shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')  # парсим дату доставки из формы

        """запрос в БД осуществляет поикс клиента по номеру телефона """
        _SQL_select_customer = """ select id, name, surname, phone FROM customers 
                        WHERE phone=%s"""
        cursor.execute(_SQL_select_customer, (phone,))
        existing_customer = cursor.fetchone()  # получаем следующую строку из запроса

        """если по указанному номеру клиент  не найден, создать нового клиента"""
        if existing_customer is None:
            _SQL_create_customer = """insert into customers (name, surname, phone, address)
                    VALUES (%s, %s, %s, %s)"""
            cursor.execute(_SQL_create_customer, (name, surname, phone, address))
            customer_id = cursor.lastrowid  # получаем ID нового клиента
        else:
            customer_id = existing_customer[0]  # получаем ID существующего клиента

        customer = Customer(id=customer_id, name=name, surname=surname, phone=phone, address=address)

        order = OilOrder(customer, data=date, shipping_date=shipping_date)
        # сохраняем заказ в БД
        _SQL_save_order = """INSERT INTO orders (customer_id, date, shipping_date, total_price, status) 
                                    VALUES (%s, %s, %s, %s, 0)"""
        cursor.execute(_SQL_save_order, (customer_id, date, shipping_date, order.calculate_total_price()))
        order_id = cursor.lastrowid  # получаем ID заказа

        for product in products:  # получаем корзину заказа из формы
            oil_name, volume, price = product.split('_')
            product = OrderItem(oil_name=oil_name, volume=volume, count=1, price=price)
            order.add_bottle(product)

        for product in order.order_details:
            _SQL_save_order_details = """INSERT INTO order_details (order_id, oil_name, volume, count, price)
            VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(_SQL_save_order_details,
                           (order_id, product.oil_name, product.volume, product.count, product.price))


@app.get('/vieworders')
def show_orders(request: Request):
    with UseDatabase(config) as cursor:
        _SQL_select_all = """SELECT * FROM orders 
                            JOIN order_details ON orders.id = order_details.order_id
                            JOIN customers ON order_details.customer_id = customers.id;
                            """
        _SQL_select_all2 = """SELECT * FROM order_details 
                            JOIN customers ON order_details.customer_id = customers.id;
                            JOIN orders ON customers.order_id = orders.id
"""
        cursor.execute(_SQL_select_all2)
        order = cursor.fetchall()
        context = {'request': request, 'title': "Начальная страница", 'order': order}
        return templates.TemplateResponse('vieworder.html', context)


# **********************************************************************************************


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
