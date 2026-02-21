# handlers/profile_handler.py
"""Профиль пользователя: просмотр, редактирование (аватар, ник, описание, закреплённый трек). Лидерборд."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_profile,
    get_user_nickname,
    save_user_nickname,
    get_user_progress,
    update_profile_avatar,
    update_profile_description,
    set_pinned_track,
    clear_pinned_track,
    get_leaderboard,
    get_last_reviews,
    get_favorites,
)
from keyboards import (
    profile_view_buttons,
    profile_edit_buttons,
    profile_pin_track_buttons,
    back_to_menu_button,
    leaderboard_buttons,
    back_to_leaderboard_button,
)
from utils import user_states, hash_to_track_id, level_progress_bar


def _profile_text(profile: dict, progress: dict) -> str:
    """Текст профиля: ник, описание, закреплённый трек, уровень."""
    parts = [f"👤 *{profile['nickname']}*", f"📊 {level_progress_bar(progress['level'], progress['exp'])}"]
    if profile.get("description"):
        parts.append(f"\n📄 {profile['description']}")
    if profile.get("pinned_track_id"):
        parts.append(
            f"\n📌 Трек: *{profile.get('pinned_track_title') or 'Трек'}* — {profile.get('pinned_track_artist') or ''}"
        )
    return "\n".join(parts)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль: аватар (если есть), текст, кнопки Редактировать / Лидерборд."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        msg = query.message
        chat_id = msg.chat_id
    else:
        user_id = update.message.from_user.id
        msg = update.message
        chat_id = msg.chat_id

    profile = get_profile(user_id)
    if not profile:
        nickname = get_user_nickname(user_id) or f"User_{user_id}"
        profile = {
            "nickname": nickname,
            "avatar_file_id": None,
            "description": "",
            "pinned_track_id": None,
            "pinned_track_title": None,
            "pinned_track_artist": None,
        }
    progress = get_user_progress(user_id)
    text = _profile_text(profile, progress)

    try:
        if query and getattr(msg, "photo", None):
            await msg.delete()
    except Exception:
        pass

    if profile.get("avatar_file_id"):
        try:
            if query:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=profile["avatar_file_id"],
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=profile_view_buttons(),
                )
                try:
                    await msg.delete()
                except Exception:
                    pass
            else:
                await msg.reply_photo(
                    photo=profile["avatar_file_id"],
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=profile_view_buttons(),
                )
        except Exception:
            if query:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=profile_view_buttons(),
                )
            else:
                await msg.reply_text(text, parse_mode="Markdown", reply_markup=profile_view_buttons())
    else:
        if query:
            try:
                await msg.edit_text(text, parse_mode="Markdown", reply_markup=profile_view_buttons())
            except Exception:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=profile_view_buttons(),
                )
        else:
            await msg.reply_text(text, parse_mode="Markdown", reply_markup=profile_view_buttons())


async def profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню редактирования профиля."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ Что изменить?",
        reply_markup=profile_edit_buttons(),
    )


async def profile_set_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить отправку фото для аватара."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = {"stage": "awaiting_profile_avatar"}
    await query.edit_message_text(
        "🖼 Отправь фото для аватарки (одним сообщением).",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="show_profile")],
        ]),
    )


async def profile_set_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить новый никнейм."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = {"stage": "awaiting_profile_nickname"}
    await query.edit_message_text(
        "📝 Введи новый никнейм (до 30 символов).",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="show_profile")],
        ]),
    )


async def profile_set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить описание профиля."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = {"stage": "awaiting_profile_description"}
    await query.edit_message_text(
        "📄 Введи описание профиля (до 500 символов). Можно отправить «-» чтобы очистить.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="show_profile")],
        ]),
    )


async def profile_pin_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список треков для закрепления (оценки + избранное)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    reviews = get_last_reviews(user_id, limit=50)
    favorites = get_favorites(user_id, limit=50)
    seen = set()
    tracks = []
    for r in reviews:
        tid = r["track_id"]
        if tid not in seen:
            seen.add(tid)
            tracks.append({
                "track_id": tid,
                "title": r["title"],
                "artist": r["artist"],
            })
    for f in favorites:
        tid = f["track_id"]
        if tid not in seen:
            seen.add(tid)
            tracks.append({
                "track_id": tid,
                "title": f["title"],
                "artist": f["artist"],
            })
    if not tracks:
        await query.edit_message_text(
            "Нет треков для закрепления. Сначала оцени или добавь в избранное.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="profile_edit")],
            ]),
        )
        return
    user_states[user_id] = {"stage": "profile_pin_list", "pin_tracks": tracks}
    page = 0
    await query.edit_message_text(
        f"📌 Выбери трек для закрепления в профиле (стр. 1/{(len(tracks) + 7) // 8}):",
        reply_markup=profile_pin_track_buttons(tracks, page=page),
    )


async def profile_pin_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пагинация списка закрепления трека."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("profile_pin_page_"):
        return
    try:
        page = int(data.replace("profile_pin_page_", ""))
    except ValueError:
        page = 0
    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    tracks = state.get("pin_tracks") or []
    if not tracks:
        await query.answer("Список устарел. Выбери «Закрепить трек» снова.", show_alert=True)
        return
    total_pages = (len(tracks) + 7) // 8
    page = max(0, min(page, total_pages - 1))
    await query.edit_message_text(
        f"📌 Выбери трек для закрепления — стр. {page + 1}/{total_pages}:",
        reply_markup=profile_pin_track_buttons(tracks, page=page),
    )


async def profile_do_pin_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить закреплённый трек по callback pin_track_{hash}."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("pin_track_"):
        return
    track_hash = data.replace("pin_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    tracks = state.get("pin_tracks") or []
    track = next((t for t in tracks if t["track_id"] == track_id), None)
    if not track:
        track = {"track_id": track_id, "title": "Трек", "artist": ""}
    set_pinned_track(user_id, track_id, track.get("title"), track.get("artist"))
    await query.edit_message_text("✅ Трек закреплён в профиле.", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 В профиль", callback_data="show_profile")],
    ]))


async def profile_unpin_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Убрать закреплённый трек."""
    query = update.callback_query
    await query.answer()
    clear_pinned_track(query.from_user.id)
    await query.edit_message_text(
        "Закрепление снято.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 В профиль", callback_data="show_profile")],
        ]),
    )


