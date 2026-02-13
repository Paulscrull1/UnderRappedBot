# utils.py
import hashlib

# Хранение состояния пользователей
user_states = {}

# Критерии оценки
CRITERIA = ["rhymes", "rhythm", "style", "charisma", "vibe"]

# Человекочитаемые названия критериев
CRITERIA_NAMES = {
    "rhymes": "Рифмы/образы",
    "rhythm": "Структура/ритмика",
    "style": "Реализация стиля",
    "charisma": "Индивидуальность/харизма",
    "vibe": "Атмосфера/вайб",
}

# Максимальный балл (5 критериев × 10)
MAX_SCORE = 50

# Начисление EXP за действия
EXP_FOR_RATING = 10
EXP_FOR_REVIEW = 15
EXP_FOR_FAVORITE = 5

# Глобальное хранилище для сопоставления хэш → track_id
hash_to_track_id = {}


def hash_id(track_id: str) -> str:
    """
    Создаёт короткий (10 символов) MD5-хэш из любого track_id.
    Используется для безопасной передачи в callback_data,
    чтобы не превысить лимит Telegram в 64 байта.
    """
    return hashlib.md5(track_id.encode('utf-8')).hexdigest()[:10]