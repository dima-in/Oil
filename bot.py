"""
Модуль Telegram-бота для системы заказа масел.
Предоставляет интерфейс для просмотра каталога, оформления заказов и управления ими через Telegram.
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from Catalog import get_oil_catalog, add_price_data_to_table
from Customer import Customer
from OilOrder import OilOrder
from OrderItem import OrderItem
from Database import (
    create_tables, insert_statuses_to_database, save_status, 
    get_status_name, save_order_details, save_order, 
    save_customer, get_customer_by_phone, select_all_orders, 
    is_id_exist, delete_order_by_id
)
from AvitoParser import update_prices_from_avito

# Загрузка переменных окружения
load_dotenv()

# Токен бота из переменных окружения
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


class OrderState(StatesGroup):
    """Машина состояний для процесса оформления заказа."""
    waiting_for_name = State()
    waiting_for_surname = State()
    waiting_for_phone = State()
    waiting_for_address = State()
    waiting_for_product_selection = State()
    waiting_for_shipping_date = State()
    waiting_for_status = State()


# Инициализация бота и диспетчера (токен будет установлен при запуске)
bot: Bot | None = None
dp = Dispatcher()

def init_bot(token: str):
    """Инициализация бота с токеном."""
    global bot
    bot = Bot(token=token)
    return bot

# Хранилище данных сессии пользователей
user_sessions: Dict[int, Dict[str, Any]] = {}


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры бота."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Каталог")],
            [KeyboardButton(text="🛒 Оформить заказ")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="📞 Контакты")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_catalog_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора товаров из каталога."""
    catalog = get_oil_catalog()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Группируем товары по названию
    products_dict = {}
    for oil_name, volume, price in catalog:
        if oil_name not in products_dict:
            products_dict[oil_name] = []
        products_dict[oil_name].append((volume, price))
    
    for oil_name, variants in products_dict.items():
        for volume, price in variants:
            btn_text = f"{oil_name} ({volume}мл) - {price}₽"
            callback_data = f"add_{oil_name}_{volume}_{price}"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=btn_text, callback_data=callback_data)
            ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="✅ Завершить выбор", callback_data="finish_selection")
    ])
    
    return keyboard


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора статуса заказа."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Новый", callback_data="status_0")],
            [InlineKeyboardButton(text="Получена предоплата", callback_data="status_1")],
            [InlineKeyboardButton(text="Avito доставка", callback_data="status_2")],
            [InlineKeyboardButton(text="Ozon", callback_data="status_3")],
            [InlineKeyboardButton(text="Завершен", callback_data="status_4")],
            [InlineKeyboardButton(text="Готов к выдаче", callback_data="status_5")],
            [InlineKeyboardButton(text="Отменен", callback_data="status_6")],
            [InlineKeyboardButton(text="Ожидает предоплаты", callback_data="status_7")],
        ]
    )
    return keyboard


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start - приветствие и главное меню."""
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в систему заказа масел!\n"
        "Выберите действие из меню ниже:",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help - справка по боту."""
    help_text = (
        "📖 **Команды бота:**\n\n"
        "/start - Запустить бота и показать главное меню\n"
        "/catalog - Показать каталог масел\n"
        "/order - Начать оформление заказа\n"
        "/myorders - Просмотреть мои заказы\n"
        "/contacts - Контактная информация\n"
        "/help - Эта справка\n\n"
        "Также вы можете использовать кнопки в главном меню."
    )
    await message.answer(help_text)


