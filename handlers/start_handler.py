# handlers/start_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from keyboards import main_menu
from database import get_user_nickname, save_user_nickname, get_user_progress
from utils import user_states, level_progress_bar


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главное меню: Трек дня, Чарт, Найти трек, Моя статистика, Общая статистика, Топ треков.
    """
    user_id = update.message.from_user.id
    nickname = get_user_nickname(user_id)

    if not nickname:
        await update.message.reply_text(
            "👋 Привет! Как тебя зовут?\n"
            "Это имя будет отображаться при оценке треков."
        )
        user_states[user_id] = {'stage': 'awaiting_nickname'}
        return

    user_states[user_id] = {'stage': 'menu', 'nickname': nickname}
    progress = get_user_progress(user_id)
    lvl, exp = progress["level"], progress["exp"]
    bar = level_progress_bar(lvl, exp)

    await update.message.reply_text(
        f"🎧 *С возвращением, {nickname}!*\n\n"
        f"📊 {bar}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Выбери действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


async def handle_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод никнейма
    """
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if not text or len(text) > 30:
        await update.message.reply_text("Никнейм должен быть от 1 до 30 символов. Попробуй ещё раз:")
        return

    save_user_nickname(user_id, text)
    user_states[user_id] = {'stage': 'menu', 'nickname': text}

    await update.message.reply_text(
        f"🎤 *Отлично, {text}!*\n\n"
        "Теперь можно искать треки, ставить оценки и копить EXP.\n"
        f"━━━━━━━━━━━━━━━━\n"
        "Выбери действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка 'Назад' — возвращает в главное меню.
    Если были показаны «Мои скачанные», удаляем пересланные аудио из чата.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    to_delete = state.get("messages_to_delete_on_back") or []
    for cid, mid in to_delete:
        try:
            await context.bot.delete_message(chat_id=cid, message_id=mid)
        except Exception:
            pass
    nickname = get_user_nickname(user_id) or state.get("nickname") or "Пользователь"
    user_states[user_id] = {"stage": "menu", "nickname": nickname}
    progress = get_user_progress(user_id)
    lvl, exp = progress["level"], progress["exp"]
    bar = level_progress_bar(lvl, exp)
    text = (
        f"🎵 *Главное меню*\n\n"
        f"Привет, {nickname}!\n\n"
        f"📊 {bar}\n"
        f"━━━━━━━━━━━━━━━━\n"
        "Выбери действие:"
    )
    try:
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    except Exception:
        try:
            await query.delete_message()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )