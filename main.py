import math
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from Catalog import add_price_data_to_table, get_oil_catalog, load_pricelist_from_pdf
from Customer import Customer
from Database import (
    add_expense_entry,
    add_price_item,
    add_production_batch,
    clear_price_list,
    delete_production_profile,
    create_tables,
    delete_expense_entry,
    delete_order_dy_id,
    delete_price,
    delete_production_batch,
    get_batch_counts_by_date,
    get_all_prices,
    get_batch_analytics,
    get_customer_by_phone,
    list_expense_entries,
    list_production_profiles,
    list_production_batches,
    get_price_item,
    get_profit_summary,
    get_status_name,
    insert_statuses_to_database,
    is_id_exist,
    save_customer,
    save_order,
    save_order_details,
    save_status,
    select_all_orders,
    update_price_item,
    upsert_production_profile,
)
from OilOrder import OilOrder
from OrderItem import OrderItem

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory='templates')
security = HTTPBasic()


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


def parse_date_or_none(value: Optional[str]):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def default_analytics_range():
    today = date.today()
    start = today.replace(day=1)
    return start, today


def _schedule_batch_dates(batch_count, target_date, daily_batch_limit, occupied_counts):
    if batch_count <= 0:
        return []

    planned_dates = []
    cursor_date = target_date
    used_counts = dict(occupied_counts)

    while len(planned_dates) < batch_count:
        key = cursor_date.isoformat()
        used_today = used_counts.get(key, 0)
        free_slots = max(daily_batch_limit - used_today, 0)

        if free_slots > 0:
            to_assign = min(free_slots, batch_count - len(planned_dates))
            planned_dates.extend([key] * to_assign)
            used_counts[key] = used_today + to_assign

        cursor_date -= timedelta(days=1)

    return sorted(planned_dates)


def _build_order_production_plan(order_items, shipping_date, profiles_by_oil, occupied_counts):
    grouped = {}
    for item in order_items:
        plan_item = grouped.setdefault(item['oil_name'], {
            'oil_name': item['oil_name'],
            'total_volume_ml': 0,
            'bottles': [],
        })
        plan_item['total_volume_ml'] += int(item['volume']) * int(item['count'])
        plan_item['bottles'].append({
            'volume': int(item['volume']),
            'count': int(item['count']),
        })

    plan = []
    planning_counts = dict(occupied_counts)
    target_date = shipping_date or date.today()

    for oil_name in sorted(grouped.keys()):
        item = grouped[oil_name]
        profile = profiles_by_oil.get(oil_name)
        bottles = sorted(item['bottles'], key=lambda bottle: bottle['volume'])
        profile_ready = bool(
            profile
            and float(profile.get('batch_seed_weight_kg', 0) or 0) > 0
            and float(profile.get('yield_percent', 0) or 0) > 0
        )

        output_per_batch_ml = 0
        batches_needed = 0
        suggested_dates = []
        daily_batch_limit = int(profile.get('daily_batch_limit', 3) or 3) if profile else 3

        if profile_ready:
            output_per_batch_ml = float(profile['batch_seed_weight_kg']) * float(profile['yield_percent']) * 10
            if output_per_batch_ml > 0:
                batches_needed = math.ceil(item['total_volume_ml'] / output_per_batch_ml)
                suggested_dates = _schedule_batch_dates(
                    batches_needed,
                    target_date,
                    daily_batch_limit,
                    planning_counts,
                )
                for scheduled_date in suggested_dates:
                    planning_counts[scheduled_date] = planning_counts.get(scheduled_date, 0) + 1

        plan.append({
            'oil_name': oil_name,
            'total_volume_ml': item['total_volume_ml'],
            'bottles': bottles,
            'profile_id': profile.get('id') if profile else None,
            'profile_ready': profile_ready,
            'batch_seed_weight_kg': float(profile.get('batch_seed_weight_kg', 0) or 0) if profile else 0,
            'yield_percent': float(profile.get('yield_percent', 0) or 0) if profile else 0,
            'output_per_batch_ml': output_per_batch_ml,
            'batches_needed': batches_needed,
            'daily_batch_limit': daily_batch_limit,
            'suggested_dates': suggested_dates,
        })

    return plan