@dp.message(Command("catalog"))
@dp.message(lambda message: message.text == "📖 Каталог")
async def show_catalog(message: types.Message):
    """Показ каталога масел."""
    await add_price_data_to_table()
    catalog = get_oil_catalog()
    
    if not catalog:
        await message.answer("❌ Каталог пуст.")
        return
    
    # Группируем товары по названию
    products_dict = {}
    for oil_name, volume, price in catalog:
        if oil_name not in products_dict:
            products_dict[oil_name] = []
        products_dict[oil_name].append((volume, price))
    
    catalog_text = "📖 **Каталог масел:**\n\n"
    for oil_name, variants in products_dict.items():
        catalog_text += f"🛢 **{oil_name}**:\n"
        for volume, price in variants:
            catalog_text += f"  • {volume}мл - {price}₽\n"
        catalog_text += "\n"
    
    await message.answer(
        catalog_text,
        reply_markup=get_catalog_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(Command("order"))
@dp.message(lambda message: message.text == "🛒 Оформить заказ")
async def start_order(message: types.Message, state: FSMContext):
    """Начало оформления заказа."""
    await message.answer(
        "🛒 **Оформление заказа**\n\n"
        "Давайте начнем! Введите ваше **имя**:",
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.waiting_for_name)
    user_sessions[message.from_user.id] = {"cart": []}


@dp.message(OrderState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """Обработка имени клиента."""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Пожалуйста, введите корректное имя:")
        return
    
    await state.update_data(name=name)
    user_sessions[message.from_user.id]["name"] = name
    
    await message.answer(f"✅ Имя принято: {name}\n\nТеперь введите вашу **фамилию**:", parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_surname)


@dp.message(OrderState.waiting_for_surname)
async def process_surname(message: types.Message, state: FSMContext):
    """Обработка фамилии клиента."""
    surname = message.text.strip()
    if len(surname) < 2:
        await message.answer("❌ Фамилия слишком короткая. Пожалуйста, введите корректную фамилию:")
        return
    
    await state.update_data(surname=surname)
    user_sessions[message.from_user.id]["surname"] = surname
    
    await message.answer(f"✅ Фамилия принята: {surname}\n\nТеперь введите ваш **номер телефона** (например, +79991234567):", parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_phone)


@dp.message(OrderState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Обработка номера телефона клиента."""
    phone = message.text.strip()
    if len(phone) < 10:
        await message.answer("❌ Номер телефона слишком короткий. Пожалуйста, введите корректный номер:")
        return
    
    await state.update_data(phone=phone)
    user_sessions[message.from_user.id]["phone"] = phone
    
    # Проверяем, есть ли клиент в базе
    existing_customer = await get_customer_by_phone(phone)
    if existing_customer:
        await message.answer(
            f"✅ Клиент найден в базе!\n\n"
            f"Имя: {existing_customer[1]} {existing_customer[2]}\n"
            f"Телефон: {existing_customer[3]}\n\n"
            "Введите **адрес доставки**:",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"✅ Телефон принят: {phone}\n\nВведите **адрес доставки**:", parse_mode="Markdown")
    
    await state.set_state(OrderState.waiting_for_address)


@dp.message(OrderState.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    """Обработка адреса доставки."""
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("❌ Адрес слишком короткий. Пожалуйста, введите корректный адрес:")
        return
    
    await state.update_data(address=address)
    user_sessions[message.from_user.id]["address"] = address
    
    await message.answer(
        "✅ Адрес принят.\n\n"
        "Теперь выберите товары из каталога, нажимая на кнопки ниже.\n"
        "Когда закончите выбор, нажмите '✅ Завершить выбор':",
        reply_markup=get_catalog_keyboard()
    )
    await state.set_state(OrderState.waiting_for_product_selection)


@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_product_to_cart(callback: types.CallbackQuery, state: FSMContext):
    """Добавление товара в корзину."""
    data = callback.data.split("_")
    oil_name = "_".join(data[1:-3])  # Название может содержать подчеркивания
    volume = int(data[-3])
    price = float(data[-2])
    
    # Получаем текущую корзину
    user_data = await state.get_data()
    cart = user_sessions.get(callback.from_user.id, {}).get("cart", [])
    
    # Добавляем товар
    cart.append({
        "oil_name": oil_name,
        "volume": volume,
        "price": price,
        "count": 1
    })
    user_sessions[callback.from_user.id]["cart"] = cart
    
    await callback.answer(f"✅ Добавлено: {oil_name} ({volume}мл)", show_alert=False)
    
    # Показываем текущий состав корзины
    cart_text = "🛒 **Ваша корзина:**\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        item_total = item["price"] * item["count"]
        total += item_total
        cart_text += f"{i}. {item['oil_name']} ({item['volume']}мл) x{item['count']} - {item_total}₽\n"
    cart_text += f"\n💰 **Итого: {total}₽**"
    
    await callback.message.answer(cart_text, parse_mode="Markdown")


@dp.callback_query(lambda c: c.data == "finish_selection")
async def finish_selection(callback: types.CallbackQuery, state: FSMContext):
    """Завершение выбора товаров."""
    user_data = await state.get_data()
    cart = user_sessions.get(callback.from_user.id, {}).get("cart", [])
    
    if not cart:
        await callback.answer("❌ Корзина пуста! Выберите хотя бы один товар.", show_alert=True)
        return
    
    # Рассчитываем общую сумму
    total = sum(item["price"] * item["count"] for item in cart)
    
    cart_text = "🛒 **Ваш заказ:**\n\n"
    for i, item in enumerate(cart, 1):
        item_total = item["price"] * item["count"]
        cart_text += f"{i}. {item['oil_name']} ({item['volume']}мл) x{item['count']} - {item_total}₽\n"
    cart_text += f"\n💰 **Итого: {total}₽**\n\n"
    cart_text += "Введите **дату доставки** в формате ГГГГ-ММ-ДД (например, 2024-01-15):"
    
    await callback.message.answer(cart_text, parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_shipping_date)


@dp.message(OrderState.waiting_for_shipping_date)
async def process_shipping_date(message: types.Message, state: FSMContext):
    """Обработка даты доставки."""
    shipping_date_str = message.text.strip()
    
    try:
        shipping_date = datetime.strptime(shipping_date_str, "%Y-%m-%d")
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Пожалуйста, введите дату в формате ГГГГ-ММ-ДД (например, 2024-01-15):"
        )
        return
    
    await state.update_data(shipping_date=shipping_date_str)
    user_sessions[message.from_user.id]["shipping_date"] = shipping_date
    
    await message.answer(
        f"✅ Дата доставки принята: {shipping_date_str}\n\n"
        "Выберите статус заказа:",
        reply_markup=get_status_keyboard()
    )
    await state.set_state(OrderState.waiting_for_status)


@dp.callback_query(lambda c: c.data.startswith("status_"))
async def process_status(callback: types.CallbackQuery, state: FSMContext):
    """Обработка статуса заказа и сохранение заказа в БД."""
    status_code = int(callback.data.split("_")[1])
    
    # Получаем все данные из состояния
    user_data = await state.get_data()
    session_data = user_sessions.get(callback.from_user.id, {})
    
    name = user_data.get("name", session_data.get("name"))
    surname = user_data.get("surname", session_data.get("surname"))
    phone = user_data.get("phone", session_data.get("phone"))
    address = user_data.get("address", session_data.get("address"))
    shipping_date_str = user_data.get("shipping_date", session_data.get("shipping_date"))
    cart = session_data.get("cart", [])
    
    if not all([name, surname, phone, address, shipping_date_str, cart]):
        await callback.answer("❌ Ошибка: недостаточно данных для оформления заказа.", show_alert=True)
        await state.clear()
        return
    
    # Создаем таблицы и статусы если нужно
    await create_tables()
    await insert_statuses_to_database()
    
    # Проверяем/создаем клиента
    existing_customer = await get_customer_by_phone(phone)
    if existing_customer is None:
        customer_id = await save_customer(address, name, surname, phone)
    else:
        customer_id = existing_customer[0]
    
    # Создаем объект клиента
    customer = Customer(id=customer_id, name=name, surname=surname, phone=phone, address=address)
    
    # Создаем заказ
    order_date = datetime.now()
    shipping_date = datetime.strptime(shipping_date_str, "%Y-%m-%d")
    order = OilOrder(customer, data=order_date, shipping_date=shipping_date)
    
    # Добавляем товары в заказ
    for item in cart:
        product = OrderItem(
            oil_name=item["oil_name"],
            volume=item["volume"],
            count=item["count"],
            price=item["price"]
        )
        order.add_bottle(product)
    
    # Сохраняем заказ
    order_id = await save_order(customer_id, order_date, order, shipping_date, status_code)
    
    # Сохраняем детали заказа
    for product in order.order_details:
        await save_order_details(order_id, product)
    
    # Получаем имя статуса и сохраняем его
    status_name = await get_status_name(status_code)
    await save_status(order_id, status_code, status_name)
    
    # Формируем подтверждение
    confirmation_text = (
        f"✅ **Заказ успешно оформлен!**\n\n"
        f"📦 Номер заказа: #{order_id}\n"
        f"👤 Клиент: {name} {surname}\n"
        f"📞 Телефон: {phone}\n"
        f"📍 Адрес: {address}\n"
        f"📅 Дата доставки: {shipping_date_str}\n"
        f"📊 Статус: {status_name}\n\n"
        f"🛒 **Товары:**\n"
    )
    
    total = 0
    for item in order.order_details:
        item_total = item.price * item.count
        total += item_total
        confirmation_text += f"• {item.oil_name} ({item.volume}мл) x{item.count} - {item_total}₽\n"
    
    confirmation_text += f"\n💰 **Итого к оплате: {total}₽**"
    
    await callback.message.answer(confirmation_text, parse_mode="Markdown")
    
    # Очищаем состояние и сессию
    await state.clear()
    if callback.from_user.id in user_sessions:
        del user_sessions[callback.from_user.id]


@dp.message(Command("myorders"))
@dp.message(lambda message: message.text == "📋 Мои заказы")
async def show_my_orders(message: types.Message):
    """Показ всех заказов пользователя."""
    orders = select_all_orders()
    
    if not orders:
        await message.answer("📋 У вас пока нет заказов.")
        return
    
    # Группируем заказы по ID
    orders_dict = {}
    for order in orders:
        order_id = order[0]  # ID заказа
        if order_id not in orders_dict:
            orders_dict[order_id] = {
                "order": order,
                "details": []
            }
        orders_dict[order_id]["details"].append(order)
    
    orders_text = "📋 **Ваши заказы:**\n\n"
    for order_id, data in orders_dict.items():
        order = data["order"]
        details = data["details"]
        
        orders_text += f"📦 **Заказ #{order_id}**\n"
        orders_text += f"👤 Клиент: {order[6]} {order[7]}\n"  # name, surname
        orders_text += f"📞 Телефон: {order[8]}\n"  # phone
        orders_text += f"📍 Адрес: {order[9]}\n"  # address
        orders_text += f"📅 Дата заказа: {order[2]}\n"  # date
        orders_text += f"🚚 Дата доставки: {order[3]}\n"  # shipping_date
        orders_text += f"💰 Общая сумма: {order[4]}₽\n"  # total_price
        
        # Последний статус
        statuses = [d for d in details if d[17]]  # Assuming status name is at index 17
        if statuses:
            latest_status = statuses[-1]
            orders_text += f"📊 Статус: {latest_status[17]}\n"  # status name
        
        orders_text += "\n**Товары:**\n"
        for detail in details:
            orders_text += f"• {detail[10]} ({detail[11]}мл) x{detail[12]} - {detail[13]}₽\n"  # oil_name, volume, count, price
        
        orders_text += "\n" + "-" * 30 + "\n\n"
    
    await message.answer(orders_text, parse_mode="Markdown")


@dp.message(Command("contacts"))
@dp.message(lambda message: message.text == "📞 Контакты")
async def show_contacts(message: types.Message):
    """Показ контактной информации."""
    contacts_text = (
        "📞 **Контактная информация**\n\n"
        "🏢 Компания: OilPress\n"
        "📧 Email: info@oilpress.ru\n"
        "📱 Телефон: +7 (999) 123-45-67\n"
        "🌐 Сайт: https://oilpress.ru\n"
        "📍 Адрес: г. Москва, ул. Примерная, д. 1\n\n"
        "⏰ Режим работы:\n"
        "Пн-Пт: 9:00 - 18:00\n"
        "Сб-Вс: Выходной"
    )
    await message.answer(contacts_text, parse_mode="Markdown")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Админ-панель для управления заказами (только для авторизованных)."""
    # Здесь можно добавить проверку прав доступа
    admin_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Все заказы")],
            [KeyboardButton(text="❌ Удалить заказ")],
            [KeyboardButton(text="💰 Обновить цены из Avito")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 **Панель администратора**\n\nВыберите действие:", reply_markup=admin_keyboard, parse_mode="Markdown")


@dp.message(lambda message: message.text == "💰 Обновить цены из Avito")
async def update_prices_from_avito_handler(message: types.Message):
    """Обработчик обновления цен из Avito."""
    status_message = await message.answer("⏳ Начинаю обновление цен с Avito...")
    
    try:
        updated_count = await update_prices_from_avito()
        
        if updated_count > 0:
            await status_message.edit_text(
                f"✅ Успешно обновлено цен: {updated_count}\n\n"
                f"Цены актуализированы согласно данным с Avito."
            )
        else:
            await status_message.edit_text(
                "⚠️ Не удалось найти новые цены на Avito.\n\n"
                "Возможно, товары не найдены или изменилась структура сайта."
            )
    except Exception as e:
        await status_message.edit_text(f"❌ Ошибка при обновлении цен: {str(e)}")
        print(f"Ошибка обновления цен: {e}")


async def main():
    """Запуск бота."""
    # Проверка токена
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не настроен!")
        print("Получите токен у @BotFather и установите его в переменную окружения TELEGRAM_BOT_TOKEN")
        print("Или создайте файл .env с содержимым: TELEGRAM_BOT_TOKEN=ваш_токен")
        return
    
    # Инициализация бота
    init_bot(BOT_TOKEN)
    
    # Создание таблиц базы данных
    await create_tables()
    await insert_statuses_to_database()
    
    print("✅ Бот запущен! Токен настроен корректно.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
