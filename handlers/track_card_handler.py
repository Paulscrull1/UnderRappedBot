# handlers/track_card_handler.py
"""Единая карточка трека и обработчики кнопок: Оценить, Рецензия, Скачать, Избранное."""
import io
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from yandex_music_service import get_track_by_id, download_track_bytes
from database import is_in_favorites, add_favorite, remove_favorite, add_exp
from keyboards import track_card_buttons, rating_buttons
from utils import user_states, hash_to_track_id, CRITERIA_NAMES, EXP_FOR_FAVORITE
from database import get_user_nickname


def _get_track_dict(track_id, track_dict=None):
    """Возвращает словарь трека: либо переданный, либо загрузка по id."""
    if track_dict and isinstance(track_dict, dict) and track_dict.get("id"):
        return track_dict
    return get_track_by_id(track_id)


def build_card_caption(track):
    """Текст карточки: название, исполнитель, жанр."""
    title = track.get("title", "Без названия")
    artist = track.get("artist", "Неизвестен")
    genre = track.get("genre", "—")
    return f"🎧 *{title}*\n👤 {artist}\n🏷 {genre}\n━━━━━━━━━━━━━━━━"


async def send_track_card(message_or_query, track_id, user_id, track_dict=None, parse_mode="Markdown"):
    """
    Отправляет карточку трека (фото + подпись + кнопки).
    message_or_query — объект message (для reply_photo) или callback_query (для answer + reply_photo от имени message).
    """
    track = _get_track_dict(track_id, track_dict)
    if not track:
        if hasattr(message_or_query, "reply_text"):
            await message_or_query.reply_text("❌ Не удалось загрузить трек.")
        return None
    caption = build_card_caption(track)
    url = track.get("track_url") or f"https://music.yandex.ru/search?text={track.get('artist', '')}+{track.get('title', '')}"
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav)
    photo = track.get("cover_url") or None
    msg = getattr(message_or_query, "message", message_or_query)
    if photo:
        await msg.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode=parse_mode)
    else:
        await msg.reply_text(caption, reply_markup=markup, parse_mode=parse_mode)
    return track


async def handle_chart_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback chart_track_{hash} — показать карточку выбранного трека из чарта."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("chart_track_"):
        return
    track_hash = data.replace("chart_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Трек не найден.", reply_markup=None)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.edit_message_text("❌ Не удалось загрузить трек.")
        return
    caption = build_card_caption(track)
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav)
    photo = track.get("cover_url")
    try:
        if photo:
            await query.message.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.message.reply_text(caption, reply_markup=markup, parse_mode="Markdown")
        await query.delete_message()
    except Exception:
        await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")


async def handle_rate_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback rate_track_{hash} — начать оценку трека (переход в состояние rating)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("rate_track_"):
        return
    track_hash = data.replace("rate_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.answer("❌ Не удалось загрузить трек.", show_alert=True)
        return
    nickname = get_user_nickname(user_id) or user_states.get(user_id, {}).get("nickname", "Аноним")
    user_states[user_id] = {
        "stage": "rating",
        "track_id": track_id,
        "track_title": track["title"],
        "track_artist": track["artist"],
        "ratings": {},
        "current_criteria": "rhymes",
        "nickname": nickname,
        "genre": track.get("genre"),
        "is_daily": False,
    }
    await query.message.reply_text(
        f"Оценим этот трек!\n\n🔹 *{CRITERIA_NAMES['rhymes']}*\nВыбери оценку от 1 до 10:",
        parse_mode="Markdown",
        reply_markup=rating_buttons(),
    )


# Блокировка повторного нажатия «Скачать»: (user_id, track_id) в процессе загрузки
_downloading = set()


def _download_key(user_id: int, track_id: str):
    return (user_id, track_id)


async def handle_download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback download_track_{hash} — скачать трек через API и отправить пользователю файлом."""
    query = update.callback_query
    data = query.data
    if not data.startswith("download_track_"):
        await query.answer()
        return
    track_hash = data.replace("download_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    key = _download_key(user_id, track_id)
    if key in _downloading:
        await query.answer("⏳ Загрузка уже идёт, подожди.", show_alert=True)
        return
    _downloading.add(key)
    await query.answer("⏳ Начинаю загрузку...")
    status_msg = None
    try:
        status_msg = await query.message.reply_text("⏳ _Загрузка трека началась..._", parse_mode="Markdown")
        audio_bytes, title, performer = download_track_bytes(track_id)
        if not audio_bytes:
            if status_msg:
                await status_msg.edit_text(
                    "❌ Не удалось скачать трек. Проверьте токен Яндекс.Музыки и доступность трека."
                )
            return
        if len(audio_bytes) > 50 * 1024 * 1024:
            if status_msg:
                await status_msg.edit_text("❌ Файл слишком большой для отправки в Telegram (лимит 50 МБ).")
            return
        if status_msg:
            await status_msg.edit_text("✅ _Отправляю файл..._", parse_mode="Markdown")
        filename = f"{performer} - {title}.mp3"[:60].strip() or "track.mp3"
        bio = io.BytesIO(audio_bytes)
        bio.name = filename
        await query.message.reply_audio(
            audio=InputFile(bio, filename=filename),
            title=title[:64] if title else None,
            performer=performer[:64] if performer else None,
        )
        if status_msg:
            await status_msg.edit_text("✅ Готово! Файл отправлен.")
    finally:
        _downloading.discard(key)


async def handle_fav_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback fav_toggle_{hash} — добавить/убрать из избранного и обновить кнопку."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("fav_toggle_"):
        return
    track_hash = data.replace("fav_toggle_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.answer("❌ Ошибка загрузки трека.", show_alert=True)
        return
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track_id)
    if in_fav:
        remove_favorite(user_id, track_id)
        in_fav = False
    else:
        add_favorite(user_id, track_id, track["title"], track["artist"])
        add_exp(user_id, EXP_FOR_FAVORITE)
        in_fav = True
    markup = track_card_buttons(track_id, url, in_fav)
    caption = build_card_caption(track)
    try:
        await query.edit_message_reply_markup(reply_markup=markup)
    except Exception:
        if query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")
