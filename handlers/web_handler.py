# handlers/web_handler.py
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
import json
from database import save_review


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает данные, отправленные из Telegram Mini App через tg.sendData()
    """
    try:
        data = update.message.web_app_data.data
        review = json.loads(data)

        # Сохраняем оценку
        save_review(
            user_id=review['user_id'],
            track_id=review['track_id'],
            ratings=review['ratings'],
            track_title=review['track_title'],
            track_artist=review['track_artist'],
            nickname=review.get('username', 'Аноним')
        )

        # Подтверждение пользователю
        await update.message.reply_text(
            f"✅ Спасибо за оценку!\n"
            f"Общий балл: *{review['total']}/90*\n\n"
            f"Трек: *{review['track_title']}* — {review['track_artist']}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при обработке оценки: {str(e)}")
        print("Ошибка в handle_webapp_data:", e)


# Готовый обработчик для добавления в app
webapp_handler = MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data)