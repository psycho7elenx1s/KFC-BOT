import os
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import requests
from aiohttp import web
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
dp = Dispatcher()

# Настройки CryptoBot
CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN')
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"

# Путь к файлу базы данных
DB_FILE = 'database.json'

# Загрузка базы данных
def load_db():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # База данных по умолчанию
        return {
            'users': {},
            'orders': {},
            'admins': [int(admin_id) for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id],
            'settings': {}
        }

# Сохранение базы данных
def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

# Классы состояний
class OrderStates(StatesGroup):
    choosing_platform = State()
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    entering_channel = State()
    confirmation = State()

class PaymentStates(StatesGroup):
    choosing_amount = State()
    confirmation = State()

class AdminStates(StatesGroup):
    managing_orders = State()
    adding_admin = State()
    removing_admin = State()
    changing_balance = State()

# Клавиатуры
def get_main_kb(user_id):
    db = load_db()
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🛍️ Заказать услугу"))
    kb.add(KeyboardButton(text="👤 Профиль"))
    kb.add(KeyboardButton(text="🆘 Поддержка"))
    
    if user_id in db['admins']:
        kb.add(KeyboardButton(text="👑 Админ"))
    
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def get_back_kb():
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🔙 Назад"))
    return kb.as_markup(resize_keyboard=True)

# Хендлеры команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    user_id = message.from_user.id
    
    if str(user_id) not in db['users']:
        db['users'][str(user_id)] = {
            'balance': 0,
            'orders': [],
            'registration_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'username': message.from_user.username
        }
        save_db(db)
    
    await message.answer_photo(
        photo="https://example.com/welcome_image.jpg",  # Замените на реальный URL
        caption="👋 Добро пожаловать в бота для продвижения стримов!",
        reply_markup=get_main_kb(user_id)
    )

@dp.message(F.text == "🔙 Назад")
async def cmd_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_kb(message.from_user.id)
    )

# Запуск бота
async def on_startup():
    logger.info("Бот запущен")
    # Здесь можно добавить код для отправки уведомления админам о запуске бота

async def on_shutdown():
    logger.info("Бот остановлен")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Удаляем вебхук (если был)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Для Render: создаем веб-приложение для поддержания бота в активном состоянии
    app = web.Application()
    runner = web.AppRunner(app)
    
    async def keep_alive():
        while True:
            await asyncio.sleep(15 * 60)  # Каждые 15 минут
            try:
                # Простое действие для поддержания активности
                db = load_db()
                if db['admins']:
                    await bot.send_message(db['admins'][0], "🤖 Бот активен!")
            except Exception as e:
                logger.error(f"Keep alive error: {e}")
    
    async def start():
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        asyncio.create_task(keep_alive())
        await main()
    
    asyncio.run(start())
    # Часть 2: Реализация функционала заказа услуг

# Цены на услуги
SERVICE_PRICES = {
    "Подписчики": {"price": 20, "min": 10, "unit": "шт"},
    "Живой чат RU": {"price": 319, "min": 1, "unit": "час"},
    "Живой чат ENG": {"price": 419, "min": 1, "unit": "час"},
    "Зрители": {"price": 1, "min": 10, "unit": "шт"}
}

