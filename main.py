from datetime import datetime
from OilOrder import OilOrder
import mysql.connector
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Form
import requests
from fastapi import Request
from fastapi import FastAPI

from Product import Product
from UseDatabase import UseDatabase

app = FastAPI()
templates = Jinja2Templates(directory='templates')


def create_order(request: Request):
    config = {
        'host': 'localhost',
        'user': 'myuser',
        'password': 'mypassword',
        'database': 'mydatabase'
    }
    with UseDatabase(config) as cursor:
        form_data = request.form()

        date = datetime.now()
        name = form_data.get('name')
        surname = form_data.get('surname')
        phone = form_data.get('phone')
        address = form_data.get('address')
        shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')  # парсим дату доставки из формы

        _SQL_select_customer = """ select name, surname, phone, address from customer 
                WHERE name=%s AND surname=%s AND phone=%s"""
        cursor.execute(_SQL_select_customer, (name, surname, phone, address))
        existing_customer = cursor.fetchone()  # получаем следующую строку из запроса

        #  если запись о клиенте в БД не найдена, создать нового клиента
        if not existing_customer:
            _SQL_create_customer = """insert into customer (name, surname, phone, address)
            VALUES (%s, %s, %s, %s)"""
            cursor.execute(_SQL_create_customer, (name, surname, phone, address))
            customer_id = cursor.lastrowid  # получаем ID нового клиента
        else:
            customer_id = existing_customer[0]  # получаем ID существующего клиента

        order = OilOrder(data=date, shipping_date=shipping_date, customer_id=customer_id)

        for key in order.product_basket:  # получаем корзину зааза из формы
            if 'oil_name' in key:  # если ключ соответствует oil_name
                form_index = key.split('_')[-1]  # получаем индекс из oil_name_1
                oil_name = form_data.get(key)  # получаем значение oil_name добавляя индеск
                volume = form_data.get('volume_{}'.format(form_index))  # получаем значение volume_ добавляя индеск
                price = form_data.get('price_{}'.format(form_index))  # получаем значение volume_ добавляя индеск
                order.add_bottle(oil_name=oil_name, volume=volume, price=price)

        # сохраняем заказ в БД
        _SQL_save_order = """INSERT INTO orders (customer_id, date, shipping_date, total_price) 
                            VALUES (%s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order, (customer_id, date, shipping_date, order.calculate_total_price()))

        order_id = cursor.lastrowid  # получаем ID заказа
        for product in order.product_basket:
            _SQL_save_order_basket = """INSERT INTO order_basket (order_id, oil_name, volume, price)
            VALUES (%s, %s, %s, %s)"""
            cursor.execute(_SQL_save_order_basket, (order_id, product.oil_name, product.volume, product.price))


@app.get('/entryorder')
@app.get('/')
def enrty_page() -> 'html':
    return render_template('entryorder.html', the_title='Выжимальня приветствует тебя!',
                           the_invitation='Введите данные заказа:',
                           the_clickbutton='Когда будете готовы, нажмите эту кнопку:')


@app.post('/showorder')
def show_order_list() -> 'html':
    with open('заказы.txt') as orders:
        list_order = []
        for line in orders:
            list_order.append(line.split('|'))
    titles = ('Клиент', 'Масло', 'Стоимость', 'Дата')
    return render_template('showorder.html', the_row_order=titles, the_data=list_order, )


# **********************************************************************************************


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