@app.post('/create-order')
async def create_order(request: Request, current_username: str = Depends(get_current_username)):
    await create_tables()
    await insert_statuses_to_database()
    await add_price_data_to_table()
    form_data = await request.form()

    order_date = datetime.now()
    name = form_data.get('name')
    surname = form_data.get('surname')
    phone = form_data.get('phone')
    address = form_data.get('address')
    order_status = int(form_data.get('status'))
    products = form_data.get('selected_products')
    shipping_date = datetime.strptime(form_data.get('shipping_date'), '%Y-%m-%d')

    existing_customer = await get_customer_by_phone(phone)
    if existing_customer is None:
        customer_id = await save_customer(address, name, phone, surname)
    else:
        customer_id = existing_customer[0]

    customer = Customer(id=customer_id, name=name, surname=surname, phone=phone, address=address)
    order = OilOrder(customer, data=order_date, shipping_date=shipping_date)

    for product in products.split(','):
        oil_name, volume, price, count = product.split('_')
        price_item = get_price_item(oil_name, int(volume.replace('мл', '')))
        order_item = OrderItem(
            oil_name=oil_name,
            volume=int(volume.replace('мл', '')),
            count=int(count.replace('x ', '')),
            price=float(price.replace('руб', '')),
            seed_weight_kg=float(price_item['seed_weight_kg']) if price_item else 0,
            seed_price_per_kg=float(price_item['seed_price_per_kg']) if price_item else 0,
        )
        order.add_bottle(order_item)

    order_id = await save_order(customer_id, order_date, order, shipping_date, order_status)

    for product in order.order_details:
        await save_order_details(order_id, product)

    status_name = await get_status_name(order_status)
    await save_status(order_id, order_status, status_name)

    oil_catalog = get_oil_catalog()
    context = {"request": request, 'title': "Начальная страница", 'oil_catalog': oil_catalog}
    return templates.TemplateResponse('inputdata.html', context)


@app.get("/users/me")
def read_current_user(username: str = Depends(get_current_username)):
    return {"username": username}


@app.get('/view-all-orders')
async def show_orders(request: Request, current_username: str = Depends(get_current_username)):
    order = select_all_orders()
    context = {'request': request, 'title': "Начальная страница", 'order': order}
    return templates.TemplateResponse('viewallorder.html', context)


@app.get('/view-orders')
def show_orders_public(request: Request):
    order = select_all_orders()
    context = {'request': request, 'title': "Начальная страница", 'order': order}
    return templates.TemplateResponse('vieworder.html', context)


@app.post('/delete-order')
async def delite_order(request: Request):
    form_data = await request.form()
    order_id = int(form_data.get('id_to_delete'))
    if is_id_exist(order_id):
        delete_order_dy_id(order_id)
    return RedirectResponse("/view-all-orders", status_code=303)


@app.get('/admin/pricelist')
def admin_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    prices = get_all_prices()
    context = {
        'request': request,
        'title': "Управление прайс-листом",
        'prices': prices
    }
    return templates.TemplateResponse('admin_pricelist.html', context)


@app.post('/admin/pricelist/update')
async def admin_update_price(request: Request, current_username: str = Depends(get_current_username)):
    form_data = await request.form()
    price_id = int(form_data.get('price_id'))
    new_price = float(form_data.get('new_price'))
    item = get_price_item(form_data.get('oil_name'), int(form_data.get('volume')))
    update_price_item(
        price_id,
        form_data.get('oil_name'),
        int(form_data.get('volume')),
        new_price,
        float(item['seed_weight_kg']) if item else 0,
        float(item['seed_price_per_kg']) if item else 0,
    )
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/delete')
async def admin_delete_price(request: Request, current_username: str = Depends(get_current_username)):
    form_data = await request.form()
    price_id = int(form_data.get('price_id'))
    delete_price(price_id)
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/add')
async def admin_add_price(request: Request, current_username: str = Depends(get_current_username)):
    form_data = await request.form()
    add_price_item(
        form_data.get('oil_name'),
        int(form_data.get('volume')),
        float(form_data.get('price')),
        float(form_data.get('seed_weight_kg', 0) or 0),
        float(form_data.get('seed_price_per_kg', 0) or 0),
    )
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.post('/admin/pricelist/clear')
async def admin_clear_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    clear_price_list()
    return RedirectResponse("/admin/pricelist", status_code=303)