async def handle_profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото для аватара (stage awaiting_profile_avatar)."""
    if not update.message or not update.message.photo:
        return
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {})
    if state.get("stage") != "awaiting_profile_avatar":
        return
    photo = update.message.photo[-1]
    file_id = photo.file_id
    update_profile_avatar(user_id, file_id)
    user_states[user_id] = {"stage": "menu"}
    await show_profile(update, context)


async def handle_profile_nickname_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для никнейма (stage awaiting_profile_nickname). Возвращает True если обработано."""
    if not update.message or not update.message.text:
        return False
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {})
    if state.get("stage") != "awaiting_profile_nickname":
        return False
    text = update.message.text.strip()
    if not text or len(text) > 30:
        await update.message.reply_text("Никнейм от 1 до 30 символов. Попробуй снова.")
        return True
    save_user_nickname(user_id, text)
    user_states[user_id] = {"stage": "menu"}
    await update.message.reply_text(f"✅ Никнейм изменён на *{text}*!", parse_mode="Markdown", reply_markup=profile_view_buttons())
    return True


async def handle_profile_description_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для описания (stage awaiting_profile_description). Возвращает True если обработано."""
    if not update.message or not update.message.text:
        return False
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {})
    if state.get("stage") != "awaiting_profile_description":
        return False
    text = update.message.text.strip()
    if text == "-" or text == "—":
        text = ""
    update_profile_description(user_id, text)
    user_states[user_id] = {"stage": "menu"}
    msg = "✅ Описание очищено!" if not text else "✅ Описание сохранено!"
    await update.message.reply_text(msg, reply_markup=profile_view_buttons())
    return True


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Лидерборд: топ-3 главных ценителя по EXP. По нажатию — полный профиль (аватар, описание, трек)."""
    query = update.callback_query
    if query:
        await query.answer()
    chat_id = query.message.chat_id if query else update.message.chat_id
    leaders = get_leaderboard(limit=3)
    if not leaders:
        text = "🏆 Пока никого в лидерборде. Оцени треки и накапливай EXP!"
        kb = back_to_menu_button()
    else:
        lines = ["🏆 *Топ-3 главных ценителя*\n_(по активности — EXP)_\n"]
        for i, u in enumerate(leaders, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            lines.append(f"{medal} {u['nickname']} — {u['exp']} EXP (ур. {u['level']})")
        text = "\n".join(lines) + "\n\n_Нажми на профиль, чтобы посмотреть полностью._"
        kb = leaderboard_buttons(leaders)
    if query:
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def _send_profile_for_user(chat_id: int, target_user_id: int, context: ContextTypes.DEFAULT_TYPE, edit_message=None):
    """
    Отправляет в chat_id полный профиль пользователя target_user_id (аватар, текст).
    edit_message — сообщение для редактирования (если без фото); иначе отправляем новое.
    """
    profile = get_profile(target_user_id)
    if not profile:
        nickname = get_user_nickname(target_user_id) or f"User_{target_user_id}"
        profile = {
            "nickname": nickname,
            "avatar_file_id": None,
            "description": "",
            "pinned_track_id": None,
            "pinned_track_title": None,
            "pinned_track_artist": None,
        }
    progress = get_user_progress(target_user_id)
    text = _profile_text(profile, progress)
    kb = back_to_leaderboard_button()

    if profile.get("avatar_file_id"):
        try:
            if edit_message:
                try:
                    await edit_message.delete()
                except Exception:
                    pass
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=profile["avatar_file_id"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=kb,
            )
            return
        except Exception:
            pass
    if edit_message:
        try:
            await edit_message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=kb)


async def show_leader_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать полный профиль выбранного из лидерборда (топ-3): аватар, ник, описание, закреплённый трек."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("leader_"):
        return
    await query.answer()
    try:
        target_user_id = int(query.data.replace("leader_", "", 1))
    except ValueError:
        return
    chat_id = query.message.chat_id
    await _send_profile_for_user(chat_id, target_user_id, context, edit_message=query.message)
