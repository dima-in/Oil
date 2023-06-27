from datetime import datetime

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from Catalog import add_price_data_to_table
from Customer import Customer
from Database import create_tables, insert_statuses_to_database, save_status, \
    get_status_name, save_order_details, save_order, save_customer, get_customer_by_phone, select_all_orders
from Catalog import get_oil_catalog
from OilOrder import OilOrder
from OrderItem import OrderItem

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory='templates')


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

    await create_tables()
    await insert_statuses_to_database()
    await add_price_data_to_table()
    form_data = await request.form()

    date = datetime.now()
    name = form_data.get('name')
    surname = form_data.get('surname')
    phone = form_data.get('phone')
    address = form_data.get('address')
    status = int(form_data.get('status'))
    products = form_data.get('selected_products')
    shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')  # парсим дату доставки из формы

    """запрос в БД осуществляет поикс клиента по номеру телефона """
    existing_customer = await get_customer_by_phone(phone)

    """если по указанному номеру клиент  не найден, создать нового клиента"""
    if existing_customer is None:
        customer_id = await save_customer(address, name, phone, surname)
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
    order_id = await save_order(customer_id, date, order, shipping_date, status)

    """сохранение деталей заказа"""
    for product in order.order_details:
        await save_order_details(order_id, product)

    status_name = await get_status_name(status)
    """запись текущего статуса"""
    await save_status(order_id, status, status_name)

    oil_catalog = get_oil_catalog()  # TODO! DRY!!
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


@app.get('/view-orders')
def show_orders(request: Request):
    order = select_all_orders()
    context = {'request': request, 'title': "Начальная страница", 'order': order}
    return templates.TemplateResponse('vieworder.html', context)


# **********************************************************************************************


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
