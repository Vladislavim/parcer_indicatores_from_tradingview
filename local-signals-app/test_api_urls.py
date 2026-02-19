"""Тест разных URL для Binance API"""
import ccxt
import json

# Загружаем ключи
with open('config.json', 'r') as f:
    config = json.load(f)

api_key = config['api_key']
api_secret = config['api_secret']

print("Проверка ключей:")
print(f"API Key длина: {len(api_key)}")
print(f"API Secret длина: {len(api_secret)}")
print(f"API Key начало: {api_key[:10]}...")
print(f"API Secret начало: {api_secret[:10]}...")
print()

print("Тестируем разные URL для Binance Futures API...\n")

# Тест 1: Demo Futures URL (demo-fapi.binance.com) с /fapi/v1
print("=" * 60)
print("Тест 1: demo-fapi.binance.com/fapi/v1")
print("=" * 60)
try:
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'urls': {
            'api': {
                'public': 'https://demo-fapi.binance.com/fapi/v1',
                'private': 'https://demo-fapi.binance.com/fapi/v1',
            }
        }
    })
    print(f"URL: {exchange.urls['api']['private']}")
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ! Подключение работает!")
    print(f"Баланс: {balance}")
except Exception as e:
    print(f"❌ ОШИБКА: {e}")

# Тест 2: Demo Futures без /fapi/v1
print("\n" + "=" * 60)
print("Тест 2: demo-fapi.binance.com (без /fapi/v1)")
print("=" * 60)
try:
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'urls': {
            'api': 'https://demo-fapi.binance.com'
        }
    })
    print(f"URL: {exchange.urls.get('api', 'N/A')}")
    balance = exchange.fetch_balance()
    print("✅ УСПЕХ! Подключение работает!")
    print(f"Баланс: {balance}")
except Exception as e:
    print(f"❌ ОШИБКА: {e}")

# Тест 3: Проверка времени сервера
print("\n" + "=" * 60)
print("Тест 3: Проверка времени сервера")
print("=" * 60)
try:
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'urls': {
            'api': {
                'public': 'https://demo-fapi.binance.com/fapi/v1',
                'private': 'https://demo-fapi.binance.com/fapi/v1',
            }
        }
    })
    time = exchange.fetch_time()
    print(f"✅ Время сервера: {time}")
except Exception as e:
    print(f"❌ ОШИБКА: {e}")

# Тест 4: Проверка exchangeInfo
print("\n" + "=" * 60)
print("Тест 4: Проверка exchangeInfo (без ключей)")
print("=" * 60)
try:
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'urls': {
            'api': {
                'public': 'https://demo-fapi.binance.com/fapi/v1',
                'private': 'https://demo-fapi.binance.com/fapi/v1',
            }
        }
    })
    markets = exchange.load_markets()
    print(f"✅ Загружено {len(markets)} рынков")
    print(f"Примеры: {list(markets.keys())[:5]}")
except Exception as e:
    print(f"❌ ОШИБКА: {e}")

print("\n" + "=" * 60)
print("Тестирование завершено")
print("=" * 60)