# Хендлеры для заказа услуг
@dp.message(F.text == "🛍️ Заказать услугу")
async def cmd_order(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🎮 Kick"))
    kb.add(KeyboardButton(text="📺 YouTube"))
    kb.add(KeyboardButton(text="🟣 Twitch"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer_photo(
        photo="https://example.com/order_image.jpg",
        caption="Выберите платформу:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(OrderStates.choosing_platform)

@dp.message(OrderStates.choosing_platform, F.text.in_(["🎮 Kick", "📺 YouTube", "🟣 Twitch"]))
async def process_platform(message: types.Message, state: FSMContext):
    platform_map = {
        "🎮 Kick": "Kick",
        "📺 YouTube": "YouTube",
        "🟣 Twitch": "Twitch"
    }
    await state.update_data(platform=platform_map[message.text])
    
    kb = ReplyKeyboardBuilder()
    for service in SERVICE_PRICES:
        kb.add(KeyboardButton(text=service))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer(
        f"Выбрана платформа: {platform_map[message.text]}\n\nВыберите услугу:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(OrderStates.choosing_service)

@dp.message(OrderStates.choosing_service, F.text.in_(list(SERVICE_PRICES.keys())))
async def process_service(message: types.Message, state: FSMContext):
    service = message.text
    price_info = SERVICE_PRICES[service]
    
    await state.update_data(service=service, price_info=price_info)
    
    # Здесь должна быть логика для календаря, но для упрощения используем текстовый ввод
    await message.answer(
        f"Услуга: {service}\nЦена: {price_info['price']} руб/{price_info['unit']}\n\n"
        "Введите дату стрима в формате ДД.ММ (например, 15.06):",
        reply_markup=get_back_kb())
    )
    await state.set_state(OrderStates.choosing_date)

@dp.message(OrderStates.choosing_date, F.text.regexp(r'^\d{2}\.\d{2}$'))
async def process_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer(
        "Введите время начала стрима в формате ЧЧ:ММ (например, 14:00):",
        reply_markup=get_back_kb())
    )
    await state.set_state(OrderStates.choosing_time)

@dp.message(OrderStates.choosing_time, F.text.regexp(r'^\d{2}:\d{2}$'))
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer(
        "Введите название вашего канала (например, 'MyCoolChannel'):",
        reply_markup=get_back_kb())
    )
    await state.set_state(OrderStates.entering_channel)

@dp.message(OrderStates.entering_channel)
async def process_channel(message: types.Message, state: FSMContext):
    await state.update_data(channel=message.text)
    data = await state.get_data()
    
    # Формируем сообщение с подтверждением
    confirmation_msg = (
        "Подтвердите заказ:\n\n"
        f"1. Платформа: {data['platform']}\n"
        f"2. Услуга: {data['service']} - {data['price_info']['price']} руб/{data['price_info']['unit']}\n"
        f"3. Канал: {data['channel']}\n"
        f"4. Дата стрима: {data['date']}\n"
        f"5. Время начала: {data['time']}\n\n"
        "Сумма к оплате: {data['price_info']['price']} руб"
    )
    
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="✅ Подтвердить"))
    kb.add(KeyboardButton(text="❌ Отменить"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer(
        confirmation_msg,
        reply_markup=kb.as_markup(resize_keyboard=True))
    )
    await state.set_state(OrderStates.confirmation)

@dp.message(OrderStates.confirmation, F.text == "✅ Подтвердить"))
async def confirm_order(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    db = load_db()
    
    # Создаем заказ
    order_id = len(db['orders']) + 1
    db['orders'][str(order_id)] = {
        'user_id': user_id,
        'platform': data['platform'],
        'service': data['service'],
        'channel': data['channel'],
        'date': data['date'],
        'time': data['time'],
        'amount': data['price_info']['price'],
        'status': 'pending_payment',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Добавляем заказ в профиль пользователя
    db['users'][str(user_id)]['orders'].append(order_id)
    save_db(db)
    
    # Предлагаем оплатить
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="💳 Оплатить картой"))
    kb.add(KeyboardButton(text="💰 Оплатить CryptoBot"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer(
        "Заказ создан! Выберите способ оплаты:",
        reply_markup=kb.as_markup(resize_keyboard=True))
    )
    await state.clear()

# Оплата через CryptoBot
@dp.message(F.text == "💰 Оплатить CryptoBot"))
async def pay_with_cryptobot(message: types.Message):
    db = load_db()
    user_id = message.from_user.id
    
    # Находим последний неоплаченный заказ пользователя
    user_orders = [order for order_id, order in db['orders'].items() 
                  if order['user_id'] == user_id and order['status'] == 'pending_payment']
    
    if not user_orders:
        await message.answer("У вас нет заказов для оплаты.")
        return
    
    last_order = user_orders[-1]
    amount = last_order['amount']
    
    # Создаем инвойс в CryptoBot
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "asset": "USDT",  # Или другая валюта
        "description": f"Оплата заказа #{list(db['orders'].keys())[-1]}",
        "hidden_message": f"Оплата заказа {list(db['orders'].keys())[-1]}",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/your_bot",
        "payload": str(user_id)
    }
    
    try:
        response = requests.post(f"{CRYPTO_BOT_API_URL}/createInvoice", headers=headers, json=payload)
        response.raise_for_status()
        invoice = response.json()['result']
        
        # Сохраняем invoice_id в заказе
        db['orders'][str(list(db['orders'].keys())[-1])]['invoice_id'] = invoice['invoice_id']
        save_db(db)
        
        # Отправляем пользователю ссылку на оплату
        await message.answer(
            f"Сумма к оплате: {amount} руб (~{amount / 75:.2f} USDT)\n\n"
            f"Оплатите по ссылке: {invoice['pay_url']}\n\n"
            "После оплаты бот автоматически подтвердит ваш заказ.",
            reply_markup=get_back_kb())
        )
        
        # Запускаем проверку оплаты
        asyncio.create_task(check_payment(invoice['invoice_id'], user_id, list(db['orders'].keys())[-1]))
        
    except Exception as e:
        logger.error(f"CryptoBot error: {e}")
        await message.answer(
            "Произошла ошибка при создании счета. Попробуйте позже или выберите другой способ оплаты.",
            reply_markup=get_back_kb())
        )

