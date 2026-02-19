"""Quick Bybit Demo API check."""
import json
import os
import sys

import ccxt


def main() -> int:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    api_key = (config.get("api_key") or "").strip()
    api_secret = (config.get("api_secret") or "").strip()
    if not api_key or not api_secret:
        print("ERROR: api_key/api_secret are empty in config.json")
        return 1

    print("=" * 60)
    print("Bybit Demo API check")
    print("=" * 60)
    print(f"API key prefix: {api_key[:8]}...")

    exchange = ccxt.bybit(
        {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "accountType": "unified"},
        }
    )
    exchange.enable_demo_trading(True)

    print("Connecting to Bybit Demo...")
    balance = exchange.fetch_balance()
    usdt = balance.get("USDT", {})
    free = float(usdt.get("free") or 0)
    total = float(usdt.get("total") or 0)
    print(f"USDT free: {free:.2f}")
    print(f"USDT total: {total:.2f}")

    ticker = exchange.fetch_ticker("BTC/USDT:USDT")
    print(f"BTC last: {float(ticker.get('last') or 0):,.2f}")

    positions = exchange.fetch_positions()
    opened = [p for p in positions if float(p.get("contracts") or 0) > 0]
    print(f"Open positions: {len(opened)}")
    print("OK: Bybit Demo API works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
