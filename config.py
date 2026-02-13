# config.py
# Токены только из переменных окружения или .env (никогда не хранить в коде)
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
YANDEX_MUSIC_TOKEN = os.environ.get("YANDEX_MUSIC_TOKEN", "")
