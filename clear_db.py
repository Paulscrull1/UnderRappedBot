#!/usr/bin/env python3
"""
Очистка базы данных перед релизом.
Удаляет все данные из таблиц, схема сохраняется.
Запуск: python clear_db.py
"""
import os
import sys

# Используем тот же путь, что и в database
DATABASE_PATH = os.environ.get("MUSIC_BOT_DB", "reviews.db")

TABLES = ["reviews", "users", "user_favorites", "user_progress", "user_downloads"]


def main():
    if not os.path.isfile(DATABASE_PATH):
        print(f"База {DATABASE_PATH} не найдена. Нечего очищать.")
        return
    print(f"Очистка базы: {DATABASE_PATH}")
    import sqlite3
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    for table in TABLES:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  Очищена таблица: {table}")
        except sqlite3.OperationalError as e:
            print(f"  Пропуск {table}: {e}")
    conn.commit()
    cursor.execute("VACUUM")
    conn.close()
    print("Готово. База пуста, схема сохранена.")


if __name__ == "__main__":
    main()
    sys.exit(0)
