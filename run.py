import os
import uvicorn
from pathlib import Path

if __name__ == "__main__":
    print("🌿 Запуск сервера онлайн-записи на ноготочки...")
    print("👉 Клиентский сайт & Mini App: http://localhost:8000")
    print("👉 Кабинет мастера (слоты):   http://localhost:8000/admin")
    print("Для остановки нажмите Ctrl + C\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
