from flask import Flask
import os
import threading
import time
import requests
import datetime
import logging
from telebot import TeleBot, types
from threading import Timer
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.parse

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Flask приложения
app = Flask(__name__)

# Конфигурация бота
BOT_TOKEN = "8290372805:AAGwVsrTZYXgZYOGWWB_Eq9DtlNC6KkAGto"
DEVELOPER_LINK = "https://t.me/Retur8827"
bot = TeleBot(BOT_TOKEN)

# Глобальные переменные
TIME_SLOTS = [
    "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
    "16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00",
    "20:00-21:00", "21:00-22:00", "22:00-23:00"
]

# Конфигурация PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://laundry_bot_user:V4GTJFTttRgG6C87DBb1BHpltszTSaBm@dpg-d348jbfdiees739lol9g-a/laundry_bot')

# Парсинг URL базы данных
result = urllib.parse.urlparse(DATABASE_URL)
db_config = {
    'dbname': result.path[1:],
    'user': result.username,
    'password': result.password,
    'host': result.hostname,
    'port': result.port
}

# Маршруты Flask
@app.route('/')
def index():
    return "Пустой сервер работает!!"

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/keepalive')
def keep_alive():
    return "Server is alive", 200

# Функции для работы с базой данных PostgreSQL
def get_connection():
    """Создание соединения с PostgreSQL"""
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        return None

def init_db():
    """Инициализация таблиц в PostgreSQL"""
    try:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                date TEXT,
                time_slot TEXT,
                full_name TEXT,
                room_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("База данных PostgreSQL инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")

def cleanup_old_records():
    """Очистка старых записей"""
    try:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookings WHERE date < %s", (today,))
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Старые записи очищены")
    except Exception as e:
        logger.error(f"Ошибка при очистке записей: {e}")

def schedule_daily_cleanup():
    """Планирование ежедневной очистки"""
    now = datetime.datetime.now()
    next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    seconds_until_midnight = (next_midnight - now).total_seconds()
    Timer(seconds_until_midnight, daily_cleanup_task).start()

def daily_cleanup_task():
    """Задача ежедневной очистки"""
    cleanup_old_records()
    schedule_daily_cleanup()

def get_booked_slots(date):
    """Получение занятых слотов"""
    try:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT time_slot FROM bookings WHERE date = %s", (date,))
            booked_slots = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return booked_slots
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении занятых слотов: {e}")
        return []

# Функции для работы с Telegram ботом
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    today_btn = types.KeyboardButton("📅 Сегодня")
    tomorrow_btn = types.KeyboardButton("📆 Завтра")
    developer_btn = types.KeyboardButton("Разработчик")
    cancel_btn = types.KeyboardButton("❌ Отменить запись")
    markup.add(today_btn, tomorrow_btn, developer_btn, cancel_btn)
    return markup

