"""Тест Bybit Real API"""
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
print("Тест Bybit Real API (Unified Account)")
print("=" * 60)
print(f"API Key: {API_KEY[:20]}...")
print()

try:
    # Создаём exchange БЕЗ Unified Account
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
        },
    })
    
    print("🔄 Подключение к Bybit...")
    print()
    
    # Тест 1: Получение баланса
    print("=" * 60)
    print("Тест 1: Получение баланса")
    print("=" * 60)
    balance = exchange.fetch_balance()
    
    print("✅ Подключение успешно!")
    print()
    print("Баланс USDT:")
    usdt = balance.get('USDT', {})
    print(f"  Свободно: {usdt.get('free', 0)} USDT")
    print(f"  Всего: {usdt.get('total', 0)} USDT")
    print()
    
    # Тест 2: Получение позиций
    print("=" * 60)
    print("Тест 2: Получение позиций")
    print("=" * 60)
    positions = exchange.fetch_positions()
    open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
    
    if open_positions:
        print(f"Открытых позиций: {len(open_positions)}")
        for pos in open_positions:
            print(f"  {pos.get('symbol')}: {pos.get('side')} {pos.get('contracts')}")
    else:
        print("Нет открытых позиций")
    print()
    
    # Тест 3: Получение цены BTC
    print("=" * 60)
    print("Тест 3: Получение цены BTC/USDT:USDT")
    print("=" * 60)
    ticker = exchange.fetch_ticker('BTC/USDT:USDT')
    print(f"✅ Цена BTC: ${ticker['last']:,.2f}")
    print(f"   24h изменение: {ticker.get('percentage', 0):.2f}%")
    print()
    
    print("=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 60)
    print()
    print("Теперь можно запускать приложение:")
    print("  python local-signals-app\\run.py")
    print("  или")
    print("  local-signals-app\\start.bat")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print()
    print("Проверь:")
    print("1. API ключи созданы на bybit.com (не testnet)")
    print("2. Разрешения: 'Чтение и запись' + 'Торговать'")
    print("3. IP ограничения: 'Нет ограничений'")
    print("4. Unified Trading Account включен")

