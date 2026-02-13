# handlers/commands_handler.py
# Команды: /chart, /daily, /stats, /search <запрос>
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yandex_music_service import get_chart_tracks, get_daily_track
from yandex import search_track
from database import get_last_reviews, get_user_progress, get_favorites
from keyboards import chart_list_buttons_paginated, back_to_menu_button, main_menu
from utils import hash_id, hash_to_track_id
from handlers.track_card_handler import send_track_card


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /chart — открыть чарт (первая страница с пагинацией)."""
    from handlers.chart_handler import CHART_FETCH_LIMIT, PAGE_SIZE
    tracks = get_chart_tracks(chart_id="world", limit=CHART_FETCH_LIMIT)
    if not tracks:
        await update.message.reply_text(
            "❌ Не удалось загрузить чарт. Попробуй позже.",
            reply_markup=back_to_menu_button(),
        )
        return
    total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE
    text = f"📊 *Чарт Яндекс.Музыки* — стр. 1/{total_pages}\n\nВыбери трек:"
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=chart_list_buttons_paginated(tracks, page=0, per_page=PAGE_SIZE),
    )


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /daily — трек дня."""
    track = get_daily_track()
    if not track:
        await update.message.reply_text(
            "❌ Не удалось загрузить трек дня.",
            reply_markup=back_to_menu_button(),
        )
        return
    user_id = update.message.from_user.id
    await send_track_card(update.message, track["id"], user_id, track_dict=track)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — моя статистика (оценки, уровень, избранное)."""
    user_id = update.message.from_user.id
    progress = get_user_progress(user_id)
    fav_count = len(get_favorites(user_id))
    reviews = get_last_reviews(user_id, limit=10)

    if not reviews:
        await update.message.reply_text(
            f"📊 Уровень {progress['level']} | EXP: {progress['exp']} | 🤍 Избранное: {fav_count}\n\n"
            "У тебя пока нет оценок. Самое время начать! 🎧",
            reply_markup=main_menu(),
        )
        return

    message = (
        f"📊 *Моя статистика*\n"
        f"Уровень {progress['level']} | EXP: {progress['exp']} | 🤍 Избранное: {fav_count}\n\n"
        "📌 Твои последние 10 оценок:\n\n"
    )
    buttons = [[InlineKeyboardButton(f"🤍 Моё избранное ({fav_count})", callback_data="view_favorites")]]
    for r in reviews:
        safe_hash = hash_id(r["track_id"])
        hash_to_track_id[safe_hash] = r["track_id"]
        btn_text = f"{r['title']} — {r['artist']} | {r['total']}/50"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"detail_{safe_hash}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /search <запрос> — быстрый поиск трека."""
    query_text = (context.args or [])
    if not query_text:
        await update.message.reply_text(
            "🔍 Использование: /search _Исполнитель — Название_\n\nПример: /search Платина — Бассок",
            parse_mode="Markdown",
        )
        return
    query = " ".join(query_text).strip()
    await update.message.reply_text("🔍 Ищу трек...")
    tracks = search_track(query, limit=5)
    if not tracks:
        await update.message.reply_text(
            "❌ Не нашёл такой трек. Попробуй: /search Исполнитель — Название"
        )
        return
    user_id = update.message.from_user.id
    await send_track_card(update.message, tracks[0]["id"], user_id, track_dict=tracks[0])
