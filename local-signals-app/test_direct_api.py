"""Прямой тест Binance Demo Futures API"""
import requests
import time
import hmac
import hashlib
import json
from urllib.parse import urlencode

# Загружаем ключи
import os
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

API_KEY = config['api_key']
API_SECRET = config['api_secret']
BASE_URL = 'https://demo-fapi.binance.com'

def create_signature(params, secret):
    """Создать подпись для запроса"""
    query_string = urlencode(params)
    signature = hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

print("=" * 60)
print("Тест 1: Проверка времени сервера (без авторизации)")
print("=" * 60)
try:
    response = requests.get(f'{BASE_URL}/fapi/v1/time')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("Тест 2: Проверка exchangeInfo (без авторизации)")
print("=" * 60)
try:
    response = requests.get(f'{BASE_URL}/fapi/v1/exchangeInfo')
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Symbols count: {len(data.get('symbols', []))}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("Тест 3: Проверка баланса (с авторизацией)")
print("=" * 60)
try:
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 5000
    }
    
    signature = create_signature(params, API_SECRET)
    params['signature'] = signature
    
    headers = {
        'X-MBX-APIKEY': API_KEY
    }
    
    url = f'{BASE_URL}/fapi/v2/balance'
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Params: {params}")
    
    response = requests.get(url, headers=headers, params=params)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ УСПЕХ! Подключение работает!")
        data = response.json()
        for asset in data:
            if float(asset.get('balance', 0)) > 0:
                print(f"  {asset['asset']}: {asset['balance']}")
    else:
        print(f"❌ Ошибка: {response.json()}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("Тест 4: Проверка account info (с авторизацией)")
print("=" * 60)
try:
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 5000
    }
    
    signature = create_signature(params, API_SECRET)
    params['signature'] = signature
    
    headers = {
        'X-MBX-APIKEY': API_KEY
    }
    
    url = f'{BASE_URL}/fapi/v2/account'
    response = requests.get(url, headers=headers, params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ УСПЕХ! Account info получен!")
        data = response.json()
        print(f"Total Wallet Balance: {data.get('totalWalletBalance', 'N/A')}")
    else:
        print(f"❌ Ошибка: {response.text}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("Тестирование завершено")
print("=" * 60)
