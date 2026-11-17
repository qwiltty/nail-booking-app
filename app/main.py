import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import BASE_DIR, UPLOAD_DIR, ADMIN_PIN, MASTER_NAME, STUDIO_ADDRESS
from app.database import (
    init_db,
    get_all_services,
    get_available_dates,
    get_slots_by_date,
    add_or_toggle_slot,
    delete_slot,
    create_booking,
    get_all_bookings,
    update_booking_status
)
from app.telegram import send_telegram_booking_alert, handle_telegram_update

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация БД при запуске
    init_db()
    print("🌿 База данных инициализирована и готова к работе.")
    yield

app = FastAPI(title="Nail Studio Booking System", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтирование статики и загрузок
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# --- HTML страницы ---
@app.get("/", response_class=FileResponse)
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/admin", response_class=FileResponse)
async def serve_admin():
    return FileResponse(STATIC_DIR / "admin.html")

# --- Клиентский API ---
@app.get("/api/config")
async def get_public_config():
    return {
        "master_name": MASTER_NAME,
        "studio_address": STUDIO_ADDRESS
    }

@app.get("/api/services")
async def list_services():
    services = get_all_services()
    return {"services": services}

@app.get("/api/calendar/dates")
async def available_dates():
    dates = get_available_dates()
    return {"dates": dates}

@app.get("/api/slots")
async def get_slots(date: str):
    slots = get_slots_by_date(date, for_admin=False)
    return {"slots": slots}

@app.post("/api/book")
async def submit_booking(
    slot_id: int = Form(...),
    service_id: int = Form(...),
    client_name: str = Form(...),
    client_phone: str = Form(...),
    client_telegram: str = Form(""),
    client_comment: str = Form(""),
    reference_photo: Optional[UploadFile] = File(None)
):
    saved_filename = ""
    if reference_photo and reference_photo.filename:
        # Сохранение файла референса
        file_ext = Path(reference_photo.filename).suffix.lower()
        if not file_ext:
            file_ext = ".jpg"
        saved_filename = f"ref_{uuid.uuid4().hex[:12]}{file_ext}"
        destination = UPLOAD_DIR / saved_filename
        
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(reference_photo.file, buffer)

    booking = create_booking(
        slot_id=slot_id,
        service_id=service_id,
        client_name=client_name,
        client_phone=client_phone,
        client_telegram=client_telegram,
        client_comment=client_comment,
        reference_photo=saved_filename
    )

    if not booking:
        raise HTTPException(status_code=400, detail="Выбранное окошко уже занято. Пожалуйста, выберите другое время.")

    # Мгновенная отправка уведомления мастеру в Telegram
    await send_telegram_booking_alert(booking)

    return {
        "ok": True,
        "message": "Вы успешно записаны!",
        "booking": booking
    }

# --- Мастер / Админ API ---
@app.get("/api/admin/slots")
async def admin_get_slots(date: str):
    slots = get_slots_by_date(date, for_admin=True)
    return {"slots": slots}

@app.post("/api/admin/slots")
async def admin_toggle_slot(request: Request):
    data = await request.json()
    slot_date = data.get("slot_date")
    slot_time = data.get("slot_time")
    if not slot_date or not slot_time:
        raise HTTPException(status_code=400, detail="Укажите дату и время")
    
    result = add_or_toggle_slot(slot_date, slot_time)
    return {"ok": True, "result": result}

@app.delete("/api/admin/slots/{slot_id}")
async def admin_delete_slot(slot_id: int):
    success = delete_slot(slot_id)
    return {"ok": success}

@app.get("/api/admin/bookings")
async def admin_list_bookings():
    bookings = get_all_bookings()
    return {"bookings": bookings}

@app.post("/api/admin/bookings/{booking_id}/status")
async def admin_change_status(booking_id: int, request: Request):
    data = await request.json()
    new_status = data.get("status")
    if new_status not in ["confirmed", "cancelled", "pending"]:
        raise HTTPException(status_code=400, detail="Неверный статус")
    
    updated = update_booking_status(booking_id, new_status)
    if not updated:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"ok": True, "booking": updated}

# --- Вебхук Telegram бота ---
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        await handle_telegram_update(update)
    except Exception as e:
        print(f"Error handling Telegram webhook: {e}")
    return {"ok": True}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "nail-booking-app"}
