import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MASTER_TELEGRAM_ID = os.getenv("MASTER_TELEGRAM_ID", "").strip()
WEB_APP_URL = os.getenv("WEB_APP_URL", "http://localhost:8000").strip()

# Admin PIN for web admin login (default: 1234)
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234").strip()

# Database & Uploads
DATABASE_PATH = BASE_DIR / "nail_booking.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Master info
MASTER_NAME = os.getenv("MASTER_NAME", "Мастер ногтевого сервиса")
STUDIO_ADDRESS = os.getenv("STUDIO_ADDRESS", "г. Москва (точный адрес после записи)")

# Правила слотов
# Если клиент записался на сегодня — остальные свободные окошки на сегодня удаляются
REMOVE_REMAINING_SLOTS_ON_TODAY_BOOKING = True

# Если нужно, чтобы на ЛЮБОЙ день принимался только 1 клиент (записался -> остальные слоты дня удаляются)
ONE_CLIENT_PER_DAY = os.getenv("ONE_CLIENT_PER_DAY", "false").lower() in ("true", "1", "yes")

