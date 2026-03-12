import secrets
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from Catalog import add_price_data_to_table
from Catalog import get_oil_catalog
from Customer import Customer
from Database import create_tables, insert_statuses_to_database, save_status, get_status_name, save_order_details, save_order, save_customer, get_customer_by_phone, select_all_orders,  is_id_exist
from Database import get_all_prices, update_price, delete_price, add_price_item, clear_price_list
from OilOrder import OilOrder
from OrderItem import OrderItem
from Database import delete_order_dy_id
from ExtractPDFPriceListTable import parse_price_list_pdf

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory='templates')
security = HTTPBasic()


@app.get('/', response_class=HTMLResponse)
@app.get('/entry', response_class=HTMLResponse)
def view(request: Request):
    """
    entry() - обработчик GET-запроса для вывода начального шаблона
    """
    oil_catalog = get_oil_catalog()
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "oilpress"
    correct_password = "MarshallJCM800"

    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@app.post('/create-order')
async def create_order(request: Request, current_username: str = Depends(get_current_username)):
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
    """получение имени статуса """
    status_name = await get_status_name(status)
    """запись текущего статуса"""
    await save_status(order_id, status, status_name)

    oil_catalog = get_oil_catalog()  # TODO! DRY!!
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


@app.get("/users/me")
def read_current_user(username: str = Depends(get_current_username)):
    return {"username": username}


@app.get('/view-all-orders')
async def show_orders(request: Request, current_username: str = Depends(get_current_username)):
    print("Request body:", await request.body())

    order = select_all_orders()
    context = {'request': request, 'title': "Начальная страница", 'order': order}
    return templates.TemplateResponse('viewallorder.html', context)


@app.get('/view-orders')
def show_orders(request: Request):
    order = select_all_orders()
    context = {'request': request, 'title': "Начальная страница", 'order': order}
    return templates.TemplateResponse('vieworder.html', context)


@app.post('/delete-order')
async def delite_order(request: Request):
    form_data = await request.form()
    order_id = int(form_data.get('id_to_delete'))
    if is_id_exist(order_id):
        delete_order_dy_id(order_id)
    else:
        print('Неверный order_id')
    return RedirectResponse("/view-all-orders", status_code=303)


# **********************************************************************************************
# ==================== Админ-панель: Управление прайс-листом ====================
# **********************************************************************************************

@app.get('/admin/pricelist')
def admin_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    """Страница управления прайс-листом"""
    prices = get_all_prices()
    context = {
        'request': request,
        'title': "Управление прайс-листом",
        'prices': prices
    }
    return templates.TemplateResponse('admin_pricelist.html', context)


@app.post('/admin/pricelist/update')
async def admin_update_price(request: Request, current_username: str = Depends(get_current_username)):
    """Обновление цены товара"""
    form_data = await request.form()
    price_id = int(form_data.get('price_id'))
    new_price = float(form_data.get('new_price'))
    update_price(price_id, new_price)
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/delete')
async def admin_delete_price(request: Request, current_username: str = Depends(get_current_username)):
    """Удаление товара из прайс-листа"""
    form_data = await request.form()
    price_id = int(form_data.get('price_id'))
    delete_price(price_id)
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/add')
async def admin_add_price(request: Request, current_username: str = Depends(get_current_username)):
    """Добавление нового товара в прайс-лист"""
    form_data = await request.form()
    oil_name = form_data.get('oil_name')
    volume = int(form_data.get('volume'))
    price = float(form_data.get('price'))
    add_price_item(oil_name, volume, price)
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/clear')
async def admin_clear_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    """Очистка всего прайс-листа"""
    clear_price_list()
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.get('/admin/upload-pricelist')
def admin_upload_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    """Страница загрузки PDF прайс-листа"""
    context = {
        'request': request,
        'title': "Загрузка прайс-листа"
    }
    return templates.TemplateResponse('admin_upload.html', context)


@app.post('/admin/upload-pricelist')
async def admin_process_upload(request: Request, current_username: str = Depends(get_current_username)):
    """Обработка загруженного PDF файла"""
    try:
        form_data = await request.form()
        pdf_file = form_data.get('pdf_file')
        
        if pdf_file and pdf_file.filename:
            # Сохраняем файл во временную папку
            file_contents = await pdf_file.read()
            with open('tmp/' + pdf_file.filename, 'wb') as f:
                f.write(file_contents)
            
            # Парсим PDF и обновляем прайс-лист
            clear_price_list()
            parse_price_list_pdf('tmp/' + pdf_file.filename)
            
            context = {
                'request': request,
                'title': "Загрузка завершена",
                'message': "Прайс-лист успешно загружен!"
            }
            return templates.TemplateResponse('admin_upload.html', context)
        else:
            context = {
                'request': request,
                'title': "Ошибка загрузки",
                'error': "Файл не выбран"
            }
            return templates.TemplateResponse('admin_upload.html', context, status_code=400)
    except Exception as e:
        context = {
            'request': request,
            'title': "Ошибка загрузки",
            'error': str(e)
        }
        return templates.TemplateResponse('admin_upload.html', context, status_code=500)


# **********************************************************************************************


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
