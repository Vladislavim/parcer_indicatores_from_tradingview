"""Детальный тест Bybit API с логированием"""
import requests
import time
import hmac
import hashlib
import json
import os
from urllib.parse import urlencode

# Загружаем ключи
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

API_KEY = config['api_key']
API_SECRET = config['api_secret']

print("=" * 60)
print("Детальный тест Bybit API")
print("=" * 60)
print(f"API Key: {API_KEY}")
print(f"API Secret: {API_SECRET[:10]}...{API_SECRET[-10:]}")
print()

# Тест 1: Публичный запрос (без авторизации)
print("=" * 60)
print("Тест 1: Публичный запрос - время сервера")
print("=" * 60)
try:
    url = "https://api.bybit.com/v5/market/time"
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("✅ Публичный API работает")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Тест 2: Приватный запрос - баланс
print("=" * 60)
print("Тест 2: Приватный запрос - баланс кошелька")
print("=" * 60)

try:
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    
    # Параметры для Unified Account
    params = {
        "accountType": "UNIFIED"
    }
    
    # Создаем строку для подписи
    param_str = urlencode(sorted(params.items()))
    sign_str = timestamp + API_KEY + recv_window + param_str
    
    print(f"Timestamp: {timestamp}")
    print(f"Recv Window: {recv_window}")
    print(f"Params: {param_str}")
    print(f"Sign String: {sign_str}")
    print()
    
    # Создаем подпись
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    print()
    
    # Заголовки
    headers = {
        'X-BAPI-API-KEY': API_KEY,
        'X-BAPI-SIGN': signature,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': recv_window,
        'Content-Type': 'application/json'
    }
    
    url = f"https://api.bybit.com/v5/account/wallet-balance?{param_str}"
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print()
    
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('retCode') == 0:
            print("✅ УСПЕХ! API ключи работают!")
        else:
            print(f"❌ Ошибка API: {data}")
    else:
        print(f"❌ HTTP ошибка: {response.status_code}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Тестирование завершено")
print("=" * 60)
