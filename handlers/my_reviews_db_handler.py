# handlers/my_reviews_handler.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_last_reviews, get_user_progress, get_favorites
from keyboards import back_to_menu_button, back_to_list_button
from utils import user_states, hash_id, hash_to_track_id


async def view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    progress = get_user_progress(user_id)
    fav_count = len(get_favorites(user_id))
    reviews = get_last_reviews(user_id, limit=10)

    if not reviews:
        from keyboards import main_menu
        await query.edit_message_text(
            f"📊 Уровень {progress['level']} | EXP: {progress['exp']} | 🤍 Избранное: {fav_count}\n\n"
            "У тебя пока нет оценок. Самое время начать! 🎧",
            reply_markup=main_menu()
        )
        return

    message = (
        f"📊 *Моя статистика*\n"
        f"Уровень {progress['level']} | EXP: {progress['exp']} | 🤍 Избранное: {fav_count}\n\n"
        "📌 Твои последние 10 оценок:\n\n"
    )
    buttons = [[InlineKeyboardButton(f"🤍 Моё избранное ({fav_count})", callback_data="view_favorites")]]
    for r in reviews:
        safe_hash = hash_id(r['track_id'])
        hash_to_track_id[safe_hash] = r['track_id']

        text = f"{r['title']} — {r['artist']} | {r['total']}/50"
        buttons.append([InlineKeyboardButton(text, callback_data=f"detail_{safe_hash}")])

    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")


async def show_detail_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("detail_"):
        return

    track_hash = data.replace("detail_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Оценка не найдена.", show_alert=True)
        return

    real_track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    reviews = get_last_reviews(user_id, limit=10)
    review = next((r for r in reviews if r['track_id'] == real_track_id), None)

    if not review:
        await query.answer("❌ Оценка не найдена.", show_alert=True)
        return

    detail_text = (
        f"🎵 *{review['title']}*\n"
        f"👤 {review['artist']}\n\n"
        f"📊 *Подробная оценка: {review['total']}/50*\n\n"
        f"🔸 Рифмы/образы: {review['ratings']['rhymes']}\n"
        f"🔸 Структура/ритмика: {review['ratings']['rhythm']}\n"
        f"🔸 Реализация стиля: {review['ratings']['style']}\n"
        f"🔸 Харизма: {review['ratings']['charisma']}\n"
        f"🔸 Вайб: {review['ratings']['vibe']}"
    )

    reply_markup = back_to_list_button("view_reviews")
    await query.edit_message_text(detail_text, parse_mode='Markdown', reply_markup=reply_markup)


async def view_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список избранных треков; по нажатию — карточка трека."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    favs = get_favorites(user_id, limit=30)
    if not favs:
        await query.edit_message_text(
            "🤍 В избранном пока пусто. Добавляй треки кнопкой «В избранное» на карточке.",
            reply_markup=back_to_list_button("view_reviews")
        )
        return
    tracks_for_buttons = [{"id": t["track_id"], "title": t["title"], "artist": t["artist"]} for t in favs]
    from keyboards import chart_list_buttons
    text = f"🤍 *Моё избранное* ({len(favs)})\n\nВыбери трек:"
    reply_markup = chart_list_buttons(tracks_for_buttons)
    # Заменить последнюю кнопку «Назад в меню» на «Назад» к view_reviews
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = reply_markup.inline_keyboard
    rows = rows[:-1] + [[InlineKeyboardButton("🔙 Назад", callback_data="view_reviews")]]
    reply_markup = InlineKeyboardMarkup(rows)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)