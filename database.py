# database.py
import os
import sqlite3

DATABASE_PATH = os.environ.get("MUSIC_BOT_DB", "reviews.db")


def _connect():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    """
    Создаёт таблицы при первом запуске
    """
    conn = _connect()
    cursor = conn.cursor()

    # Основная таблица оценок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            user_id INTEGER,
            track_id TEXT,
            rhymes INTEGER,
            rhythm INTEGER,
            style INTEGER,
            charisma INTEGER,
            vibe INTEGER,
            total REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            track_title TEXT,
            track_artist TEXT,
            nickname TEXT,
            genre TEXT,
            review_text TEXT,
            PRIMARY KEY (user_id, track_id)
        )
    ''')

    # Таблица для постоянного хранения никнейма пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL
        )
    ''')

    # Проверяем, есть ли новые колонки, и добавляем при необходимости
    existing_columns = {col[1] for col in cursor.execute("PRAGMA table_info(reviews)").fetchall()}
    if 'nickname' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN nickname TEXT DEFAULT 'Аноним'")
    if 'genre' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN genre TEXT")
    if 'review_text' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN review_text TEXT")

    # Избранное пользователя (треки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER,
            track_id TEXT,
            track_title TEXT,
            track_artist TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, track_id)
        )
    ''')

    # LVL/Exp: прогресс пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            exp INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def save_user_nickname(user_id: int, nickname: str):
    """
    Сохраняет или обновляет никнейм пользователя
    """
    if not nickname or len(nickname.strip()) == 0:
        return
    nickname = nickname.strip()[:50]  # Ограничение длины

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, nickname)
        VALUES (?, ?)
    ''', (user_id, nickname))
    conn.commit()
    conn.close()


def get_user_nickname(user_id: int) -> str:
    """
    Возвращает сохранённый никнейм пользователя
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_review(user_id, track_id, ratings, track_title, track_artist, nickname, genre=None, review_text=None):
    """
    Сохраняет оценку трека и начисляет EXP.
    """
    total = sum(ratings.values())

    # Используем постоянный ник из БД, если есть; иначе — переданный
    final_nickname = get_user_nickname(user_id) or nickname or f"Пользователь {user_id}"

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO reviews 
        (user_id, track_id, rhymes, rhythm, style, charisma, vibe, total,
         track_title, track_artist, nickname, genre, review_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, track_id,
        ratings['rhymes'], ratings['rhythm'], ratings['style'],
        ratings['charisma'], ratings['vibe'], total,
        track_title, track_artist, final_nickname, genre, review_text
    ))
    conn.commit()
    conn.close()

    from utils import EXP_FOR_RATING
    add_exp(user_id, EXP_FOR_RATING)


def get_last_reviews(user_id, limit=10):
    """
    Последние оценки пользователя
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist, total, rhymes, rhythm, style, charisma, vibe, review_text
        FROM reviews WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'track_id': r[0],
            'title': r[1],
            'artist': r[2],
            'total': r[3],
            'ratings': {
                'rhymes': r[4], 'rhythm': r[5], 'style': r[6],
                'charisma': r[7], 'vibe': r[8]
            },
            'review_text': r[9]
        }
        for r in rows
    ]


def get_top_tracks_by_rating(limit=10):
    """
    Топ треков по среднему баллу
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_title, track_artist, AVG(total), COUNT(*)
        FROM reviews
        GROUP BY track_id
        HAVING COUNT(*) >= 1
        ORDER BY AVG(total) DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'title': r[0],
            'artist': r[1],
            'avg_score': round(r[2], 1),
            'count': r[3]
        }
        for r in rows
    ]


def get_last_reviews_global(limit=10):
    """
    Последние оценки всех пользователей
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, track_id, track_title, track_artist, total, nickname, timestamp
        FROM reviews
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    def format_time(ts):
        try:
            date_part = ts.split()[0][5:].replace('-', '.')
            time_part = ts.split()[1][:5]
            return f"{date_part} {time_part}"
        except:
            return "недавно"

    return [
        {
            'user_id': r[0],
            'track_id': r[1],
            'title': r[2],
            'artist': r[3],
            'total': r[4],
            'nickname': r[5] or f"Пользователь {r[0]}",
            'timestamp': format_time(r[6])
        }
        for r in rows
    ]


# --- Избранное ---

def add_favorite(user_id: int, track_id: str, track_title: str, track_artist: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_favorites (user_id, track_id, track_title, track_artist)
        VALUES (?, ?, ?, ?)
    ''', (user_id, track_id, track_title, track_artist))
    conn.commit()
    conn.close()


def remove_favorite(user_id: int, track_id: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_favorites WHERE user_id = ? AND track_id = ?', (user_id, track_id))
    conn.commit()
    conn.close()


def is_in_favorites(user_id: int, track_id: str) -> bool:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM user_favorites WHERE user_id = ? AND track_id = ?', (user_id, track_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_favorites(user_id: int, limit=50):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist FROM user_favorites
        WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{'track_id': r[0], 'title': r[1], 'artist': r[2]} for r in rows]


# --- LVL / Exp ---

def add_exp(user_id: int, amount: int):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_progress (user_id, exp, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            exp = exp + ?,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, amount, amount))
    conn.commit()
    conn.close()


def get_recent_reviews_with_text(limit=5):
    """Последние текстовые рецензии по всем пользователям (для раздела «Общая статистика»)."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, track_title, track_artist, review_text, total, timestamp
        FROM reviews
        WHERE review_text IS NOT NULL AND review_text != ''
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'nickname': r[0] or 'Аноним',
            'title': r[1],
            'artist': r[2],
            'text': r[3],
            'total': r[4],
            'timestamp': r[5],
        }
        for r in rows
    ]


def get_user_progress(user_id: int):
    """Возвращает dict с ключами exp, level. Уровень: 1 + exp // 100."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT exp FROM user_progress WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    exp = row[0] if row else 0
    level = 1 + exp // 100
    return {'exp': exp, 'level': level}