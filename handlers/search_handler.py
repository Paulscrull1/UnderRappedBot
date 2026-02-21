# handlers/search_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from yandex import search_track
from database import save_review
from keyboards import rating_buttons, after_review_buttons, back_to_menu_button
from utils import user_states, CRITERIA_NAMES
from handlers.track_card_handler import send_track_card


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        "🔍 *Поиск трека*\n\n"
        "Напиши в формате:\n*Исполнитель — Название трека*\n\n"
        "Пример: `Платина — Бассок`",
        parse_mode="Markdown",
        reply_markup=back_to_menu_button(),
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if query.startswith('/'):
        return

    await update.message.reply_text("🔍 Ищу трек...")
    tracks = search_track(query, limit=1)

    if not tracks:
        await update.message.reply_text(
            "❌ Не нашёл такой трек. Попробуй уточнить:\nИсполнитель — Название",
            reply_markup=back_to_menu_button(),
        )
        return

    user_id = update.message.from_user.id
    await send_track_card(update.message, tracks[0]["id"], user_id, track_dict=tracks[0])


async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]['stage'] != 'rating':
        await query.answer("Сессия истекла.", show_alert=True)
        try:
            await query.message.delete()
        except:
            pass
        return

    state = user_states[user_id]
    current = state['current_criteria']
    await query.answer()

    if data == "cancel_rating":
        await query.edit_message_text("❌ Оценка отменена.", reply_markup=back_to_menu_button())
        if user_id in user_states:
            del user_states[user_id]
        return

    if data.startswith("rate_"):
        try:
            score = int(data.split("_")[1])
            if not 1 <= score <= 10:
                raise ValueError()
        except ValueError:
            await query.answer("Введите число от 1 до 10.", show_alert=True)
            return

        state['ratings'][current] = score
        criteria_list = ["rhymes", "rhythm", "style", "charisma", "vibe"]
        idx = criteria_list.index(current)

        if idx < len(criteria_list) - 1:
            next_crit = criteria_list[idx + 1]
            state['current_criteria'] = next_crit
            await query.edit_message_text(
                f"🔹 *{CRITERIA_NAMES[next_crit]}*\nВыбери оценку от 1 до 10:",
                parse_mode='Markdown',
                reply_markup=rating_buttons()
            )
        else:
            total = sum(state['ratings'].values())
            result_text = (
                f"✅ Оценка завершена!\nОбщий балл: *{total}/50*\n\n"
                f"🔸 Рифмы/образы: {state['ratings']['rhymes']}\n"
                f"🔸 Структура/ритмика: {state['ratings']['rhythm']}\n"
                f"🔸 Реализация стиля: {state['ratings']['style']}\n"
                f"🔸 Индивидуальность/харизма: {state['ratings']['charisma']}\n"
                f"🔸 Атмосфера/вайб: {state['ratings']['vibe']}"
            )
            await query.edit_message_text(result_text, parse_mode='Markdown')

            save_review(
                user_id=user_id,
                track_id=state['track_id'],
                ratings=state['ratings'],
                track_title=state['track_title'],
                track_artist=state['track_artist'],
                nickname=state['nickname'],
                genre=state['genre']
            )

            del user_states[user_id]

            await query.message.reply_text(
                "✅ Оценка сохранена!",
                reply_markup=after_review_buttons(track_id=state['track_id'])
            )