from flask import Flask
import os
import threading
import time
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return "Пустой сервер работает!!"

@app.route('/health')
def health_check():
    return "OK", 200

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
        time.sleep(10)  # Каждые 5 минут

if __name__ == '__main__':
    # Запускаем keep-alive в фоновом режиме
    threading.Thread(target=ping_self, daemon=True).start()
    
    # Важно: используем порт из переменной окружения
    port = int(os.environ.get('PORT', 4000))
    
    # Запускаем Flask с правильными параметрами
    app.run(
        host='0.0.0.0',  # Слушаем все интерфейсы
        port=port,
        debug=False
    )
