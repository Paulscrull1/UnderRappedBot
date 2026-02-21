# handlers/playlist_handler.py
"""Треки из плейлиста: запрос ссылки → парсинг → пагинация по 10, карточка как в чарте."""
from telegram import Update
from telegram.ext import ContextTypes
from yandex_music_service import get_playlist_tracks
from keyboards import back_to_menu_button, playlist_list_buttons_paginated
from utils import user_states

PLAYLIST_PAGE_SIZE = 10


async def start_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «Треки из плейлиста» — просим прислать ссылку."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    user_id = query.from_user.id
    user_states[user_id] = {"stage": "awaiting_playlist_link"}
    await query.message.reply_text(
        "📑 *Треки из плейлиста*\n\n"
        "Поделись со мной ссылкой на плейлист Яндекс.Музыки — и я покажу тебе эти треки.\n\n"
        "Пример: `https://music.yandex.ru/playlists/user/123` или ссылка из приложения.",
        parse_mode="Markdown",
        reply_markup=back_to_menu_button(),
    )


async def handle_playlist_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает сообщение со ссылкой на плейлист (вызывается из main при stage == awaiting_playlist_link).
    """
    user_id = update.message.from_user.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(
            "Пришли ссылку на плейлист. Например: https://music.yandex.ru/playlists/...",
            reply_markup=back_to_menu_button(),
        )
        return

    # Ищем URL в тексте (пользователь мог вставить с пробелами или одним куском)
    for part in text.split():
        if "music.yandex" in part and "playlist" in part.lower():
            url = part.split("?")[0]
            break
    else:
        url = text.split("?")[0] if "music.yandex" in text and "playlist" in text.lower() else None

    if not url:
        await update.message.reply_text(
            "❌ В сообщении нет ссылки на плейлист Яндекс.Музыки. Пришли ссылку вида:\n"
            "https://music.yandex.ru/playlists/...",
            reply_markup=back_to_menu_button(),
        )
        return

    await update.message.reply_text("📑 Загружаю плейлист...")
    tracks = get_playlist_tracks(url)
    if not tracks:
        if user_id in user_states and user_states[user_id].get("stage") == "awaiting_playlist_link":
            del user_states[user_id]
        await update.message.reply_text(
            "❌ Не удалось загрузить плейлист. Проверь ссылку и что плейлист доступен.",
            reply_markup=back_to_menu_button(),
        )
        return

    user_states[user_id] = {"stage": "menu", "playlist_tracks": tracks}
    total_pages = (len(tracks) + PLAYLIST_PAGE_SIZE - 1) // PLAYLIST_PAGE_SIZE
    await update.message.reply_text(
        f"📑 *Плейлист* — {len(tracks)} треков, стр. 1/{total_pages}\n\nВыбери трек:",
        parse_mode="Markdown",
        reply_markup=playlist_list_buttons_paginated(tracks, page=0, per_page=PLAYLIST_PAGE_SIZE),
    )


async def show_playlist_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback playlist_page_N — показать страницу N плейлиста (треки из user state)."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("playlist_page_"):
        return
    try:
        page = max(0, int(data.replace("playlist_page_", "", 1)))
    except ValueError:
        page = 0

    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    tracks = state.get("playlist_tracks")
    if not tracks:
        await query.edit_message_text(
            "❌ Сессия плейлиста истекла. Пришли ссылку ещё раз.",
            reply_markup=back_to_menu_button(),
        )
        return

    total_pages = (len(tracks) + PLAYLIST_PAGE_SIZE - 1) // PLAYLIST_PAGE_SIZE
    if page >= total_pages:
        page = max(0, total_pages - 1)

    text = f"📑 *Плейлист* — {len(tracks)} треков, стр. {page + 1}/{total_pages}\n\nВыбери трек:"
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=playlist_list_buttons_paginated(tracks, page=page, per_page=PLAYLIST_PAGE_SIZE),
    )
