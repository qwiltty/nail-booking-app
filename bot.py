import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile
)

from app.config import (
    BOT_TOKEN,
    MASTER_TELEGRAM_ID,
    MASTER_NAME,
    STUDIO_ADDRESS,
    UPLOAD_DIR,
    REMOVE_REMAINING_SLOTS_ON_TODAY_BOOKING,
    ONE_CLIENT_PER_DAY
)
from app.database import (
    init_db,
    get_all_services,
    get_service_by_id,
    get_available_dates,
    get_slots_by_date,
    create_booking,
    add_or_toggle_slot,
    delete_slot,
    get_all_bookings,
    update_booking_status
)

load_dotenv()

# Инициализация бота
if not BOT_TOKEN:
    print("\n" + "!" * 60)
    print("ВНИМАНИЕ: BOT_TOKEN не указан в файле .env!")
    print("Откройте .env и укажите токен от @BotFather перед запуском.")
    print("!" * 60 + "\n")

# Поддержка прокси (для обхода ограничений провайдеров в РФ)
from aiogram.client.session.aiohttp import AiohttpSession
PROXY_URL = os.getenv("PROXY", "").strip()

if PROXY_URL:
    print(f"🌐 Используется прокси: {PROXY_URL}")
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN if BOT_TOKEN else "123456:dummy", session=session)
else:
    bot = Bot(token=BOT_TOKEN if BOT_TOKEN else "123456:dummy")

dp = Dispatcher(storage=MemoryStorage())

# FSM состояния для записи клиента
class BookingState(StatesGroup):
    service = State()
    date = State()
    slot = State()
    name = State()
    phone = State()
    comment = State()
    photo = State()
    confirm = State()

# FSM состояния для мастера (добавление слотов)
class AdminSlotState(StatesGroup):
    choose_date = State()
    choose_time = State()
    custom_time = State()

# --- КЛАВИАТУРЫ ---