async def check_payment(invoice_id, user_id, order_id):
    db = load_db()
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
    }
    
    for _ in range(30):  # Проверяем в течение 15 минут (30 раз по 30 секунд)
        await asyncio.sleep(30)
        
        try:
            response = requests.get(f"{CRYPTO_BOT_API_URL}/getInvoices?invoice_ids={invoice_id}", headers=headers)
            response.raise_for_status()
            invoice = response.json()['result']['items'][0]
            
            if invoice['status'] == 'paid':
                # Обновляем статус заказа
                db['orders'][order_id]['status'] = 'paid'
                db['orders'][order_id]['paid_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_db(db)
                
                # Уведомляем пользователя
                await bot.send_message(
                    user_id,
                    "✅ Оплата прошла успешно! Ваш заказ принят в обработку.",
                    reply_markup=get_main_kb(user_id))
                
                # Уведомляем админов
                for admin_id in db['admins']:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"Новый оплаченный заказ #{order_id} от пользователя @{db['users'][str(user_id)]['username']}")
                    except:
                        continue
                
                return
                
        except Exception as e:
            logger.error(f"Payment check error: {e}")
            continue
    
    # Если оплата не прошла в течение 15 минут
    await bot.send_message(
        user_id,
        "Время на оплату истекло. Если вы произвели оплату, обратитесь в поддержку.",
        reply_markup=get_main_kb(user_id))
        # Часть 3: Реализация профиля и поддержки

@dp.message(F.text == "👤 Профиль"))
async def cmd_profile(message: types.Message):
    db = load_db()
    user_id = message.from_user.id
    user_data = db['users'].get(str(user_id), {})
    
    if not user_data:
        await message.answer("Профиль не найден. Начните с команды /start")
        return
    
    # Статистика заказов
    orders_count = len(user_data['orders'])
    paid_orders = sum(1 for order_id in user_data['orders'] 
                     if db['orders'].get(str(order_id), {}).get('status') == 'paid')
    
    profile_msg = (
        f"👤 Ваш профиль:\n\n"
        f"📅 Дата регистрации: {user_data.get('registration_date', 'неизвестно')}\n"
        f"💰 Баланс: {user_data.get('balance', 0)} руб\n\n"
        f"📊 Статистика заказов:\n"
        f"• Всего заказов: {orders_count}\n"
        f"• Оплаченных: {paid_orders}\n\n"
        f"🆔 Ваш ID: {user_id}"
    )
    
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="💳 Пополнить баланс"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer_photo(
        photo="https://example.com/profile_image.jpg",
        caption=profile_msg,
        reply_markup=kb.as_markup(resize_keyboard=True))
    )

@dp.message(F.text == "💳 Пополнить баланс"))
async def cmd_deposit(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите сумму пополнения в рублях (минимум 100 руб):",
        reply_markup=get_back_kb())
    )
    await state.set_state(PaymentStates.choosing_amount)

