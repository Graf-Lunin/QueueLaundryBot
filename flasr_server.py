from flask import Flask
import asyncio
import os
import aiohttp
from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve

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

def start_flask_server():
    """Запускает Flask сервер в отдельном потоке"""
    def run_server():
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_ping_site, 'interval', minutes=10)
        scheduler.start()
        
        port = int(os.environ.get('PORT', 8888))
        print(f"Запуск Flask сервера на порту {port}...")
        serve(app, host='0.0.0.0', port=port)
    
    import threading
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