@app.get('/admin/upload-pricelist')
def admin_upload_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    context = {
        'request': request,
        'title': "Загрузка прайс-листа"
    }
    return templates.TemplateResponse('admin_upload.html', context)


@app.post('/admin/upload-pricelist')
async def admin_process_upload(request: Request, current_username: str = Depends(get_current_username)):
    try:
        form_data = await request.form()
        pdf_file = form_data.get('pdf_file')

        if pdf_file and pdf_file.filename:
            file_contents = await pdf_file.read()
            with open('tmp/' + pdf_file.filename, 'wb') as temp_file:
                temp_file.write(file_contents)

            clear_price_list()
            load_pricelist_from_pdf('tmp/' + pdf_file.filename)

            context = {
                'request': request,
                'title': "Загрузка завершена",
                'message': "Прайс-лист успешно загружен!"
            }
            return templates.TemplateResponse('admin_upload.html', context)

        context = {
            'request': request,
            'title': "Ошибка загрузки",
            'error': "Файл не выбран"
        }
        return templates.TemplateResponse('admin_upload.html', context, status_code=400)
    except Exception as error:
        context = {
            'request': request,
            'title': "Ошибка загрузки",
            'error': str(error)
        }
        return templates.TemplateResponse('admin_upload.html', context, status_code=500)


@app.get('/api/catalog')
async def api_get_catalog():
    await create_tables()
    catalog = get_oil_catalog()
    return [{"oil_name": item[0], "volume": item[1], "price": item[2]} for item in catalog]


@app.get('/api/orders')
async def api_get_orders(current_username: str = Depends(get_current_username)):
    await create_tables()
    orders = select_all_orders()
    profiles_by_oil = {profile['oil_name']: profile for profile in list_production_profiles()}
    occupied_counts = get_batch_counts_by_date()
    grouped_orders = {}

    for row in orders:
        order = grouped_orders.setdefault(row[0], {
            "id": row[0],
            "customer_id": row[1],
            "date": str(row[2]) if row[2] else None,
            "shipping_date": str(row[3]) if row[3] else None,
            "total_price": row[4],
            "status": row[5],
            "customer_name": row[6],
            "customer_surname": row[7],
            "customer_phone": row[8],
            "customer_address": row[9],
            "items": [],
        })
        order["items"].append({
            "oil_name": row[10],
            "volume": row[11],
            "count": row[12],
            "price": row[13],
            "seed_weight_kg": row[14],
            "seed_price_per_kg": row[15],
            "seed_cost": row[16],
            "revenue": row[17],
            "profit": row[18],
        })

    result = []
    for order in grouped_orders.values():
        shipping_date = parse_date_or_none(order['shipping_date'])
        order['production_plan'] = _build_order_production_plan(
            order['items'],
            shipping_date,
            profiles_by_oil,
            occupied_counts,
        )
        result.append(order)

    return result


@app.post('/api/order')
async def api_create_order(request: Request, current_username: str = Depends(get_current_username)):
    await create_tables()
    await insert_statuses_to_database()

    data = await request.json()

    order_date = datetime.now()
    name = data.get('name')
    surname = data.get('surname')
    phone = data.get('phone')
    address = data.get('address')
    order_status = int(data.get('status', 0))
    items = data.get('items', [])
    shipping_date = datetime.strptime(data.get('shipping_date'), '%Y-%m-%d')

    existing_customer = await get_customer_by_phone(phone)
    if existing_customer is None:
        customer_id = await save_customer(address, name, phone, surname)
    else:
        customer_id = existing_customer[0]

    customer = Customer(id=customer_id, name=name, surname=surname, phone=phone, address=address)
    order = OilOrder(customer, data=order_date, shipping_date=shipping_date)

    for item in items:
        price_item = get_price_item(item['oil_name'], int(item['volume']))
        product = OrderItem(
            oil_name=item['oil_name'],
            volume=int(item['volume']),
            count=int(item['count']),
            price=float(item['price']),
            seed_weight_kg=float(price_item['seed_weight_kg']) if price_item else 0,
            seed_price_per_kg=float(price_item['seed_price_per_kg']) if price_item else 0,
        )
        order.add_bottle(product)

    order_id = await save_order(customer_id, order_date, order, shipping_date, order_status)

    for product in order.order_details:
        await save_order_details(order_id, product)

    status_name = await get_status_name(order_status)
    await save_status(order_id, order_status, status_name)

    return {"success": True, "order_id": order_id}


