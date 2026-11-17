import os
import httpx
from typing import Dict, Any, Optional
from pathlib import Path
from app.config import BOT_TOKEN, MASTER_TELEGRAM_ID, WEB_APP_URL, UPLOAD_DIR
from app.database import update_booking_status

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def send_telegram_booking_alert(booking: Dict[str, Any]) -> bool:
    """
    Отправляет карточку новой записи мастеру в Telegram с фотографией референса
    и кнопками подтверждения/связи.
    """
    if not BOT_TOKEN or not MASTER_TELEGRAM_ID:
        print("\n" + "="*50)
        print("🔔 [СИМУЛЯЦИЯ TELEGRAM УВЕДОМЛЕНИЯ]")
        print(f"Мастеру {MASTER_TELEGRAM_ID or '(ID не указан)'} отправлено уведомление:")
        print(f"Клиент: {booking.get('client_name')} | Тел: {booking.get('client_phone')} | TG: @{booking.get('client_telegram')}")
        print(f"Услуга: {booking.get('service_title')} ({booking.get('service_price')})")
        print(f"Дата и время: {booking.get('slot_date')} в {booking.get('slot_time')}")
        if booking.get('client_comment'):
            print(f"Комментарий: {booking.get('client_comment')}")
        if booking.get('reference_photo'):
            print(f"Фото-референс: {booking.get('reference_photo')}")
        print("="*50 + "\n")
        return True

    # Текст сообщения
    tg_user = booking.get('client_telegram', '').strip().lstrip('@')
    tg_link = f"@{tg_user}" if tg_user else "не указан"
    comment = booking.get('client_comment', '').strip() or "нет комментария"
    
    caption = (
        f"💅 <b>НОВАЯ ЗАПИСЬ НА НОГТИ!</b>\n\n"
        f"👤 <b>Клиент:</b> {booking.get('client_name')}\n"
        f"📞 <b>Телефон:</b> <code>{booking.get('client_phone')}</code>\n"
        f"💬 <b>Telegram:</b> {tg_link}\n\n"
        f"✨ <b>Услуга:</b> {booking.get('service_category')} — {booking.get('service_title')}\n"
        f"💰 <b>Стоимость:</b> {booking.get('service_price')}\n"
        f"📅 <b>Дата:</b> {booking.get('slot_date')}\n"
        f"⏰ <b>Время:</b> {booking.get('slot_time')}\n\n"
        f"📝 <b>Пожелания / Дизайн:</b>\n<i>«{comment}»</i>"
    )

    # Инлайн-кнопки для мастера
    booking_id = booking.get('id')
    keyboard_buttons = [
        [
            {"text": "✅ Подтвердить", "callback_data": f"confirm_{booking_id}"},
            {"text": "❌ Отклонить", "callback_data": f"cancel_{booking_id}"}
        ]
    ]

    if tg_user:
        keyboard_buttons.append([
            {"text": "💬 Написать клиенту в TG", "url": f"https://t.me/{tg_user}"}
        ])

    reply_markup = {"inline_keyboard": keyboard_buttons}

    photo_filename = booking.get('reference_photo')
    photo_path = UPLOAD_DIR / photo_filename if photo_filename else None

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Если есть фото референса — отправляем sendPhoto
            if photo_path and photo_path.exists():
                with open(photo_path, "rb") as f:
                    files = {"photo": (photo_filename, f.read(), "image/jpeg")}
                    data = {
                        "chat_id": MASTER_TELEGRAM_ID,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": httpx._models.json_dumps(reply_markup)
                    }
                    resp = await client.post(f"{TELEGRAM_API_BASE}/sendPhoto", data=data, files=files)
            else:
                # Без фото — обычный sendMessage
                payload = {
                    "chat_id": MASTER_TELEGRAM_ID,
                    "text": caption,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup
                }
                resp = await client.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload)
            
            return resp.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка отправки Telegram-уведомления: {e}")
            return False

async def handle_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обрабатывает входящие события вебхука от Telegram (кнопки подтверждения, команды /start)
    """
    if not BOT_TOKEN:
        return {"ok": True, "info": "Bot token not configured"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Обработка нажатий на инлайн-кнопки мастером
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            message = cb.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            message_id = message.get("message_id")

            if cb_data.startswith("confirm_"):
                b_id = int(cb_data.split("_")[1])
                updated = update_booking_status(b_id, "confirmed")
                status_text = "\n\n🟢 <b>ЗАПИСЬ ПОДТВЕРЖДЕНА МАСТЕРОМ!</b>"
                await client.post(f"{TELEGRAM_API_BASE}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "Запись подтверждена!"})
                
                # Обновляем текст сообщения в TG
                new_caption = (message.get("caption") or message.get("text", "")) + status_text
                if "caption" in message:
                    await client.post(f"{TELEGRAM_API_BASE}/editMessageCaption", json={
                        "chat_id": chat_id, "message_id": message_id, "caption": new_caption, "parse_mode": "HTML"
                    })
                else:
                    await client.post(f"{TELEGRAM_API_BASE}/editMessageText", json={
                        "chat_id": chat_id, "message_id": message_id, "text": new_caption, "parse_mode": "HTML"
                    })

            elif cb_data.startswith("cancel_"):
                b_id = int(cb_data.split("_")[1])
                updated = update_booking_status(b_id, "cancelled")
                status_text = "\n\n🔴 <b>ЗАПИСЬ ОТКЛОНЕНА (слот освобожден)</b>"
                await client.post(f"{TELEGRAM_API_BASE}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "Запись отменена"})
                
                new_caption = (message.get("caption") or message.get("text", "")) + status_text
                if "caption" in message:
                    await client.post(f"{TELEGRAM_API_BASE}/editMessageCaption", json={
                        "chat_id": chat_id, "message_id": message_id, "caption": new_caption, "parse_mode": "HTML"
                    })
                else:
                    await client.post(f"{TELEGRAM_API_BASE}/editMessageText", json={
                        "chat_id": chat_id, "message_id": message_id, "text": new_caption, "parse_mode": "HTML"
                    })

            return {"ok": True}

        # Обработка команды /start
        if "message" in update and "text" in update["message"]:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "").strip()

            if text.startswith("/start"):
                is_master = str(chat_id) == str(MASTER_TELEGRAM_ID)
                
                if is_master:
                    reply_text = (
                        f"👋 Здравствуйте, мастер!\n\n"
                        f"Здесь вы будете получать мгновенные уведомления о новых записях с фото референсов.\n\n"
                        f"Для управления свободными окошками со смартфона нажмите кнопку ниже:"
                    )
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": "📅 Управление окошками и записями", "web_app": {"url": f"{WEB_APP_URL}/admin"}}]
                        ]
                    }
                else:
                    reply_text = (
                        f"🌸 Привет! Добро пожаловать в онлайн-запись на маникюр.\n\n"
                        f"Выберите удобное время, услугу и прикрепите фото желаемого дизайна в нашем мини-приложении:"
                    )
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": "💅 Записаться на ноготочки", "web_app": {"url": WEB_APP_URL}}]
                        ]
                    }

                await client.post(f"{TELEGRAM_API_BASE}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": reply_text,
                    "reply_markup": reply_markup
                })

        return {"ok": True}
