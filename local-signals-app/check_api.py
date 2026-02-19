"""Быстрая проверка Binance Demo Futures API (максимально стабильная)"""
import sys
import json

print("=" * 50)
print("Проверка Binance Demo Futures API")
print("=" * 50)

# Загружаем конфиг
try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    exchange_name = config.get("exchange")
    is_demo = (exchange_name == "BINANCE_DEMO") or bool(config.get("demo_mode"))

    if not config.get("api_key") or not config.get("api_secret"):
        raise ValueError("В config.json должны быть api_key и api_secret")

    print("\n✅ Config.json загружен")
    print(f"   Exchange: {exchange_name}")
    print(f"   Demo mode: {is_demo}")
    print(f"   Testnet: {config.get('testnet')}")
    print(f"   API Key preview: {(config.get('api_key') or '')[:10]}...")
except Exception as e:
    print(f"\n❌ Ошибка загрузки config.json: {e}")
    sys.exit(1)

# CCXT
try:
    import ccxt
    print("\n✅ CCXT установлен")
    print(f"   Версия: {ccxt.__version__}")
except ImportError:
    print("\n❌ CCXT не установлен")
    print("   Установите: pip install ccxt")
    sys.exit(1)

try:
    print("\n🔄 Подключение...")

    params = {
        "apiKey": config["api_key"],
        "secret": config["api_secret"],
        "enableRateLimit": True,
        "recvWindow": 60000,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,  # авто-подстройка времени
        },
    }

    if is_demo:
        # ВАЖНО: demo-fapi
        params["urls"] = {
            "api": {
                "public": "https://demo-fapi.binance.com/fapi/v1",
                "private": "https://demo-fapi.binance.com/fapi/v1",
            }
        }
        print("   Режим: Binance Demo Futures (demo-fapi)")
    else:
        # если вдруг используешь настоящий testnet (не demo.binance.com)
        print("   Режим: НЕ demo (проверь config)")
        if config.get("testnet"):
            print("   Testnet: да (sandbox_mode)")
        else:
            print("   Production: да")

    exchange = ccxt.binance(params)

    # sandbox_mode только для testnet, НЕ для demo-fapi
    if (not is_demo) and config.get("testnet"):
        exchange.set_sandbox_mode(True)

    print("   URLs(api):", exchange.urls.get("api"))

    # Публичная проверка (не требует ключей)
    print("\n🔄 Проверка времени сервера...")
    server_time = exchange.fetch_time()
    print("   Server time OK:", server_time)

    # Баланс: в demo используем только futures endpoint, без SAPI
    print("\n🔄 Получение баланса Futures (/fapi/v2/balance)...")
    try:
        raw = exchange.fapiPrivateGetBalance()
    except Exception:
        raw = exchange.fapiPrivateV2GetBalance()

    usdt = next((x for x in raw if x.get("asset") == "USDT"), None)
    if not usdt:
        raise RuntimeError(f"USDT не найден. Пример ответа: {raw[:2]}")

    free = float(usdt.get("availableBalance", 0) or 0)
    total = float(usdt.get("balance", 0) or 0)
    used = total - free

    print("\n✅ Подключение успешно!")
    print("\n💰 Баланс USDT (Futures):")
    print(f"   Свободно: ${free:,.2f}")
    print(f"   В позициях: ${used:,.2f}")
    print(f"   Всего: ${total:,.2f}")

    # Тикер
    print("\n🔄 Получение цены BTC...")
    ticker = exchange.fetch_ticker("BTC/USDT")
    print(f"   BTC/USDT last: {ticker.get('last')}")

    print("\n" + "=" * 50)
    print("✅ ГОТОВО")
    print("=" * 50)

except ccxt.AuthenticationError as e:
    print(f"\n❌ Auth error: {e}")
    print("\nЧто сделать, чтобы не ломалось:")
    print("1) В demo-ключе включи: Enable Reading + Enable Futures")
    print("2) Отключи IP restriction на время теста ИЛИ добавь текущий внешний IP")
    print("3) Убедись, что ключ создан именно на demo.binance.com (у тебя да)")
except ccxt.NetworkError as e:
    print(f"\n❌ Network error: {e}")
    print("Проверь интернет/VPN/блокировки.")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("\nНажмите Enter для выхода...")
input()