@dp.message(PaymentStates.choosing_amount, F.text.regexp(r'^\d+$'))
async def process_deposit_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    
    if amount < 100:
        await message.answer("Минимальная сумма пополнения - 100 руб. Введите другую сумму:")
        return
    
    await state.update_data(amount=amount)
    
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="💳 Оплатить картой"))
    kb.add(KeyboardButton(text="💰 Оплатить CryptoBot"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer(
        f"Сумма пополнения: {amount} руб\n\nВыберите способ оплаты:",
        reply_markup=kb.as_markup(resize_keyboard=True))
    )
    await state.set_state(PaymentStates.confirmation)

@dp.message(PaymentStates.confirmation, F.text == "💰 Оплатить CryptoBot"))
async def deposit_with_cryptobot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    
    # Создаем инвойс в CryptoBot
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "asset": "USDT",
        "description": f"Пополнение баланса на {amount} руб",
        "hidden_message": f"Пополнение баланса пользователя {user_id}",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/your_bot",
        "payload": f"deposit_{user_id}"
    }
    
    try:
        response = requests.post(f"{CRYPTO_BOT_API_URL}/createInvoice", headers=headers, json=payload)
        response.raise_for_status()
        invoice = response.json()['result']
        
        # Отправляем пользователю ссылку на оплату
        await message.answer(
            f"Сумма к оплате: {amount} руб (~{amount / 75:.2f} USDT)\n\n"
            f"Оплатите по ссылке: {invoice['pay_url']}\n\n"
            "После оплаты баланс будет пополнен автоматически.",
            reply_markup=get_back_kb())
        )
        
        # Запускаем проверку оплаты
        asyncio.create_task(check_deposit_payment(invoice['invoice_id'], user_id, amount))
        
    except Exception as e:
        logger.error(f"CryptoBot deposit error: {e}")
        await message.answer(
            "Произошла ошибка при создании счета. Попробуйте позже или выберите другой способ оплаты.",
            reply_markup=get_back_kb())
        )

async def check_deposit_payment(invoice_id, user_id, amount):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
    }
    
    for _ in range(30):  # Проверяем в течение 15 минут
        await asyncio.sleep(30)
        
        try:
            response = requests.get(f"{CRYPTO_BOT_API_URL}/getInvoices?invoice_ids={invoice_id}", headers=headers)
            response.raise_for_status()
            invoice = response.json()['result']['items'][0]
            
            if invoice['status'] == 'paid':
                # Обновляем баланс пользователя
                db = load_db()
                db['users'][str(user_id)]['balance'] = db['users'][str(user_id)].get('balance', 0) + amount
                save_db(db)
                
                # Уведомляем пользователя
                await bot.send_message(
                    user_id,
                    f"✅ Баланс успешно пополнен на {amount} руб!",
                    reply_markup=get_main_kb(user_id))
                
                return
                
        except Exception as e:
            logger.error(f"Deposit check error: {e}")
            continue
    
    # Если оплата не прошла в течение 15 минут
    await bot.send_message(
        user_id,
        "Время на оплату истекло. Если вы произвели оплату, обратитесь в поддержку.",
        reply_markup=get_main_kb(user_id))

@dp.message(F.text == "🆘 Поддержка"))
async def cmd_support(message: types.Message):
    support_msg = (
        "🆘 Поддержка\n\n"
        "Этот бот предназначен для заказа услуг продвижения ваших стримов на различных платформах.\n\n"
        "📌 Как это работает:\n"
        "1. Вы выбираете платформу и услугу\n"
        "2. Указываете детали заказа\n"
        "3. Оплачиваете удобным способом\n"
        "4. Мы выполняем ваш заказ в указанное время\n\n"
        "❓ Если у вас возникли вопросы или проблемы:\n"
        "• Напишите нам в поддержку: @support_username\n"
        "• Или на email: support@example.com\n\n"
        "⏳ Время ответа: обычно в течение 1 часа в рабочее время (10:00-20:00 МСК)"
    )
    
    await message.answer_photo(
        photo="https://example.com/support_image.jpg",
        caption=support_msg,
        reply_markup=get_back_kb())
    )
    # Часть 4: Реализация админ-панели

@dp.message(F.text == "👑 Админ"))
async def cmd_admin(message: types.Message):
    db = load_db()
    user_id = message.from_user.id
    
    if user_id not in db['admins']:
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="📊 Статистика бота"))
    kb.add(KeyboardButton(text="📦 Управление заказами"))
    kb.add(KeyboardButton(text="👥 Назначить админа"))
    kb.add(KeyboardButton(text="👥 Снять админа"))
    kb.add(KeyboardButton(text="💰 Изменить баланс"))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer_photo(
        photo="https://example.com/admin_image.jpg",
        caption="👑 Админ-панель",
        reply_markup=kb.as_markup(resize_keyboard=True))
    )

