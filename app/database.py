import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.config import (
    DATABASE_PATH,
    REMOVE_REMAINING_SLOTS_ON_TODAY_BOOKING,
    ONE_CLIENT_PER_DAY
)

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица услуг
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        price TEXT NOT NULL,
        price_num INTEGER NOT NULL,
        duration_minutes INTEGER DEFAULT 120,
        description TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )
    """)

    # Таблица доступных слотов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS time_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_date TEXT NOT NULL,      -- YYYY-MM-DD
        slot_time TEXT NOT NULL,      -- HH:MM
        is_booked INTEGER DEFAULT 0,  -- 0: свободно, 1: занято
        is_active INTEGER DEFAULT 1,  -- 1: активно, 0: скрыто мастером
        UNIQUE(slot_date, slot_time)
    )
    """)

    # Таблица записей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        client_name TEXT NOT NULL,
        client_phone TEXT NOT NULL,
        client_telegram TEXT DEFAULT '',
        client_comment TEXT DEFAULT '',
        reference_photo TEXT DEFAULT '',
        status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (slot_id) REFERENCES time_slots (id),
        FOREIGN KEY (service_id) REFERENCES services (id)
    )
    """)

    conn.commit()

    # Первичное наполнение услугами из прайс-листа
    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] == 0:
        default_services = [
            ("Маникюр", "С покрытием", "1 200 ₽", 1200, 120, ""),
            ("Маникюр", "С покрытием + дизайн", "от 1 200 ₽", 1200, 150, "цена зависит от сложности дизайна"),
            ("Наращивание", "Без дизайна", "1 800 ₽", 1800, 150, ""),
            ("Наращивание", "С дизайном", "от 1 800 ₽", 1800, 180, "цена зависит от сложности дизайна")
        ]
        cursor.executemany("""
            INSERT INTO services (category, title, price, price_num, duration_minutes, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, default_services)
        conn.commit()

    # Генерация демонстрационных слотов на ближайшие 7 дней, если расписание пустое
    cursor.execute("SELECT COUNT(*) FROM time_slots")
    if cursor.fetchone()[0] == 0:
        today = datetime.now().date()
        times = ["10:00", "13:30", "17:00", "20:00"]
        slots_to_insert = []
        for day_offset in range(1, 8):
            slot_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for t in times:
                slots_to_insert.append((slot_date, t))
        cursor.executemany("""
            INSERT OR IGNORE INTO time_slots (slot_date, slot_time)
            VALUES (?, ?)
        """, slots_to_insert)
        conn.commit()

    conn.close()

# --- Функции для работы с услугами ---
def get_all_services() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_service_by_id(service_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# --- Функции для работы со слотами ---
def get_available_dates(days_ahead: int = 30) -> List[str]:
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.execute("""
        SELECT DISTINCT slot_date 
        FROM time_slots 
        WHERE slot_date >= ? AND is_booked = 0 AND is_active = 1
        ORDER BY slot_date ASC
    """, (today,))
    dates = [row["slot_date"] for row in cursor.fetchall()]
    conn.close()
    return dates

def get_slots_by_date(slot_date: str, for_admin: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    if for_admin:
        query = "SELECT * FROM time_slots WHERE slot_date = ? ORDER BY slot_time ASC"
    else:
        query = "SELECT * FROM time_slots WHERE slot_date = ? AND is_booked = 0 AND is_active = 1 ORDER BY slot_time ASC"
    rows = conn.execute(query, (slot_date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_or_toggle_slot(slot_date: str, slot_time: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM time_slots WHERE slot_date = ? AND slot_time = ?", (slot_date, slot_time)).fetchone()
    if row:
        new_active = 0 if row["is_active"] == 1 else 1
        cursor.execute("UPDATE time_slots SET is_active = ? WHERE id = ?", (new_active, row["id"]))
        result = {"id": row["id"], "action": "toggled", "is_active": new_active, "is_booked": row["is_booked"]}
    else:
        cursor.execute("INSERT INTO time_slots (slot_date, slot_time, is_booked, is_active) VALUES (?, ?, 0, 1)", (slot_date, slot_time))
        result = {"id": cursor.lastrowid, "action": "created", "is_active": 1, "is_booked": 0}
    conn.commit()
    conn.close()
    return result

def delete_slot(slot_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM time_slots WHERE id = ? AND is_booked = 0", (slot_id,))
    conn.commit()
    conn.close()
    return True

# --- Функции для работы с записями ---
def create_booking(
    slot_id: int,
    service_id: int,
    client_name: str,
    client_phone: str,
    client_telegram: str = "",
    client_comment: str = "",
    reference_photo: str = ""
) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем, свободен ли слот (защита от двойной записи)
    slot = cursor.execute("SELECT * FROM time_slots WHERE id = ? AND is_booked = 0 AND is_active = 1", (slot_id,)).fetchone()
    if not slot:
        conn.close()
        return None

    # Помечаем выбранный слот как забронированный
    cursor.execute("UPDATE time_slots SET is_booked = 1 WHERE id = ?", (slot_id,))

    # Проверяем дату: если запись на сегодня (или включено правило 1 клиента в день),
    # удаляем все остальные свободные слоты на эту дату
    slot_date = slot["slot_date"]
    today_str = datetime.now().strftime("%Y-%m-%d")

    if (REMOVE_REMAINING_SLOTS_ON_TODAY_BOOKING and slot_date == today_str) or ONE_CLIENT_PER_DAY:
        cursor.execute("""
            DELETE FROM time_slots 
            WHERE slot_date = ? AND is_booked = 0
        """, (slot_date,))

    # Создаем запись
    cursor.execute("""
        INSERT INTO bookings (slot_id, service_id, client_name, client_phone, client_telegram, client_comment, reference_photo, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (slot_id, service_id, client_name.strip(), client_phone.strip(), client_telegram.strip().lstrip('@'), client_comment.strip(), reference_photo))
    
    booking_id = cursor.lastrowid
    conn.commit()
    
    # Получаем полные данные для уведомления
    booking_data = cursor.execute("""
        SELECT b.*, s.title as service_title, s.price as service_price, s.category as service_category,
               t.slot_date, t.slot_time
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        JOIN time_slots t ON b.slot_id = t.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    conn.close()
    return dict(booking_data) if booking_data else None

def get_all_bookings(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = """
        SELECT b.*, s.title as service_title, s.price as service_price, s.category as service_category,
               t.slot_date, t.slot_time
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        JOIN time_slots t ON b.slot_id = t.id
        ORDER BY t.slot_date DESC, t.slot_time DESC
        LIMIT ?
    """
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_booking_status(booking_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    booking = cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        conn.close()
        return None
    
    cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
    
    # Если запись отменена, освобождаем слот
    if new_status == "cancelled":
        cursor.execute("UPDATE time_slots SET is_booked = 0 WHERE id = ?", (booking["slot_id"],))
    elif new_status == "confirmed":
        cursor.execute("UPDATE time_slots SET is_booked = 1 WHERE id = ?", (booking["slot_id"],))
        
    conn.commit()
    
    updated = cursor.execute("""
        SELECT b.*, s.title as service_title, s.price as service_price,
               t.slot_date, t.slot_time
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        JOIN time_slots t ON b.slot_id = t.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    conn.close()
    return dict(updated) if updated else None
