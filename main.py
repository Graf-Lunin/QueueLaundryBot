from flask import Flask, jsonify
import os
import threading
import time
import requests
import sqlite3
import datetime
import logging
from telebot import TeleBot, types
from threading import Timer

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


# Маршруты Flask
@app.route('/')
def index():
    return "Пустой сервер работает!!"


@app.route('/health')
def health_check():
    return "OK", 200


@app.route('/api/bookings')
def get_bookings():
    """API для получения всех текущих записей"""
    try:
        conn = sqlite3.connect('laundry.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, username, first_name, last_name, 
                   date, time_slot, full_name, room_number, created_at 
            FROM bookings 
            ORDER BY date, time_slot
        """)
        
        bookings = []
        for row in cursor.fetchall():
            bookings.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'first_name': row[3],
                'last_name': row[4],
                'date': row[5],
                'time_slot': row[6],
                'full_name': row[7],
                'room_number': row[8],
                'created_at': row[9]
            })
        
        conn.close()
        return jsonify(bookings)
    
    except Exception as e:
        logger.error(f"Ошибка при получении записей: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/bookings/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    """API для удаления записи"""
    try:
        conn = sqlite3.connect('laundry.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Запись удалена'})
    
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/admin')
def admin_panel():
    """Админ-панель для просмотра записей"""
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Админ-панель - Записи на стирку</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                text-align: center;
                color: #333;
                margin-bottom: 20px;
            }
            table { 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 20px;
                font-size: 14px;
            }
            th, td { 
                border: 1px solid #ddd; 
                padding: 10px; 
                text-align: left; 
            }
            th { 
                background-color: #4CAF50; 
                color: white; 
                position: sticky;
                top: 0;
            }
            tr:nth-child(even) { 
                background-color: #f9f9f9; 
            }
            tr:hover {
                background-color: #f1f1f1;
            }
            .delete-btn { 
                color: red; 
                cursor: pointer; 
                font-weight: bold;
                padding: 5px 10px;
                border: 1px solid red;
                border-radius: 3px;
                background: #ffe6e6;
            }
            .delete-btn:hover {
                background: #ffcccc;
            }
            .status {
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
            .status-complete {
                background: #d4edda;
                color: #155724;
            }
            .status-pending {
                background: #fff3cd;
                color: #856404;
            }
            .refresh-btn {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                cursor: pointer;
                margin-bottom: 10px;
            }
            .refresh-btn:hover {
                background: #0056b3;
            }
            .last-update {
                text-align: right;
                color: #666;
                font-size: 12px;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📋 Записи на стирку</h1>
            
            <div class="controls">
                <button class="refresh-btn" onclick="loadBookings()">🔄 Обновить</button>
                <div class="last-update" id="last-update">Последнее обновление: -</div>
            </div>
            
            <div id="bookings-container">
                <table id="bookings-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Дата</th>
                            <th>Время</th>
                            <th>ФИО</th>
                            <th>Комната</th>
                            <th>Username</th>
                            <th>User ID</th>
                            <th>Имя</th>
                            <th>Фамилия</th>
                            <th>Дата создания</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody id="bookings-body">
                        <tr>
                            <td colspan="11" style="text-align: center;">Загрузка данных...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            // Функция для обновления времени последнего обновления
            function updateLastUpdateTime() {
                const now = new Date();
                const timeString = now.toLocaleTimeString('ru-RU');
                document.getElementById('last-update').textContent = 
                    `Последнее обновление: ${timeString}`;
            }

            // Функция для загрузки записей
            function loadBookings() {
                fetch('/api/bookings')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Ошибка сети');
                        }
                        return response.json();
                    })
                    .then(data => {
                        const tbody = document.getElementById('bookings-body');
                        
                        if (data.length === 0) {
                            tbody.innerHTML = `
                                <tr>
                                    <td colspan="11" style="text-align: center; color: #666;">
                                        Нет активных записей
                                    </td>
                                </tr>
                            `;
                            return;
                        }
                        
                        tbody.innerHTML = '';
                        
                        data.forEach(booking => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${booking.id}</td>
                                <td>${booking.date || 'Не указано'}</td>
                                <td>${booking.time_slot || 'Не указано'}</td>
                                <td>${booking.full_name || 'Не указано'}</td>
                                <td>${booking.room_number || 'Не указано'}</td>
                                <td>${booking.username || 'Не указано'}</td>
                                <td>${booking.user_id}</td>
                                <td>${booking.first_name || 'Не указано'}</td>
                                <td>${booking.last_name || 'Не указано'}</td>
                                <td>${booking.created_at}</td>
                                <td>
                                    <span class="delete-btn" onclick="deleteBooking(${booking.id})">
                                        ❌ Удалить
                                    </span>
                                </td>
                            `;
                            tbody.appendChild(row);
                        });
                        
                        updateLastUpdateTime();
                    })
                    .catch(error => {
                        console.error('Ошибка:', error);
                        const tbody = document.getElementById('bookings-body');
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="11" style="text-align: center; color: red;">
                                    Ошибка загрузки данных. Попробуйте обновить страницу.
                                </td>
                            </tr>
                        `;
                    });
            }

            // Функция для удаления записи
            function deleteBooking(bookingId) {
                if (confirm('Вы уверены, что хотите удалить эту запись?')) {
                    fetch(`/api/bookings/${bookingId}`, {
                        method: 'DELETE'
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Ошибка сети');
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.success) {
                            alert('Запись удалена');
                            loadBookings(); // Перезагружаем список
                        } else {
                            alert('Ошибка при удалении: ' + (data.error || 'Неизвестная ошибка'));
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка:', error);
                        alert('Ошибка при удалении записи');
                    });
                }
            }

            // Автоматическое обновление каждые 30 секунд
            function startAutoRefresh() {
                setInterval(loadBookings, 30000);
            }

            // Загружаем записи при загрузке страницы
            document.addEventListener('DOMContentLoaded', function() {
                loadBookings();
                startAutoRefresh();
            });
        </script>
    </body>
    </html>
    '''


# Функции для работы с базой данных
def init_db():
    conn = sqlite3.connect('laundry.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
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
    conn.close()


def cleanup_old_records():
    try:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        conn = sqlite3.connect('laundry.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookings WHERE date < ?", (today,))
        conn.commit()
        conn.close()
        logger.info("Старые записи очищены")
    except Exception as e:
        logger.error(f"Ошибка при очистке записей: {e}")


def schedule_daily_cleanup():
    now = datetime.datetime.now()
    next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    seconds_until_midnight = (next_midnight - now).total_seconds()
    Timer(seconds_until_midnight, daily_cleanup_task).start()


def daily_cleanup_task():
    cleanup_old_records()
    schedule_daily_cleanup()


def get_booked_slots(date):
    try:
        conn = sqlite3.connect('laundry.db')
        cursor = conn.cursor()
        cursor.execute("SELECT time_slot FROM bookings WHERE date = ?", (date,))
        booked_slots = [row[0] for row in cursor.fetchall()]
        conn.close()
        return booked_slots
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
            conn = sqlite3.connect('laundry.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE user_id = ? AND full_name IS NULL", (message.from_user.id,))
            booking = cursor.fetchone()
            conn.close()

            if booking:
                process_booking_data(message, booking)
            else:
                conn = sqlite3.connect('laundry.db')
                cursor = conn.cursor()
                cursor.execute("""
                        SELECT id, full_name, room_number 
                        FROM bookings 
                        WHERE user_id = ? AND (full_name IS NULL OR room_number IS NULL)
                    """, (message.from_user.id,))
                booking = cursor.fetchone()
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
            conn = sqlite3.connect('laundry.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bookings (user_id, username, first_name, last_name, date, time_slot) VALUES (?, ?, ?, ?, ?, ?)",
                (call.from_user.id, call.from_user.username, call.from_user.first_name,
                 call.from_user.last_name, date, time_slot)
            )
            conn.commit()
            conn.close()

            bot.send_message(
                call.message.chat.id,
                "Введите ваше ФИО:",
                reply_markup=types.ReplyKeyboardRemove()
            )

            bot.answer_callback_query(call.id, "Вы выбрали время для стирки")

    except Exception as e:
        logger.error(f"Ошибка в handle_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def process_booking_data(message, booking):
    conn = sqlite3.connect('laundry.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT full_name, room_number FROM bookings WHERE id = ?", (booking[0],))
        current_data = cursor.fetchone()

        logger.info(f"Booking ID: {booking[0]}, Current data: {current_data}, Message text: '{message.text}'")

        if current_data[0] is None:
            cursor.execute(
                "UPDATE bookings SET full_name = ? WHERE id = ?",
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
                    "UPDATE bookings SET room_number = ? WHERE id = ?",
                    (message.text, booking[0])
                )
                conn.commit()

                cursor.execute("SELECT date, time_slot, full_name, room_number FROM bookings WHERE id = ?",
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
                cursor.execute("DELETE FROM bookings WHERE id = ?", (booking[0],))
                conn.commit()

                bot.send_message(
                    message.chat.id,
                    "❌ Неверный номер комнатф",
                    reply_markup=main_menu()
                )
        else:
            cursor.execute("DELETE FROM bookings WHERE id = ?", (booking[0],))
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
        conn.close()


def cancel_booking(message):
    try:
        conn = sqlite3.connect('laundry.db')
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bookings WHERE user_id = ?",
            (message.from_user.id,)
        )
        conn.commit()
        conn.close()

        bot.send_message(
            message.chat.id,
            "✅ Ваша запись успешно отменена.",
            reply_markup=main_menu()
        )

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
            response = requests.get(f'{base_url}/health', timeout=10)
            print(f"Self-ping successful: {response.status_code}")
        except Exception as e:
            print(f"Self-ping failed: {e}")
        time.sleep(300)  # Каждые 5 минут


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
