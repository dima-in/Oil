from datetime import datetime

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from Catalog import get_oil_catalog, create_catalog_table, add_price_row
from Customer import Customer
from DBTable import create_tables, create_oil_statuses
from OilOrder import OilOrder
from OrderItem import OrderItem
from UseDatabase import UseDatabase
from UseDatabase import config

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory='templates')

# создает таблицы, необходимые перед вызовом view(request: Request)
@app.get('/create-table-try-except-method', response_class=HTMLResponse)
def create_table_try_except_method():
    with UseDatabase(config) as cursor:
        try:
            # попытаться выполнить запрос для получения данных из таблицы oil-statuses
            cursor.execute('SELECT * FROM oil_statuses')
        except:
            # таблица oil-statuses не существует, вызываем функцию create_table_insert_items()

            create_oil_statuses()

        try:
            # попытаться выполнить запрос для получения данных из таблицы catalog
            cursor.execute('SELECT * FROM catalog')
        except:
            # таблица catalog не существует, вызываем функцию create_table_insert_items()
            create_catalog_table()
            add_price_row()

# создает таблицы, необходимые перед вызовом view(request: Request)
@app.get('/create-oil-statuses-catalog-table', response_class=HTMLResponse)
def create_table_insert_items():
    with UseDatabase(config) as cursor:

            # попытаться выполнить запрос для получения данных из таблицы oil-statuses
        if cursor.execute('SELECT * FROM oil_statuses'):
            print('table oil_statuses exist')
            # таблица oil-statuses не существует, вызываем функцию create_table_insert_items()
        else:
            print('table oil_statuses doesn"t exist')
            create_oil_statuses()


            # попытаться выполнить запрос для получения данных из таблицы catalog
        if cursor.execute('SELECT * FROM catalog'):
            print('table catalog exist')
            # таблица catalog не существует, вызываем функцию create_table_insert_items()
        else:
            print('table catalog doesn"t exist')
            create_catalog_table()
            add_price_row()

# создает таблицы, необходимые перед вызовом view(request: Request)
@app.get('/create-first', response_class=HTMLResponse)
def create_table_insert_items():
    with UseDatabase(config) as cursor:

            create_oil_statuses()
            create_catalog_table()
            add_price_row()



@app.get('/', response_class=HTMLResponse)
@app.get('/entry', response_class=HTMLResponse)
def view(request: Request):
    """
    entry() - обработчик GET-запроса для вывода начального шаблона
    """
    oil_catalog = get_oil_catalog()
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


@app.post('/create-order')
async def create_order(request: Request):
    create_table_insert_items()
    create_tables()
    with UseDatabase(config) as cursor:
        form_data = await request.form()

        date = datetime.now()
        name = form_data.get('name')
        surname = form_data.get('surname')
        phone = form_data.get('phone')
        address = form_data.get('address')
        status = int(form_data.get('status'))
        products = form_data.get('selected_products')
        print(f'products =  {products}')
        shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')  # парсим дату доставки из формы

        """запрос в БД осуществляет поикс клиента по номеру телефона """
        _SQL_select_customer = """ SELECT id, name, surname, phone FROM customers 
                        WHERE phone=%s"""
        cursor.execute(_SQL_select_customer, (phone,))
        existing_customer = cursor.fetchone()  # получаем следующую строку из запроса

        """если по указанному номеру клиент  не найден, создать нового клиента"""
        if existing_customer is None:
            _SQL_create_customer = """INSERT INTO customers (name, surname, phone, address)
                    VALUES (%s, %s, %s, %s)"""
            cursor.execute(_SQL_create_customer, (name, surname, phone, address))
            customer_id = cursor.lastrowid  # получаем ID нового клиента
        else:
            customer_id = existing_customer[0]  # получаем ID существующего клиента

        """создание экземпляра клиента customer для передачи в экземпляр заказа order"""
        customer = Customer(id=customer_id, name=name, surname=surname, phone=phone, address=address)
        """создание экземпляр заказа"""
        order = OilOrder(customer, data=date, shipping_date=shipping_date)

        """извлечение заказа из формы products = form_data.get('select_products'),
        создание экземпляра продукта product и добавление в список деталей заказа
        """

        for product in products.split(','):  # получаем детали заказа из формы
            oil_name, volume, price, count = product.split('_')
            product = OrderItem(oil_name=oil_name, volume=int(volume.replace('мл', '')),
                                count=int(count.replace('x ', '')), price=float(price.replace('руб', '')))
            order.add_bottle(product)

        """сохранение заказа в БД"""
        _SQL_save_order = """INSERT INTO orders (customer_id, date, shipping_date, total_price, status) 
                                    VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(_SQL_save_order, (customer_id, date, shipping_date, order.calculate_total_price(), status))
        order_id = cursor.lastrowid  # получаем ID заказа

        """сохранение деталей заказа"""
        for product in order.order_details:
            _SQL_save_order_details = """INSERT INTO order_details (order_id, oil_name, volume, count, price)
            VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(_SQL_save_order_details,
                           (order_id, product.oil_name, product.volume, product.count, product.price))

        """запись текущего статуса"""
        _SQL_insert_statuses_list = """INSERT INTO statuses_list (order_id, order_status, name) 
        VALUES (%s, %s, %s)"""


        _SQL_select_status_name = """SELECT name FROM order_statuses WHERE id = %s"""
        cursor.execute(_SQL_select_status_name, (status,))
        status_name = cursor.fetchone()[0]
        cursor.execute(_SQL_insert_statuses_list, (order_id, status, status_name))
    oil_catalog = get_oil_catalog()  # TODO! DRY!!
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


@app.get('/view-orders')
def show_orders(request: Request):
    with UseDatabase(config) as cursor:

        _SQL_select_all = """SELECT * FROM orders 
                            JOIN customers ON orders.customer_id = customers.id
                            JOIN order_details ON orders.id = order_details.order_id
                            JOIN statuses_list ON orders.id = statuses_list.order_id;
                            """
        cursor.execute(_SQL_select_all)
        order = cursor.fetchall()
        context = {'request': request, 'title': "Начальная страница", 'order': order}
        return templates.TemplateResponse('vieworder.html', context)


# **********************************************************************************************


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