@dp.message(F.text == "📊 Статистика бота"))
async def cmd_bot_stats(message: types.Message):
    db = load_db()
    
    total_users = len(db['users'])
    total_orders = len(db['orders'])
    paid_orders = sum(1 for order in db['orders'].values() if order['status'] == 'paid')
    total_revenue = sum(order['amount'] for order in db['orders'].values() if order['status'] == 'paid')
    
    stats_msg = (
        "📊 Статистика бота:\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"💰 Оплаченных заказов: {paid_orders}\n"
        f"💵 Общая выручка: {total_revenue} руб\n\n"
        f"🔄 Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await message.answer(stats_msg, reply_markup=get_back_kb())

@dp.message(F.text == "📦 Управление заказами"))
async def cmd_manage_orders(message: types.Message, state: FSMContext):
    db = load_db()
    
    if not db['orders']:
        await message.answer("Нет заказов для управления.")
        return
    
    # Создаем клавиатуру с заказами
    kb = InlineKeyboardBuilder()
    for order_id, order in list(db['orders'].items())[-10:]:  # Последние 10 заказов
        kb.add(InlineKeyboardButton(
            text=f"#{order_id} - {order['status']}",
            callback_data=f"order_{order_id}"))
    
    kb.adjust(1)
    await message.answer(
        "Выберите заказ для управления:",
        reply_markup=kb.as_markup())
    )
    await state.set_state(AdminStates.managing_orders)

@dp.callback_query(F.data.startswith("order_"), AdminStates.managing_orders)
async def process_order_selection(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[1]
    db = load_db()
    order = db['orders'].get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    user = db['users'].get(str(order['user_id']), {})
    username = user.get('username', 'неизвестно')
    
    order_msg = (
        f"📦 Заказ #{order_id}\n\n"
        f"👤 Пользователь: @{username} (ID: {order['user_id']})\n"
        f"🛒 Услуга: {order['service']}\n"
        f"🖥 Платформа: {order['platform']}\n"
        f"📺 Канал: {order['channel']}\n"
        f"📅 Дата: {order['date']}\n"
        f"⏰ Время: {order['time']}\n"
        f"💰 Сумма: {order['amount']} руб\n"
        f"📌 Статус: {order['status']}\n"
        f"🕒 Создан: {order['created_at']}"
    )
    
    # Кнопки для изменения статуса
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{order_id}"))
    kb.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"))
    kb.add(InlineKeyboardButton(text="🔄 В процессе", callback_data=f"process_{order_id}"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_orders"))
    kb.adjust(2)
    
    await callback.message.edit_text(order_msg, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith(("confirm_", "reject_", "process_")), AdminStates.managing_orders)
async def process_order_status_change(callback: types.CallbackQuery):
    action, order_id = callback.data.split("_")
    db = load_db()
    order = db['orders'].get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    status_map = {
        "confirm": "completed",
        "reject": "rejected",
        "process": "in_progress"
    }
    
    order['status'] = status_map[action]
    save_db(db)
    
    # Уведомляем пользователя
    try:
        status_messages = {
            "completed": "✅ Ваш заказ #{} выполнен!",
            "rejected": "❌ Ваш заказ #{} отклонен. Для уточнений обратитесь в поддержку.",
            "in_progress": "🔄 Ваш заказ #{} взят в работу."
        }
        await bot.send_message(
            order['user_id'],
            status_messages[status_map[action]].format(order_id))
    except:
        pass
    
    await callback.answer(f"Статус заказа #{order_id} изменен на {order['status']}")
    await cmd_manage_orders(callback.message, callback.message.from_user.id)

@dp.message(F.text == "👥 Назначить админа"))
async def cmd_add_admin(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите ID пользователя, которого хотите назначить админом:",
        reply_markup=get_back_kb())
    )
    await state.set_state(AdminStates.adding_admin)

@dp.message(AdminStates.adding_admin, F.text.regexp(r'^\d+$'))
async def process_add_admin(message: types.Message, state: FSMContext):
    db = load_db()
    new_admin_id = int(message.text)
    
    if new_admin_id in db['admins']:
        await message.answer("Этот пользователь уже является админом.")
        return
    
    db['admins'].append(new_admin_id)
    save_db(db)
    
    await message.answer(f"Пользователь {new_admin_id} назначен админом.")
    await state.clear()
    await cmd_admin(message)

@dp.message(F.text == "👥 Снять админа"))
async def cmd_remove_admin(message: types.Message, state: FSMContext):
    db = load_db()
    
    if len(db['admins']) <= 1:
        await message.answer("Нельзя снять последнего админа!")
        return
    
    kb = ReplyKeyboardBuilder()
    for admin_id in db['admins']:
        if admin_id != message.from_user.id:  # Нельзя снять себя
            kb.add(KeyboardButton(text=str(admin_id)))
    kb.add(KeyboardButton(text="🔙 Назад"))
    kb.adjust(2)
    
    await message.answer(
        "Выберите ID админа, которого хотите снять:",
        reply_markup=kb.as_markup(resize_keyboard=True))
    )
    await state.set_state(AdminStates.removing_admin)

