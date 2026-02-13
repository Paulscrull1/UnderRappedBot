# handlers/global_reviews_handler.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
from database import get_last_reviews_global, get_top_tracks_by_rating, get_recent_reviews_with_text
from keyboards import back_to_menu_button, back_to_list_button
from utils import hash_id, hash_to_track_id


def _format_timestamp(ts):
    try:
        if not ts:
            return "недавно"
        parts = str(ts).split(" ")
        date_part = parts[0][5:].replace("-", ".") if len(parts[0]) >= 5 else parts[0]
        time_part = parts[1][:5] if len(parts) > 1 and len(parts[1]) >= 5 else ""
        return f"{date_part} {time_part}".strip() or "недавно"
    except Exception:
        return "недавно"


async def show_general_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Общая статистика: топ треков по количеству оценок + последние рецензии.
    """
    query = update.callback_query
    await query.answer()

    top_tracks = get_top_tracks_by_rating(limit=10)
    recent_reviews = get_recent_reviews_with_text(limit=5)

    lines = ["🌍 *Общая статистика*\n"]
    lines.append("🏆 *Топ-10 треков по количеству оценок:*\n")
    if top_tracks:
        for i, t in enumerate(top_tracks, 1):
            lines.append(f"{i}. *{t['title']}* — {t['artist']}\n   {t['avg_score']}/50 ({t['count']} оценок)\n")
    else:
        lines.append("Пока нет данных.\n")
    lines.append("\n📖 *Последние рецензии:*\n")
    if recent_reviews:
        for r in recent_reviews:
            short = (r["text"][:50] + "…") if len(r["text"]) > 50 else r["text"]
            lines.append(f"• *{r['nickname']}* — {r['title']} ({r['total']}/50)\n  _{short}_\n")
    else:
        lines.append("Пока нет рецензий.\n")

    keyboard = [
        [InlineKeyboardButton("👥 Последние оценки пользователей", callback_data="view_global_reviews_list")],
        [InlineKeyboardButton("📖 Список последних рецензий", callback_data="view_recent_reviews")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("".join(lines), parse_mode="Markdown", reply_markup=reply_markup)


async def view_global_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reviews = get_last_reviews_global(limit=10)

    if len(hash_to_track_id) > 100:
        hash_to_track_id.clear()

    if not reviews:
        await query.edit_message_text("🌍 Пока нет оценок от других.", reply_markup=back_to_menu_button())
        return

    message = "🌍 Последние оценки других пользователей:\n\n"
    buttons = []

    for r in reviews:
        nick_display = r['nickname'] or f"Пользователь {r['user_id']}"
        line1 = f"{nick_display} — {r['title']}"
        line2 = f"{r['artist']} | {r['total']}/50"
        line3 = r['timestamp']

        button_text = f"{line1}\n{line2}\n{line3}"

        safe_hash = hash_id(r['track_id'])
        hash_to_track_id[safe_hash] = r['track_id']

        buttons.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"global_detail_{r['user_id']}_{safe_hash}"
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="view_global_reviews")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(buttons))


async def view_recent_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние текстовые рецензии от других пользователей"""
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, track_title, track_artist, review_text, total, timestamp
        FROM reviews
        WHERE review_text IS NOT NULL AND review_text != ''
        ORDER BY rowid DESC
        LIMIT 10
    ''')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await query.edit_message_text("📖 Пока нет текстовых рецензий от других.", reply_markup=back_to_menu_button())
        return

    message = "📖 Последние рецензии других пользователей:\n\n"
    buttons = []
    for i, (nickname, title, artist, text, score, ts) in enumerate(rows):
        nick_display = nickname or "Аноним"
        short_text = (text[:30] + "...") if len(text) > 30 else text
        time_str = format_timestamp(ts)
        button_text = f"{nick_display}\n{title}\n{short_text} | {score}/50\n{time_str}"
        buttons.append([
            InlineKeyboardButton(button_text, callback_data=f"review_detail_{i}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(buttons))


async def show_review_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает полный текст рецензии по индексу (callback review_detail_0 .. review_detail_9)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("review_detail_"):
        return
    try:
        idx = int(data.replace("review_detail_", "", 1))
    except ValueError:
        return
    reviews = get_recent_reviews_with_text(limit=10)
    if idx < 0 or idx >= len(reviews):
        await query.answer("Рецензия не найдена.", show_alert=True)
        return
    r = reviews[idx]
    time_str = _format_timestamp(r.get("timestamp"))
    text = (
        f"📖 *Рецензия*\n\n"
        f"👤 *{r['nickname']}*\n"
        f"🎵 {r['title']} — {r['artist']}\n"
        f"⭐ {r['total']}/50 | ⏰ {time_str}\n\n"
        f"_{r['text']}_"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_to_list_button("view_recent_reviews"))


async def show_global_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("global_detail_"):
        return

    parts = data.split("_")
    if len(parts) < 4:
        await query.answer("Неверные данные.", show_alert=True)
        return

    try:
        user_id_in_data = int(parts[2])
    except:
        await query.answer("Неверный ID пользователя.", show_alert=True)
        return

    track_hash = parts[-1]
    if track_hash not in hash_to_track_id:
        await query.answer("Трек не найден.", show_alert=True)
        return

    track_id = hash_to_track_id[track_hash]
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_title, track_artist, rhymes, rhythm, style, charisma, vibe, total, nickname
        FROM reviews WHERE user_id = ? AND track_id = ?
    ''', (user_id_in_data, track_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await query.answer("Оценка не найдена.", show_alert=True)
        return

    title, artist, r1, r2, r3, r4, r5, total, nickname = row
    display_name = nickname or f"Пользователь {user_id_in_data}"

    detail_text = (
        f"🌍 *Оценка от {display_name}*\n\n"
        f"🎵 *{title}*\n"
        f"👤 {artist}\n\n"
        f"📊 *Общий балл: {total}/50*\n\n"
        f"🔸 Рифмы/образы: {r1}\n"
        f"🔸 Структура/ритмика: {r2}\n"
        f"🔸 Реализация стиля: {r3}\n"
        f"🔸 Харизма: {r4}\n"
        f"🔸 Атмосфера: {r5}"
    )

    await query.edit_message_text(detail_text, parse_mode='Markdown', reply_markup=back_to_list_button("view_global_reviews"))


async def show_global_reviews_for_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.replace("global_for_track_", "", 1)
    if data not in hash_to_track_id:
        await query.answer("Трек не найден.", show_alert=True)
        return

    track_id = hash_to_track_id[data]
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, total, timestamp
        FROM reviews WHERE track_id = ? ORDER BY total DESC
    ''', (track_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await query.edit_message_text("❌ По этому треку пока нет оценок.", reply_markup=back_to_list_button("view_reviews"))
        return

    message = f"👥 *Оценки других по треку*\n\n"
    for nickname, total, ts in rows:
        nick_display = nickname or "Аноним"
        message += f"• `{nick_display}` — *{total}/50* ({format_timestamp(ts)})\n"

    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=back_to_list_button("view_reviews"))


async def show_reviews_for_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает только текстовые рецензии по конкретному треку"""
    query = update.callback_query
    await query.answer()
    data = query.data.replace("reviews_for_track_", "", 1)
    if data not in hash_to_track_id:
        await query.answer("Трек не найден.", show_alert=True)
        return

    track_id = hash_to_track_id[data]
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, review_text, total, timestamp
        FROM reviews
        WHERE track_id = ? AND review_text IS NOT NULL AND review_text != ''
        ORDER BY total DESC
    ''', (track_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await query.edit_message_text("❌ По этому треку пока нет текстовых рецензий.", reply_markup=back_to_list_button("view_reviews"))
        return

    message = f"💬 *Рецензии других по треку*\n\n"
    for nickname, text, score, ts in rows:
        nick_display = nickname or "Аноним"
        time_str = format_timestamp(ts)
        message += f"👤 *{nick_display}* | ⭐ {score}/50 | ⏰ {time_str}\n💬 _{text}_\n\n"

    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=back_to_list_button("view_reviews"))


def format_timestamp(ts):
    try:
        date_part = ts.split(" ")[0][5:].replace('-', '.')
        time_part = ts.split(" ")[1][:5]
        return f"{date_part} {time_part}"
    except Exception:
        return "недавно"