def cancel_menu():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    cancel_btn = types.KeyboardButton("❌ Отменить запись")
    markup.add(cancel_btn)
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в бот для записи на стирку!\n\n"
        "Правила:\n\n"
        "- указывать верное ФИО (можно только фамилию и инициалы)\n\n"
        "- указывать верный номер комнаты\n\n"
        "- запрещено каким-либо образом создавать более одной заявки\n\n"
        "За нарушение правил вы можете быть внесены в чёрный список. Имейте ввиду, что я вижу, кто и когда создаёт заявки\n\n"
        "ПРОДОЛЖАЯ РАБОТУ С БОТОМ, ВЫ ДАЁТЕ СОГЛАСИЕ НА ОБРАБОТКУ ВВЕДЁННЫХ ВАМИ ДАННЫХ\n\n"
        "Выберите день для записи:",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        if message.text == "Разработчик":
            bot.send_message(
                message.chat.id,
                f"Связь с разработчиком: {DEVELOPER_LINK}",
                reply_markup=main_menu()
            )

        elif message.text == "❌ Отменить запись":
            cancel_booking(message)

        elif message.text == "📅 Сегодня":
            show_time_slots(message, 0)

        elif message.text == "📆 Завтра":
            show_time_slots(message, 1)

        else:
            conn = get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM bookings WHERE user_id = %s AND full_name IS NULL", (message.from_user.id,))
                booking = cursor.fetchone()
                cursor.close()
                conn.close()

                if booking:
                    process_booking_data(message, booking)
                else:
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT id, full_name, room_number 
                            FROM bookings 
                            WHERE user_id = %s AND (full_name IS NULL OR room_number IS NULL)
                        """, (message.from_user.id,))
                        booking = cursor.fetchone()
                        cursor.close()
                        conn.close()

                        logger.info(f"Active booking found: {booking}")

                        if booking:
                            process_booking_data(message, booking)
                        else:
                            bot.send_message(
                                message.chat.id,
                                "Пожалуйста, используйте кнопки меню:",
                                reply_markup=main_menu()
                            )
                    else:
                        bot.send_message(
                            message.chat.id,
                            "Ошибка подключения к базе данных",
                            reply_markup=main_menu()
                        )
            else:
                bot.send_message(
                    message.chat.id,
                    "Ошибка подключения к базе данных",
                    reply_markup=main_menu()
                )

    except Exception as e:
        logger.error(f"Ошибка в handle_text: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте позже.")

def show_time_slots(message, days_offset):
    target_date = (datetime.datetime.now() + datetime.timedelta(days=days_offset)).strftime("%d-%m-%Y")
    booked_slots = get_booked_slots(target_date)
    markup = types.InlineKeyboardMarkup()

    for slot in TIME_SLOTS:
        if slot not in booked_slots:
            btn = types.InlineKeyboardButton(
                f"✅ {slot}",
                callback_data=f"slot_{target_date}_{slot}"
            )
            markup.add(btn)

    if not markup.keyboard:
        bot.send_message(
            message.chat.id,
            "❌ На этот день все временные слоты заняты.",
            reply_markup=main_menu()
        )
    else:
        day_name = "сегодня" if days_offset == 0 else "завтра"
        bot.send_message(
            message.chat.id,
            f"🕐 Выберите время для стирки ({day_name} {target_date}):",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data.startswith("slot_"):
            _, date, time_slot = call.data.split("_", 2)
            conn = get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bookings (user_id, username, first_name, last_name, date, time_slot) VALUES (%s, %s, %s, %s, %s, %s)",
                    (call.from_user.id, call.from_user.username, call.from_user.first_name,
                     call.from_user.last_name, date, time_slot)
                )
                conn.commit()
                cursor.close()
                conn.close()

                bot.send_message(
                    call.message.chat.id,
                    "Введите ваше ФИО:",
                    reply_markup=types.ReplyKeyboardRemove()
                )

                bot.answer_callback_query(call.id, "Вы выбрали время для стирки")
            else:
                bot.answer_callback_query(call.id, "Ошибка подключения к базе данных")

    except Exception as e:
        logger.error(f"Ошибка в handle_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

def process_booking_data(message, booking):
    conn = get_connection()
    if not conn:
        bot.send_message(message.chat.id, "Ошибка подключения к базе данных")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, room_number FROM bookings WHERE id = %s", (booking[0],))
        current_data = cursor.fetchone()

        logger.info(f"Booking ID: {booking[0]}, Current data: {current_data}, Message text: '{message.text}'")

        if current_data[0] is None:
            cursor.execute(
                "UPDATE bookings SET full_name = %s WHERE id = %s",
                (message.text, booking[0])
            )
            conn.commit()

            bot.send_message(
                message.chat.id,
                "🏠 Введите номер комнаты:"
            )

        elif current_data[1] is None and len(message.text) == 3:
            if message.text[0] in "1234567890" and message.text[1] in "1234567890" and message.text[2] in "1234567890":
                cursor.execute(
                    "UPDATE bookings SET room_number = %s WHERE id = %s",
                    (message.text, booking[0])
                )
                conn.commit()

                cursor.execute("SELECT date, time_slot, full_name, room_number FROM bookings WHERE id = %s",
                               (booking[0],))
                updated_data = cursor.fetchone()

                logger.info(f"Updated data: {updated_data}")

                if updated_data:
                    bot.send_message(
                        message.chat.id,
                        f"✅ Запись успешно создана!\n\n"
                        f"📅 Дата: {updated_data[0]}\n"
                        f"🕐 Время: {updated_data[1]}\n"
                        f"👤 ФИО: {updated_data[2]}\n"
                        f"🏠 Комната: {updated_data[3]}",
                        reply_markup=cancel_menu()
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ Ошибка при создании записи",
                        reply_markup=main_menu()
                    )
            else:
                cursor.execute("DELETE FROM bookings WHERE id = %s", (booking[0],))
                conn.commit()

                bot.send_message(
                    message.chat.id,
                    "❌ Неверный номер комнаты",
                    reply_markup=main_menu()
                )
        else:
            cursor.execute("DELETE FROM bookings WHERE id = %s", (booking[0],))
            conn.commit()

            bot.send_message(
                message.chat.id,
                "❌ Неверный номер комнаты",
                reply_markup=main_menu()
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке данных бронирования: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при обработке данных")

    finally:
        cursor.close()
        conn.close()

def cancel_booking(message):
    try:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM bookings WHERE user_id = %s",
                (message.from_user.id,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            bot.send_message(
                message.chat.id,
                "✅ Ваша запись успешно отменена.",
                reply_markup=main_menu()
            )
        else:
            bot.send_message(message.chat.id, "Ошибка подключения к базе данных")

    except Exception as e:
        logger.error(f"Ошибка при отмене записи: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при отмене записи")

# Функция для поддержания активности сервера
def ping_self():
    """Пинг самого себя для поддержания активности"""
    while True:
        try:
            # Получаем URL из переменных окружения или используем дефолтный
            base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:4000')
            response = requests.get(f'{base_url}/keepalive', timeout=10)
            print(f"Self-ping successful: {response.status_code}")
        except Exception as e:
            print(f"Self-ping failed: {e}")
        time.sleep(10)  # Каждые 10 секунд

def start_bot():
    """Запуск Telegram бота"""
    logger.info("Бот запущен...")
    bot.infinity_polling()

def start_flask_server():
    """Запуск Flask сервера"""
    port = int(os.environ.get('PORT', 4000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )

if __name__ == '__main__':
    # Инициализация базы данных
    init_db()

    # Запуск ежедневной очистки
    schedule_daily_cleanup()

    # Запуск keep-alive в фоновом режиме
    threading.Thread(target=ping_self, daemon=True).start()

    # Запуск Flask сервера в отдельном потоке
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()

    # Запуск бота в основном потоке
    start_bot()
