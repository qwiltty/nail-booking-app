from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime, timedelta

client = TestClient(app)

def run_tests():
    print("🧪 Запуск тестирования приложения...")
    
    # 1. Проверка получения услуг
    res = client.get("/api/services")
    assert res.status_code == 200, f"Error getting services: {res.text}"
    services = res.json()["services"]
    print(f"✅ Услуги успешно получены ({len(services)} шт.)")
    for s in services:
        print(f"   - [{s['category']}] {s['title']} : {s['price']}")

    # 2. Проверка слотов
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    res = client.get(f"/api/slots?date={tomorrow}")
    assert res.status_code == 200
    slots = res.json()["slots"]
    print(f"✅ Доступные слоты на {tomorrow}: {len(slots)} слотов найдено")
    assert len(slots) > 0, "No slots found for tomorrow"
    slot_id = slots[0]["id"]
    service_id = services[0]["id"]

    # 3. Проверка бронирования с комментарием и референсом
    print("💅 Тестирование записи клиента с фото...")
    dummy_photo_content = b"fake-jpeg-photo-data-for-nail-art-reference"
    res = client.post(
        "/api/book",
        data={
            "slot_id": slot_id,
            "service_id": service_id,
            "client_name": "Екатерина",
            "client_phone": "+7 (999) 123-45-67",
            "client_telegram": "@katya_nails",
            "client_comment": "Хочу дизайн как на фото, длина 3"
        },
        files={
            "reference_photo": ("sample_design.jpg", dummy_photo_content, "image/jpeg")
        }
    )
    assert res.status_code == 200, f"Booking error: {res.text}"
    booking_data = res.json()
    print("✅ Запись успешно создана!")
    print(f"   Номер записи: #{booking_data['booking']['id']}")
    print(f"   Клиент: {booking_data['booking']['client_name']}")
    print(f"   Файл фото: {booking_data['booking']['reference_photo']}")

    # 4. Проверка синхронизации: слот должен исчезнуть из доступных
    res = client.get(f"/api/slots?date={tomorrow}")
    remaining_slots = res.json()["slots"]
    assert all(s["id"] != slot_id for s in remaining_slots), "Slot still marked as available!"
    print("✅ Синхронизация подтверждена: занятый слот моментально исчез из расписания!")

    # 5. Проверка нового правила: удаление остальных слотов при записи на СЕГОДНЯ
    print("📅 Тестирование правила удаления остальных окошек на сегодня...")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Добавляем 3 тестовых слота на сегодня
    client.post("/api/admin/slots", json={"slot_date": today_str, "slot_time": "11:00"})
    client.post("/api/admin/slots", json={"slot_date": today_str, "slot_time": "15:00"})
    client.post("/api/admin/slots", json={"slot_date": today_str, "slot_time": "19:00"})

    slots_today_before = client.get(f"/api/slots?date={today_str}").json()["slots"]
    assert len(slots_today_before) >= 3, "Failed to create slots for today"
    today_slot_to_book = slots_today_before[0]["id"]

    # Записываемся на первый слот сегодняшнего дня
    res_today = client.post(
        "/api/book",
        data={
            "slot_id": today_slot_to_book,
            "service_id": service_id,
            "client_name": "Алина",
            "client_phone": "+7 (999) 777-88-99",
            "client_comment": "Запись на сегодня"
        }
    )
    assert res_today.status_code == 200

    # Проверяем, что ВСЕ остальные свободные слоты на сегодня удалены
    slots_today_after = client.get(f"/api/slots?date={today_str}").json()["slots"]
    assert len(slots_today_after) == 0, f"Expected 0 available slots for today, got {len(slots_today_after)}"
    print("✅ Правило подтверждено: при записи на сегодня все остальные слоты на сегодня успешно удалены!")

    # 6. Проверка админ-панели
    res = client.get("/api/admin/bookings")
    assert res.status_code == 200
    all_bookings = res.json()["bookings"]
    assert len(all_bookings) >= 1
    print(f"✅ В кабинете мастера отображается {len(all_bookings)} записей")

    print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! Система полностью работоспособна.")

if __name__ == "__main__":
    run_tests()