def get_main_menu(is_master: bool = False):
    buttons = [
        [InlineKeyboardButton(text="💅 Записаться на ноготочки", callback_data="client_start_booking")],
        [InlineKeyboardButton(text="📋 Прайс-лист", callback_data="client_view_price")],
        [InlineKeyboardButton(text="📍 Адрес и информация", callback_data="client_view_info")]
    ]
    if is_master:
        buttons.append([InlineKeyboardButton(text="⚙️ Кабинет мастера (слоты)", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_kb():
    services = get_all_services()
    buttons = []
    for s in services:
        btn_text = f"{s['category']}: {s['title']} ({s['price']})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv_{s['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_dates_kb(dates: list):
    buttons = []
    weekdays_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months_ru = ["", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

    row = []
    for d_str in dates[:12]:
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        w = weekdays_ru[dt.weekday()]
        m = months_ru[dt.month]
        btn_text = f"{w}, {dt.day} {m}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"date_{d_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад к услугам", callback_data="client_start_booking")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_slots_kb(slots: list):
    buttons = []
    row = []
    for s in slots:
        btn_text = f"⏰ {s['slot_time']}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s['id']}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Выбрать другой день", callback_data="back_to_dates")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ХЭНДЛЕРЫ КЛИЕНТА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    is_master = str(message.from_user.id) == str(MASTER_TELEGRAM_ID)

    welcome_text = (
        f"🌿 <b>Добро пожаловать!</b>\n\n"
        f"Я персональный бот для онлайн-записи к мастеру ногтевого сервиса.\n\n"
        f"✨ <b>АКТУАЛЬНЫЙ ПРАЙС:</b>\n"
        f"💅 <b>МАНИКЮР</b>\n"
        f"• С покрытием — <b>1 200 ₽</b>\n"
        f"• С покрытием + дизайн — <b>от 1 200 ₽</b>\n"
        f"<i>(цена зависит от сложности дизайна)</i>\n\n"
        f"🌸 <b>НАРАЩИВАНИЕ</b>\n"
        f"• Без дизайна — <b>1 800 ₽</b>\n"
        f"• С дизайном — <b>от 1 800 ₽</b>\n"
        f"<i>(цена зависит от сложности дизайна)</i>\n\n"
        f"Выберите действие ниже 👇"
    )

    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu(is_master))

@dp.callback_query(F.data == "back_to_main")
async def cb_back_to_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    is_master = str(cb.from_user.id) == str(MASTER_TELEGRAM_ID)
    await cb.message.edit_text("Главное меню 👇", reply_markup=get_main_menu(is_master))

@dp.callback_query(F.data == "client_view_price")
async def cb_view_price(cb: types.CallbackQuery):
    price_text = (
        f"💅 <b>ПРАЙС-ЛИСТ НА УСЛУГИ:</b>\n\n"
        f"<b>МАНИКЮР</b>\n"
        f"• С покрытием ........................ <b>1 200 ₽</b>\n"
        f"• С покрытием + дизайн ............... <b>от 1 200 ₽</b>\n"
        f"<i>цена зависит от сложности дизайна</i>\n\n"
        f"<b>НАРАЩИВАНИЕ</b>\n"
        f"• Без дизайна ........................ <b>1 800 ₽</b>\n"
        f"• С дизайном ......................... <b>от 1 800 ₽</b>\n"
        f"<i>цена зависит от сложности дизайна</i>\n\n"
        f"🌿 Стерильный инструмент, качественные материалы, бережное отношение к вашим ногтям."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💅 Записаться сейчас", callback_data="client_start_booking")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    await cb.message.edit_text(price_text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "client_view_info")
async def cb_view_info(cb: types.CallbackQuery):
    info_text = (
        f"📍 <b>ИНФОРМАЦИЯ И АДРЕС:</b>\n\n"
        f"🏡 <b>Локация:</b> {STUDIO_ADDRESS}\n"
        f"☕️ Уютная домашняя атмосфера, чай, кофе и приятные фильмы.\n\n"
        f"📌 <b>Правила записи:</b>\n"
        f"• Пожалуйста, приходите вовремя.\n"
        f"• Если не получается прийти — предупредите заранее, чтобы освободить окошко другим."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💅 Перейти к записи", callback_data="client_start_booking")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    await cb.message.edit_text(info_text, parse_mode="HTML", reply_markup=kb)

# --- ПРОЦЕСС ЗАПИСИ (FSM) ---

@dp.callback_query(F.data == "client_start_booking")
async def cb_start_booking(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(BookingState.service)
    await cb.message.edit_text(
        "🌸 <b>Шаг 1 из 5: Выберите желаемую услугу:</b>",
        parse_mode="HTML",
        reply_markup=get_services_kb()
    )

@dp.callback_query(BookingState.service, F.data.startswith("srv_"))
async def cb_choose_service(cb: types.CallbackQuery, state: FSMContext):
    srv_id = int(cb.data.split("_")[1])
    srv = get_service_by_id(srv_id)
    if not srv:
        await cb.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(service_id=srv_id, service_title=srv["title"], service_price=srv["price"], service_category=srv["category"])

    # Получаем даты со свободными окошками
    dates = get_available_dates(days_ahead=21)
    if not dates:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]])
        await cb.message.edit_text("😔 К сожалению, на ближайшие дни пока нет свободных окошек.\nЗагляните чуть позже!", reply_markup=kb)
        await state.clear()
        return

    await state.set_state(BookingState.date)
    await cb.message.edit_text(
        f"Вы выбрали: <b>{srv['category']} — {srv['title']} ({srv['price']})</b>\n\n"
        f"📅 <b>Шаг 2 из 5: Выберите подходящую дату:</b>",
        parse_mode="HTML",
        reply_markup=get_dates_kb(dates)
    )

@dp.callback_query(BookingState.date, F.data.startswith("date_"))
async def cb_choose_date(cb: types.CallbackQuery, state: FSMContext):
    chosen_date = cb.data.replace("date_", "")
    slots = get_slots_by_date(chosen_date, for_admin=False)

    if not slots:
        await cb.answer("На этот день уже нет свободных мест", show_alert=True)
        return

    await state.update_data(slot_date=chosen_date)
    await state.set_state(BookingState.slot)

    dt = datetime.strptime(chosen_date, "%Y-%m-%d")
    months_ru = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    date_formatted = f"{dt.day} {months_ru[dt.month]}"

    await cb.message.edit_text(
        f"📅 Дата: <b>{date_formatted}</b>\n\n"
        f"⏰ <b>Шаг 3 из 5: Выберите удобное время:</b>",
        parse_mode="HTML",
        reply_markup=get_slots_kb(slots)
    )

@dp.callback_query(F.data == "back_to_dates")
async def cb_back_to_dates(cb: types.CallbackQuery, state: FSMContext):
    dates = get_available_dates()
    await state.set_state(BookingState.date)
    await cb.message.edit_text("📅 <b>Выберите дату:</b>", parse_mode="HTML", reply_markup=get_dates_kb(dates))

@dp.callback_query(BookingState.slot, F.data.startswith("slot_"))
async def cb_choose_slot(cb: types.CallbackQuery, state: FSMContext):
    slot_id = int(cb.data.split("_")[1])
    data = await state.get_data()
    slots = get_slots_by_date(data["slot_date"])
    slot_obj = next((s for s in slots if s["id"] == slot_id), None)

    if not slot_obj:
        await cb.answer("Это время уже заняли!", show_alert=True)
        return

    await state.update_data(slot_id=slot_id, slot_time=slot_obj["slot_time"])
    await state.set_state(BookingState.name)

    # Предлагаем имя из профиля
    default_name = cb.from_user.first_name or ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оставить «{default_name}»", callback_data="name_use_tg")]
    ]) if default_name else None

    await cb.message.edit_text(
        f"⏰ Время: <b>{slot_obj['slot_time']}</b>\n\n"
        f"👤 <b>Шаг 4 из 5: Как вас зовут?</b>\n"
        f"Напишите ваше имя сообщением:",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(BookingState.name, F.data == "name_use_tg")
async def cb_use_tg_name(cb: types.CallbackQuery, state: FSMContext):
    name = cb.from_user.first_name or "Клиент"
    await state.update_data(client_name=name)
    await state.set_state(BookingState.phone)
    await cb.message.edit_text(
        f"Приятно познакомиться, {name}!\n\n"
        f"📱 <b>Введите ваш номер телефона</b> для связи\n"
        f"(например: <code>+79991234567</code>):",
        parse_mode="HTML"
    )

@dp.message(BookingState.name)
async def msg_get_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(client_name=name)
    await state.set_state(BookingState.phone)
    await message.answer(
        f"Приятно познакомиться, {name}!\n\n"
        f"📱 <b>Введите ваш номер телефона</b> для связи\n"
        f"(например: <code>+79991234567</code>):",
        parse_mode="HTML"
    )

@dp.message(BookingState.phone)
async def msg_get_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(client_phone=phone, client_telegram=message.from_user.username or "")
    await state.set_state(BookingState.comment)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить ➡️", callback_data="skip_comment")]
    ])

    await message.answer(
        "📝 <b>Есть ли пожелания к процедуре?</b>\n"
        "Например: <i>нужно снять старое покрытие, хочу френч, сломался один ноготок</i>.\n\n"
        "Напишите сообщением или нажмите «Пропустить»:",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(BookingState.comment, F.data == "skip_comment")
async def cb_skip_comment(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(client_comment="")
    await ask_photo_step(cb.message, state)

@dp.message(BookingState.comment)
async def msg_get_comment(message: types.Message, state: FSMContext):
    await state.update_data(client_comment=message.text.strip())
    await ask_photo_step(message, state)

async def ask_photo_step(msg: types.Message, state: FSMContext):
    await state.set_state(BookingState.photo)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без фото референса ➡️", callback_data="skip_photo")]
    ])
    text = (
        "📸 <b>Прикрепите фото желаемого дизайна (референс):</b>\n\n"
        "Просто отправьте фотографию из галереи в этот чат!\n"
        "Это поможет мастеру заранее подготовить материалы и цвет.\n\n"
        "Если дизайн еще не выбрали — нажмите «Без фото»."
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(BookingState.photo, F.data == "skip_photo")
async def cb_skip_photo(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(reference_photo="", photo_file_id="")
    await show_confirmation(cb.message, state)

@dp.message(BookingState.photo, F.photo)
async def msg_get_photo(message: types.Message, state: FSMContext):
    # Берем фото в лучшем качестве
    photo = message.photo[-1]
    file_id = photo.file_id

    # Скачиваем фото в папку uploads
    file_info = await bot.get_file(file_id)
    saved_filename = f"tg_ref_{file_id[:12]}.jpg"
    dest_path = UPLOAD_DIR / saved_filename
    await bot.download_file(file_info.file_path, dest_path)

    await state.update_data(reference_photo=saved_filename, photo_file_id=file_id)
    await show_confirmation(message, state)

async def show_confirmation(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BookingState.confirm)

    tg_username = f"@{data.get('client_telegram')}" if data.get('client_telegram') else "не указан"
    comment = data.get('client_comment') or "без комментариев"
    has_photo = "Да, фото прикреплено 📸" if data.get('photo_file_id') else "Без фото"

    summary_text = (
        f"🌿 <b>ПРОВЕРЬТЕ ДАННЫЕ ВАШЕЙ ЗАПИСИ:</b>\n\n"
        f"💅 <b>Услуга:</b> {data['service_category']} — {data['service_title']}\n"
        f"💰 <b>Стоимость:</b> {data['service_price']}\n"
        f"📅 <b>Дата:</b> {data['slot_date']}\n"
        f"⏰ <b>Время:</b> {data['slot_time']}\n\n"
        f"👤 <b>Клиент:</b> {data['client_name']}\n"
        f"📱 <b>Телефон:</b> {data['client_phone']}\n"
        f"💬 <b>Telegram:</b> {tg_username}\n"
        f"📝 <b>Пожелания:</b> {comment}\n"
        f"🎨 <b>Референс:</b> {has_photo}\n\n"
        f"Всё верно? Нажмите кнопку для подтверждения 👇"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="confirm_final_booking")],
        [InlineKeyboardButton(text="❌ Начать сначала", callback_data="back_to_main")]
    ])

    if data.get('photo_file_id'):
        await msg.answer_photo(photo=data['photo_file_id'], caption=summary_text, parse_mode="HTML", reply_markup=kb)
    else:
        await msg.answer(summary_text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(BookingState.confirm, F.data == "confirm_final_booking")
async def cb_final_confirm(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # Сохраняем в базу
    booking = create_booking(
        slot_id=data["slot_id"],
        service_id=data["service_id"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        client_telegram=data.get("client_telegram", ""),
        client_comment=data.get("client_comment", ""),
        reference_photo=data.get("reference_photo", "")
    )

    if not booking:
        await cb.answer("К сожалению, это время только что заняли!", show_alert=True)
        await state.clear()
        return

    await state.clear()

    # Сообщение клиенту
    success_text = (
        f"🎉 <b>Вы успешно записаны!</b>\n\n"
        f"💅 <b>{booking['service_title']}</b>\n"
        f"📅 <b>{booking['slot_date']}</b> в <b>{booking['slot_time']}</b>\n\n"
        f"Мастер уже получил вашу запись и референс дизайна.\n"
        f"Перед визитом вам придет напоминание. До скорой встречи! 🌸"
    )
    await cb.message.answer(success_text, parse_mode="HTML")

    # УВЕДОМЛЕНИЕ МАСТЕРУ В TELEGRAM
    if MASTER_TELEGRAM_ID:
        master_caption = (
            f"💅 <b>НОВАЯ ЗАПИСЬ НА НОГТИ!</b>\n\n"
            f"👤 <b>Клиент:</b> {booking['client_name']}\n"
            f"📞 <b>Телефон:</b> <code>{booking['client_phone']}</code>\n"
            f"💬 <b>Telegram:</b> @{booking.get('client_telegram') or 'нет'}\n\n"
            f"✨ <b>Услуга:</b> {booking['service_category']} — {booking['service_title']}\n"
            f"💰 <b>Стоимость:</b> {booking['service_price']}\n"
            f"📅 <b>Дата:</b> {booking['slot_date']}\n"
            f"⏰ <b>Время:</b> {booking['slot_time']}\n\n"
            f"📝 <b>Комментарий:</b> {booking.get('client_comment') or 'нет'}"
        )

        b_id = booking['id']
        master_kb = [
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm_confirm_{b_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_cancel_{b_id}")
            ]
        ]
        if booking.get('client_telegram'):
            master_kb.append([InlineKeyboardButton(text="💬 Написать клиенту", url=f"https://t.me/{booking['client_telegram']}")])

        markup = InlineKeyboardMarkup(inline_keyboard=master_kb)

        try:
            if data.get('photo_file_id'):
                await bot.send_photo(chat_id=MASTER_TELEGRAM_ID, photo=data['photo_file_id'], caption=master_caption, parse_mode="HTML", reply_markup=markup)
            else:
                await bot.send_message(chat_id=MASTER_TELEGRAM_ID, text=master_caption, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            print(f"Ошибка отправки мастеру: {e}")

# --- ПАНЕЛЬ МАСТЕРА (ADMIN) ---

@dp.message(Command("admin"))
@dp.callback_query(F.data == "admin_menu")
async def handle_admin_menu(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    if str(user_id) != str(MASTER_TELEGRAM_ID):
        text = "⛔️ Этот раздел доступен только мастеру."
        if isinstance(event, types.CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    admin_text = (
        f"⚙️ <b>КАБИНЕТ МАСТЕРА</b>\n\n"
        f"Здесь вы можете управлять свободными окошками и просматривать записи."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить свободное окошко", callback_data="adm_add_slot_date")],
        [InlineKeyboardButton(text="📋 Посмотреть записи", callback_data="adm_view_bookings")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(admin_text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(admin_text, parse_mode="HTML", reply_markup=kb)

# Мастер добавляет слот: шаг 1 — выбор даты
@dp.callback_query(F.data == "adm_add_slot_date")
async def cb_adm_add_date(cb: types.CallbackQuery, state: FSMContext):
    today = datetime.now().date()
    buttons = []
    row = []
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i in range(14):
        d = today + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        w = weekdays[d.weekday()]
        label = f"Сегодня ({d.day}.{d.month})" if i == 0 else (f"Завтра ({d.day}.{d.month})" if i == 1 else f"{w}, {d.day}.{d.month}")
        row.append(InlineKeyboardButton(text=label, callback_data=f"admslotdate_{d_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])

    await cb.message.edit_text("📅 <b>На какой день добавить окошко?</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# Мастер добавляет слот: шаг 2 — выбор времени
@dp.callback_query(F.data.startswith("admslotdate_"))
async def cb_adm_add_time(cb: types.CallbackQuery, state: FSMContext):
    date_str = cb.data.replace("admslotdate_", "")
    await state.update_data(admin_slot_date=date_str)

    # Быстрые кнопки времени
    preset_times = ["10:00", "12:00", "13:30", "15:00", "17:00", "19:00", "20:00"]
    existing_slots = [s["slot_time"] for s in get_slots_by_date(date_str, for_admin=True)]

    buttons = []
    row = []
    for t in preset_times:
        is_exists = t in existing_slots
        mark = "✓ " if is_exists else "+ "
        row.append(InlineKeyboardButton(text=f"{mark}{t}", callback_data=f"admtoggle_{t}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="✍️ Ввести другое время", callback_data="adm_custom_time")])
    buttons.append([InlineKeyboardButton(text="🔙 К выбору даты", callback_data="adm_add_slot_date")])

    await cb.message.edit_text(
        f"📅 Дата: <b>{date_str}</b>\n\n"
        f"Нажмите на время, чтобы открыть/закрыть окошко:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(F.data.startswith("admtoggle_"))
async def cb_adm_toggle_time(cb: types.CallbackQuery, state: FSMContext):
    time_str = cb.data.replace("admtoggle_", "")
    data = await state.get_data()
    date_str = data.get("admin_slot_date")
    if date_str:
        add_or_toggle_slot(date_str, time_str)
        await cb_adm_add_time(cb, state)

@dp.callback_query(F.data == "adm_custom_time")
async def cb_adm_custom_time(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminSlotState.custom_time)
    await cb.message.answer("Введите время приема сообщением (например, <code>11:15</code> или <code>16:30</code>):", parse_mode="HTML")

@dp.message(AdminSlotState.custom_time)
async def msg_adm_custom_time(message: types.Message, state: FSMContext):
    custom_t = message.text.strip()
    data = await state.get_data()
    date_str = data.get("admin_slot_date")
    if date_str and custom_t:
        add_or_toggle_slot(date_str, custom_t)
        await message.answer(f"✅ Окошко на <b>{date_str} в {custom_t}</b> успешно добавлено!", parse_mode="HTML")
        await handle_admin_menu(message, state)

# Просмотр записей мастером
@dp.callback_query(F.data == "adm_view_bookings")
async def cb_adm_view_bookings(cb: types.CallbackQuery):
    bookings = get_all_bookings(limit=10)
    if not bookings:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]])
        await cb.message.edit_text("Записей пока нет.", reply_markup=kb)
        return

    text = "📋 <b>ПОСЛЕДНИЕ ЗАПИСИ КЛИЕНТОВ:</b>\n\n"
    for b in bookings[:8]:
        st_icon = "🟢" if b["status"] == "confirmed" else ("🔴" if b["status"] == "cancelled" else "🟡")
        tg = f"@{b['client_telegram']}" if b['client_telegram'] else "нет"
        text += (
            f"{st_icon} <b>{b['client_name']}</b> ({b['client_phone']}, {tg})\n"
            f"✨ {b['service_title']} ({b['service_price']})\n"
            f"📅 {b['slot_date']} в <b>{b['slot_time']}</b>\n"
            f"Статус: <i>{b['status']}</i>\n"
            f"—————————————\n"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню мастера", callback_data="admin_menu")]])
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# Действия мастера по кнопкам в уведомлении
@dp.callback_query(F.data.startswith("adm_confirm_"))
async def cb_master_confirm(cb: types.CallbackQuery):
    b_id = int(cb.data.split("_")[2])
    update_booking_status(b_id, "confirmed")
    await cb.answer("Запись подтверждена!")
    new_text = (cb.message.caption or cb.message.text or "") + "\n\n🟢 <b>ЗАПИСЬ ПОДТВЕРЖДЕНА ВАМИ!</b>"
    if cb.message.caption:
        await cb.message.edit_caption(caption=new_text, parse_mode="HTML")
    else:
        await cb.message.edit_text(text=new_text, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_cancel_"))
async def cb_master_cancel(cb: types.CallbackQuery):
    b_id = int(cb.data.split("_")[2])
    update_booking_status(b_id, "cancelled")
    await cb.answer("Запись отклонена, слот освобожден!")
    new_text = (cb.message.caption or cb.message.text or "") + "\n\n🔴 <b>ЗАПИСЬ ОТКЛОНЕНА (слот освобожден)</b>"
    if cb.message.caption:
        await cb.message.edit_caption(caption=new_text, parse_mode="HTML")
    else:
        await cb.message.edit_text(text=new_text, parse_mode="HTML")

# --- СТАРТ БОТА ---
async def main():
    init_db()
    print("\n" + "=" * 50)
    print("💅 TELEGRAM БОТ ОНЛАЙН-ЗАПИСИ ЗАПУЩЕН!")
    print(f"Мастер ID: {MASTER_TELEGRAM_ID or '(не указан)'}")
    print("Бот работает в режиме Long Polling (без веб-сервера, без оплат)")
    print("Для остановки нажмите Ctrl + C")
    print("=" * 50 + "\n")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
