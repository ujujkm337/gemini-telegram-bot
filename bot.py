# bot.py
import os
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler # Для Keep-Alive
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai.errors import APIError

# --- 1. Настройки и Константы ---

# Ключи считываются из переменных окружения (Secrets/Environment Variables).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080)) # Порт для Render Keep-Alive
MODEL_NAME = "gemini-2.5-flash"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. Инициализация Клиента Gemini и Словарь Чатов ---
gemini_client = None 
chat_sessions = {} 

if GEMINI_API_KEY and TELEGRAM_BOT_TOKEN:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Клиент Gemini инициализирован успешно.")
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации клиента Gemini: {e}")
else:
    logger.error("Критическая ошибка: Ключи API не найдены в переменных окружения.")


# --- 3. Обработчики Команд и Сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка команды /start. Сброс памяти."""
    
    chat_id = update.message.chat_id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
        
    await update.message.reply_text(
        'Привет! Я бот на базе Gemini. Я помню контекст разговора. Задайте мне вопрос! Чтобы сбросить память, используйте команду /start.'
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет запрос в текущую сессию чата Gemini."""
    global gemini_client, chat_sessions
    
    if not gemini_client:
        await update.message.reply_text("Критическая ошибка: Сервис неактивен. Проверьте логи на сервере.")
        return
        
    user_prompt = update.message.text
    chat_id = update.message.chat_id
    
    await update.message.chat.send_action(action='typing')

    # Создаем или получаем сессию чата
    if chat_id not in chat_sessions:
        try:
            chat_sessions[chat_id] = gemini_client.chats.create(model=MODEL_NAME)
            logger.info(f"Создана новая сессия чата для пользователя {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при создании сессии чата: {e}")
            await update.message.reply_text("Не удалось начать новую сессию чата.")
            return

    current_chat = chat_sessions[chat_id]

    try:
        response = current_chat.send_message(user_prompt)

        if response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("Извините, Gemini не смог сгенерировать ответ.")

    except APIError as e:
        logger.error(f"Ошибка API Gemini: {e}")
        await update.message.reply_text("Произошла ошибка при обращении к Gemini API. Возможно, превышены лимиты.")
    except Exception as e:
        error_message = f"Непредвиденная ошибка: {e}"
        logger.error(error_message)
        await update.message.reply_text(
            "Произошла непредвиденная ошибка. Попробуйте попросить меня разделить запрос на части."
        )


# --- 4. Keep-Alive Server для Render ---

class KeepAliveHandler(BaseHTTPRequestHandler):
    """Простой HTTP-обработчик, который отвечает 200 OK на любые запросы."""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Telegram Bot is Alive')

def run_keep_alive_server():
    """Запускает HTTP-сервер в отдельном потоке."""
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, KeepAliveHandler)
    logger.info(f"Keep-Alive Server запущен на порту {PORT}")
    httpd.serve_forever()


# --- 5. Главная Функция Запуска ---

def main() -> None:
    """Запускает бота и Keep-Alive сервер."""
    if not TELEGRAM_BOT_TOKEN or not gemini_client:
        logger.critical("Невозможно запустить бота: Проверьте ключи и инициализацию.")
        return

    # Запускаем Keep-Alive сервер в отдельном потоке
    server_thread = Thread(target=run_keep_alive_server)
    server_thread.start()
    
    # Запускаем Telegram-бота
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Telegram Бот запущен. Опрос Telegram начат.")
    application.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()
