import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai.errors import APIError

# --- 1. Настройки и Константы ---

# 🛑 БЕЗОПАСНО: Ключи считываются из переменных окружения!
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

MODEL_NAME = "gemini-2.5-flash"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. Инициализация Клиента Gemini ---
gemini_client = None

if GEMINI_API_KEY and TELEGRAM_BOT_TOKEN:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Клиент Gemini инициализирован успешно (ключи загружены из окружения).")
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации клиента Gemini: {e}")
else:
    logger.error("Критическая ошибка: Ключи GEMINI_API_KEY или TELEGRAM_BOT_TOKEN не найдены в переменных окружения.")


# --- 3. Обработчики Команд и Сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Привет! Я бот на базе Gemini. Просто отправь мне сообщение!'
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет запрос в Gemini и возвращает ответ."""
    global gemini_client

    if not gemini_client:
        await update.message.reply_text("Критическая ошибка: Сервис неактивен. Проверьте логи на сервере.")
        return

    user_prompt = update.message.text
    await update.message.chat.send_action(action='typing')

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt
        )

        if response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("Извините, Gemini не смог сгенерировать ответ.")

    except APIError as e:
        logger.error(f"Ошибка API Gemini: {e}")
        # Теперь эта ошибка (400 FAILED_PRECONDITION) должна исчезнуть, так как бот будет запущен в разрешенном регионе.
        await update.message.reply_text("Произошла ошибка при обращении к Gemini API. Возможно, превышены лимиты.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        await update.message.reply_text("Произошла непредвиденная ошибка.")


# --- 4. Главная Функция Запуска ---

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("Невозможно запустить бота: TELEGRAM_BOT_TOKEN не найден.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
    application.run_polling(poll_interval=3)


if __name__ == '__main__':
    main()