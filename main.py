# main.py
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram import Update
from telegram.ext import ContextTypes
from telegram.request import HTTPXRequest
import config
import sqlite3

# Импортируем обработчики
from handlers.start_handler import start, handle_nickname, back_to_menu
from handlers.search_handler import start_search, handle_search, handle_rating_callback
from handlers.daily_track_handler import show_daily_track
from handlers.chart_handler import show_chart
from handlers.top_tracks_handler import show_top_tracks
from handlers.my_reviews_db_handler import view_reviews, show_detail_review, view_favorites, view_downloads
from handlers.global_reviews_handler import (
    show_general_stats,
    view_global_reviews,
    show_review_detail,
    show_global_detail,
    show_global_reviews_for_track,
    view_recent_reviews,
    show_reviews_for_track,
)
from handlers.review_handler import ask_for_review, cancel_review, show_reviews_for_track
from handlers.track_card_handler import (
    handle_chart_track,
    handle_search_track,
    handle_playlist_track,
    handle_rate_track,
    handle_fav_toggle,
    handle_download_track,
)
from handlers.commands_handler import cmd_chart, cmd_daily, cmd_stats, cmd_search, cmd_info
from handlers.playlist_handler import start_playlist, handle_playlist_link, show_playlist_page
from handlers.profile_handler import (
    show_profile,
    profile_edit,
    profile_set_avatar,
    profile_set_nickname,
    profile_set_description,
    profile_pin_track,
    profile_pin_page,
    profile_do_pin_track,
    profile_unpin_track,
    show_leaderboard,
    show_leader_profile,
    handle_profile_photo,
    handle_profile_nickname_text,
    handle_profile_description_text,
)
from handlers.web_handler import webapp_handler
from database import init_db, add_exp
from utils import user_states, EXP_FOR_REVIEW
from keyboards import after_review_buttons


async def _noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для кнопок без действия (например «Стр. 1/3»)."""
    await update.callback_query.answer()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Единый обработчик текстовых сообщений
    """
    if update.message is None or update.message.from_user is None:
        return
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {})

    if state.get("stage") == "awaiting_nickname":
        await handle_nickname(update, context)
        return

    if state.get("stage") == "awaiting_playlist_link":
        await handle_playlist_link(update, context)
        return

    if state.get("stage") == "awaiting_profile_nickname":
        if await handle_profile_nickname_text(update, context):
            return

    if state.get("stage") == "awaiting_profile_description":
        if await handle_profile_description_text(update, context):
            return

    if state.get("stage") == "rating":
        return

    if state.get("stage") == "writing_review":
        review_text = update.message.text.strip()
        if len(review_text) > 500:
            await update.message.reply_text("❌ Слишком длинно! До 500 символов.")
            return

        conn = sqlite3.connect("reviews.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reviews SET review_text = ? WHERE user_id = ? AND track_id = ?",
            (review_text, user_id, state["track_id"]),
        )
        conn.commit()
        conn.close()

        add_exp(user_id, EXP_FOR_REVIEW)
        track_id = state["track_id"]
        del user_states[user_id]
        await update.message.reply_text("✅ Рецензия добавлена!", reply_markup=after_review_buttons(track_id=track_id))
        return

    await handle_search(update, context)


