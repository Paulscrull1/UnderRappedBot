# handlers/daily_track_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from yandex_music_service import get_daily_track
from keyboards import back_to_menu_button
from handlers.track_card_handler import send_track_card


async def show_daily_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    track = get_daily_track()
    if not track:
        await query.edit_message_text(
            "❌ Не удалось загрузить трек дня.",
            reply_markup=back_to_menu_button()
        )
        return

    user_id = query.from_user.id
    await query.delete_message()
    await send_track_card(query.message, track["id"], user_id, track_dict=track)
