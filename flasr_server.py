from flask import Flask
import asyncio
import os
import aiohttp
import threading
from apscheduler.schedulers.background import BackgroundScheduler


app = Flask(__name__)


@app.route('/')
def index():
    return "Пустой сервер работает!!"


@app.route('/health')
def health_check():
    return "OK", 200


async def ping_site():
    url = 'https://queuelaundrybot.onrender.com'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f'Pinged site, response status: {response.status}')
    except Exception as e:
        print(f'Error pinging site: {e}')


def run_ping_site():
    asyncio.run(ping_site())


def flask_run():
    print("Запуск Flask-сервера...")
    port = int(os.environ.get('PORT', 8888))
    from waitress import serve
    serve(app, host='0.0.0.0', port=port)


def start_flask_serve():
    flask_thread = threading.Thread(target=flask_run)
    flask_thread.daemon = True
    flask_thread.start()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_ping_site, 'interval', minutes=10)
    scheduler.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == '__main__':
    start_flask_serve()