def main():
    init_db()
    # Увеличенные таймауты: отправка аудио может быть долгой (медленная сеть, большие файлы)
    request = HTTPXRequest(
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=10.0,
        media_write_timeout=120.0,  # загрузка медиа/файлов — до 2 минут
    )
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("chart", cmd_chart))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_profile_photo))

    # Поиск и оценка
    app.add_handler(CallbackQueryHandler(start_search, pattern="^start_search$"))
    app.add_handler(CallbackQueryHandler(handle_rate_track, pattern="^rate_track_"))
    app.add_handler(CallbackQueryHandler(handle_rating_callback, pattern="^rate_"))
    app.add_handler(CallbackQueryHandler(handle_rating_callback, pattern="^cancel_rating$"))
    # Карточка трека: чарт, избранное
    app.add_handler(CallbackQueryHandler(handle_chart_track, pattern="^chart_track_"))
    app.add_handler(CallbackQueryHandler(handle_search_track, pattern="^search_track_"))
    app.add_handler(CallbackQueryHandler(handle_playlist_track, pattern="^playlist_track_"))
    app.add_handler(CallbackQueryHandler(handle_fav_toggle, pattern="^fav_toggle_"))
    app.add_handler(CallbackQueryHandler(handle_download_track, pattern="^download_track_"))

    # Трек дня и чарт
    app.add_handler(CallbackQueryHandler(show_daily_track, pattern="^show_daily_track$"))
    app.add_handler(CallbackQueryHandler(show_chart, pattern="^show_chart$"))
    app.add_handler(CallbackQueryHandler(show_chart, pattern="^chart_page_\\d+$"))
    app.add_handler(CallbackQueryHandler(start_playlist, pattern="^start_playlist$"))
    app.add_handler(CallbackQueryHandler(show_playlist_page, pattern="^playlist_page_\\d+$"))

    # Топ треков
    app.add_handler(CallbackQueryHandler(show_top_tracks, pattern="^show_top_tracks$"))

    # Профиль и лидерборд
    app.add_handler(CallbackQueryHandler(show_profile, pattern="^show_profile$"))
    app.add_handler(CallbackQueryHandler(profile_edit, pattern="^profile_edit$"))
    app.add_handler(CallbackQueryHandler(profile_set_avatar, pattern="^profile_set_avatar$"))
    app.add_handler(CallbackQueryHandler(profile_set_nickname, pattern="^profile_set_nickname$"))
    app.add_handler(CallbackQueryHandler(profile_set_description, pattern="^profile_set_description$"))
    app.add_handler(CallbackQueryHandler(profile_pin_track, pattern="^profile_pin_track$"))
    app.add_handler(CallbackQueryHandler(profile_pin_page, pattern="^profile_pin_page_\\d+$"))
    app.add_handler(CallbackQueryHandler(profile_do_pin_track, pattern="^pin_track_"))
    app.add_handler(CallbackQueryHandler(profile_unpin_track, pattern="^profile_unpin_track$"))
    app.add_handler(CallbackQueryHandler(show_leaderboard, pattern="^show_leaderboard$"))
    app.add_handler(CallbackQueryHandler(show_leader_profile, pattern="^leader_\\d+$"))

    # Моя статистика и избранное
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews$"))
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews_page_\\d+$"))
    app.add_handler(CallbackQueryHandler(view_favorites, pattern="^view_favorites$"))
    app.add_handler(CallbackQueryHandler(view_downloads, pattern="^view_downloads$"))
    app.add_handler(CallbackQueryHandler(show_detail_review, pattern="^detail_"))

    # Общая статистика и оценки других
    app.add_handler(CallbackQueryHandler(show_general_stats, pattern="^view_global_reviews$"))
    app.add_handler(CallbackQueryHandler(view_global_reviews, pattern="^view_global_reviews_list$"))
    app.add_handler(CallbackQueryHandler(view_recent_reviews, pattern="^view_recent_reviews$"))
    app.add_handler(CallbackQueryHandler(show_review_detail, pattern="^review_detail_"))
    app.add_handler(CallbackQueryHandler(show_global_detail, pattern="^global_detail_"))
    app.add_handler(CallbackQueryHandler(show_global_reviews_for_track, pattern="^global_for_track_"))
    app.add_handler(CallbackQueryHandler(show_reviews_for_track, pattern="^reviews_for_track_"))

    # Рецензия и отмена
    app.add_handler(CallbackQueryHandler(ask_for_review, pattern="^ask_review_"))
    app.add_handler(CallbackQueryHandler(cancel_review, pattern="^cancel_review$"))

    # Навигация и служебные
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(_noop_callback, pattern="^noop$"))

    # Mini App
    app.add_handler(webapp_handler)

    print("🎧 Бот запущен. Готов к работе!")
    app.run_polling()


if __name__ == "__main__":
    main()