@dp.message(AdminStates.removing_admin, F.text.regexp(r'^\d+$'))
async def process_remove_admin(message: types.Message, state: FSMContext):
    db = load_db()
    admin_id = int(message.text)
    
    if admin_id not in db['admins']:
        await message.answer("Этот пользователь не является админом.")
        return
    
    if admin_id == message.from_user.id:
        await message.answer("Вы не можете снять себя. Обратитесь к другому админу.")
        return
    
    db['admins'].remove(admin_id)
    save_db(db)
    
    await message.answer(f"Пользователь {admin_id} больше не админ.")
    await state.clear()
    await cmd_admin(message)

@dp.message(F.text == "💰 Изменить баланс"))
async def cmd_change_balance(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите ID пользователя и сумму через пробел (например, '123456 500' для пополнения или '123456 -500' для списания):",
        reply_markup=get_back_kb())
    )
    await state.set_state(AdminStates.changing_balance)

@dp.message(AdminStates.changing_balance, F.text.regexp(r'^\d+\s+-?\d+$'))
async def process_change_balance(message: types.Message, state: FSMContext):
    user_id, amount = message.text.split()
    user_id = int(user_id)
    amount = int(amount)
    
    db = load_db()
    if str(user_id) not in db['users']:
        await message.answer("Пользователь не найден.")
        return
    
    current_balance = db['users'][str(user_id)].get('balance', 0)
    new_balance = current_balance + amount
    
    if new_balance < 0:
        await message.answer("Нельзя установить отрицательный баланс.")
        return
    
    db['users'][str(user_id)]['balance'] = new_balance
    save_db(db)
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            f"Ваш баланс был изменен администратором.\n"
            f"Изменение: {'+' if amount >= 0 else ''}{amount} руб\n"
            f"Новый баланс: {new_balance} руб")
    except:
        pass
    
    await message.answer(
        f"Баланс пользователя {user_id} изменен.\n"
        f"Старый баланс: {current_balance} руб\n"
        f"Изменение: {'+' if amount >= 0 else ''}{amount} руб\n"
        f"Новый баланс: {new_balance} руб")
    
    await state.clear()
    await cmd_admin(message)
    # Обработка ошибок
@dp.error()
async def error_handler(event: types.Update, exception: Exception):
    logger.error(f"Ошибка: {exception}", exc_info=True)
    
    # Перезагрузка бота при критических ошибках
    if isinstance(exception, (KeyboardInterrupt, SystemExit)):
        raise exception
    
    # Уведомление админов об ошибке
    db = load_db()
    for admin_id in db['admins']:
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ Произошла ошибка в боте:\n\n{str(exception)[:3000]}")
        except:
            continue
    
    # Перезапуск бота через 5 секунд
    await asyncio.sleep(5)
    await dp.start_polling(bot, skip_updates=True)
    # Запускаем поллинг с авто-рестартом
    while True:
        try:
            await dp.start_polling(bot, skip_updates=True)
        except Exception as e:
            print(f"Ошибка: {e}\nПерезапуск через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Для Render: просто вызываем main()
    asyncio.run(main())