@app.get('/api/admin/pricelist')
async def api_get_pricelist(current_username: str = Depends(get_current_username)):
    await create_tables()
    prices = get_all_prices()
    return [
        {
            "id": p[0],
            "oil_name": p[1],
            "volume": p[2],
            "price": p[3],
            "seed_weight_kg": p[4],
            "seed_price_per_kg": p[5],
        }
        for p in prices
    ]


@app.post('/api/admin/pricelist')
async def api_add_price_item(item: dict, current_username: str = Depends(get_current_username)):
    await create_tables()
    add_price_item(
        item['oil_name'],
        int(item['volume']),
        float(item['price']),
        float(item.get('seed_weight_kg', 0) or 0),
        float(item.get('seed_price_per_kg', 0) or 0),
    )
    return {"success": True}


@app.put('/api/admin/pricelist/{price_id}')
async def api_update_price(price_id: int, price_data: dict, current_username: str = Depends(get_current_username)):
    await create_tables()
    current_item = next((item for item in get_all_prices() if item[0] == price_id), None)
    if current_item is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    update_price_item(
        price_id,
        price_data.get('oil_name', current_item[1]),
        int(price_data.get('volume', current_item[2])),
        float(price_data.get('price', current_item[3])),
        float(price_data.get('seed_weight_kg', current_item[4])),
        float(price_data.get('seed_price_per_kg', current_item[5])),
    )
    return {"success": True}


@app.delete('/api/admin/pricelist/{price_id}')
async def api_delete_price(price_id: int, current_username: str = Depends(get_current_username)):
    delete_price(price_id)
    return {"success": True}


@app.post('/api/admin/pricelist/clear')
async def api_clear_pricelist(current_username: str = Depends(get_current_username)):
    clear_price_list()
    return {"success": True}


