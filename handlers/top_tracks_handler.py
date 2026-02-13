# handlers/top_tracks_handler.py
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_top_tracks_by_rating
from keyboards import back_to_menu_button


async def show_top_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    top_tracks = get_top_tracks_by_rating(limit=10)

    if not top_tracks:
        await query.edit_message_text(
            "Пока нет данных для рейтинга. Оцени больше треков!",
            reply_markup=back_to_menu_button()
        )
        return

    message = "🏆 *Топ-10 треков по оценкам*\n\n"
    for i, t in enumerate(top_tracks, 1):
        stars = "⭐" * (max(1, int(t['avg_score'] / 10)))  # Примерная визуализация
        message += (
            f"{i}. *{t['title']}*\n"
            f"   {t['artist']} | {t['avg_score']}/50 ({t['count']} оценок)\n"
            f"   {stars}\n\n"
        )

    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=back_to_menu_button())