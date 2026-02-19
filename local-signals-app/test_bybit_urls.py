"""Тест разных URL для Bybit API"""
import ccxt
import json
import os

# Загружаем ключи
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

API_KEY = config['api_key']
API_SECRET = config['api_secret']

print("=" * 60)
print("Тест разных Bybit API URLs")
print("=" * 60)
print(f"API Key: {API_KEY}")
print()

# Тест 1: Дефолтный URL
print("=" * 60)
print("Тест 1: Дефолтный Bybit URL")
print("=" * 60)
try:
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'},
    })
    
    print(f"URL: {exchange.urls['api']}")
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ!")
    print(f"Баланс USDT: {balance.get('USDT', {}).get('total', 0)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Тест 2: API v5
print("=" * 60)
print("Тест 2: Bybit API v5")
print("=" * 60)
try:
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'version': 'v5',
        },
    })
    
    print(f"URL: {exchange.urls['api']}")
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ!")
    print(f"Баланс USDT: {balance.get('USDT', {}).get('total', 0)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Тест 3: Contract Account
print("=" * 60)
print("Тест 3: Contract Account")
print("=" * 60)
try:
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'accountType': 'contract',
        },
    })
    
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ!")
    print(f"Баланс USDT: {balance.get('USDT', {}).get('total', 0)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Тест 4: Unified Account
print("=" * 60)
print("Тест 4: Unified Account")
print("=" * 60)
try:
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'accountType': 'unified',
        },
    })
    
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ!")
    print(f"Баланс USDT: {balance.get('USDT', {}).get('total', 0)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()
print("=" * 60)
print("Тестирование завершено")
print("=" * 60)