@app.get('/api/admin/analytics')
async def api_admin_analytics(
    period: str = Query('month', pattern='^(day|week|month)$'),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    daily_batch_limit: int = Query(3, ge=1, le=24),
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    parsed_from = parse_date_or_none(date_from)
    parsed_to = parse_date_or_none(date_to)
    if parsed_from is None and parsed_to is None:
        parsed_from, parsed_to = default_analytics_range()
    summary = get_profit_summary(parsed_from, parsed_to, period)
    summary['batch_analytics'] = get_batch_analytics(parsed_from, parsed_to, daily_batch_limit)
    return summary


@app.get('/api/admin/expenses')
async def api_admin_expenses(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    return list_expense_entries(parse_date_or_none(date_from), parse_date_or_none(date_to))


@app.post('/api/admin/expenses')
async def api_add_expense(
    expense_data: dict,
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    expense_date = parse_date_or_none(expense_data.get('expense_date'))
    if expense_date is None:
        raise HTTPException(status_code=400, detail='expense_date is required')

    goods_total = expense_data.get('goods_total')
    weight_kg = float(expense_data.get('weight_kg', 0) or 0)
    price_per_kg = float(expense_data.get('price_per_kg', 0) or 0)
    if goods_total in (None, ''):
        goods_total = weight_kg * price_per_kg

    expense_id = add_expense_entry(
        expense_date,
        expense_data.get('item_name', ''),
        weight_kg,
        price_per_kg,
        float(goods_total or 0),
        float(expense_data.get('delivery_cost', 0) or 0),
        float(expense_data.get('carsharing_cost', 0) or 0),
        expense_data.get('note'),
    )
    return {'success': True, 'id': expense_id}


@app.delete('/api/admin/expenses/{expense_id}')
async def api_delete_expense(
    expense_id: int,
    current_username: str = Depends(get_current_username),
):
    delete_expense_entry(expense_id)
    return {'success': True}


@app.get('/api/admin/production-batches')
async def api_admin_production_batches(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    return list_production_batches(parse_date_or_none(date_from), parse_date_or_none(date_to))


@app.get('/api/admin/production-profiles')
async def api_admin_production_profiles(current_username: str = Depends(get_current_username)):
    await create_tables()
    return list_production_profiles()


@app.post('/api/admin/production-profiles')
async def api_upsert_production_profile(
    profile_data: dict,
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    oil_name = (profile_data.get('oil_name') or '').strip()
    if not oil_name:
        raise HTTPException(status_code=400, detail='oil_name is required')

    upsert_production_profile(
        oil_name,
        float(profile_data.get('batch_seed_weight_kg', 0) or 0),
        float(profile_data.get('yield_percent', 0) or 0),
        int(profile_data.get('daily_batch_limit', 3) or 3),
        profile_data.get('note'),
    )
    return {'success': True}


@app.delete('/api/admin/production-profiles/{profile_id}')
async def api_delete_production_profile(
    profile_id: int,
    current_username: str = Depends(get_current_username),
):
    delete_production_profile(profile_id)
    return {'success': True}


@app.post('/api/admin/production-batches')
async def api_add_production_batch(
    batch_data: dict,
    current_username: str = Depends(get_current_username),
):
    await create_tables()
    batch_date = parse_date_or_none(batch_data.get('batch_date'))
    if batch_date is None:
        raise HTTPException(status_code=400, detail='batch_date is required')

    seed_weight_kg = float(batch_data.get('seed_weight_kg', 0) or 0)
    yield_percent = float(batch_data.get('yield_percent', 0) or 0)
    output_volume_ml = batch_data.get('output_volume_ml')
    if output_volume_ml in (None, ''):
        output_volume_ml = seed_weight_kg * yield_percent * 10

    batch_id = add_production_batch(
        batch_date,
        batch_data.get('oil_name', ''),
        seed_weight_kg,
        float(batch_data.get('seed_price_per_kg', 0) or 0),
        yield_percent,
        float(output_volume_ml or 0),
        float(batch_data.get('labor_cost', 0) or 0),
        float(batch_data.get('packaging_cost', 0) or 0),
        float(batch_data.get('other_cost', 0) or 0),
        batch_data.get('note'),
    )
    return {'success': True, 'id': batch_id}


@app.delete('/api/admin/production-batches/{batch_id}')
async def api_delete_production_batch(
    batch_id: int,
    current_username: str = Depends(get_current_username),
):
    delete_production_batch(batch_id)
    return {'success': True}


@app.post('/api/admin/upload-pricelist')
async def api_upload_pricelist(request: Request, current_username: str = Depends(get_current_username)):
    try:
        form_data = await request.form()
        pdf_file = form_data.get('pdf_file')

        if pdf_file and pdf_file.filename:
            file_contents = await pdf_file.read()
            filename = pdf_file.filename.replace(' ', '_')
            with open('tmp/' + filename, 'wb') as temp_file:
                temp_file.write(file_contents)

            clear_price_list()
            load_pricelist_from_pdf('tmp/' + filename)
            return {"success": True, "message": "Прайс-лист загружен"}

        raise HTTPException(status_code=400, detail="Файл не выбран")
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.delete('/api/order/{order_id}')
async def api_delete_order(order_id: int, current_username: str = Depends(get_current_username)):
    if is_id_exist(order_id):
        delete_order_dy_id(order_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Заказ не найден")


@app.get('/')
@app.get('/orders')
@app.get('/orders/')
@app.get('/admin')
@app.get('/admin/')
@app.get('/app')
@app.get('/app/')
@app.get('/app/{path:path}')
def serve_frontend(request: Request, path: str = ""):
    return templates.TemplateResponse('index.html', {"request": request})


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
