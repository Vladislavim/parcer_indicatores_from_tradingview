# Local Signals Pro (Bybit Trading Terminal)

Local desktop terminal for Bybit futures demo/test trading with manual orders, auto mode, and multi-strategy execution.

Current app format:
- one main terminal window;
- Bybit API connection;
- manual and automated orders;
- strategy panel;
- trade journal and runtime logs.

## Current Safety Behavior

- New orders run in strict mode: no position should remain open without `SL/TP`.
- If exchange-side `SL/TP` is rejected in order params, the app retries via a dedicated trading-stop API call.
- If protection still cannot be set, the position is closed immediately.
- Existing positions are periodically synced for protective `SL/TP`.

## Requirements

- Python `3.10+`
- Windows (primary target)

Dependencies:
- `PySide6>=6.10.0`
- `ccxt>=4.4.0`
- `requests>=2.32.0`

## Quick Start

```bash
git clone https://github.com/Vladislavim/parcer_indicatores_from_tradingview.git
cd parcer_indicatores_from_tradingview
pip install -r local-signals-app/requirements.txt
python local-signals-app/run.py
```

## Bybit Demo API Setup

Setup guide:
- `local-signals-app/BINANCE_DEMO_SETUP.md` (legacy filename, used for current `BYBIT_DEMO` flow)

Minimal `local-signals-app/config.json`:

```json
{
  "exchange": "BYBIT_DEMO",
  "demo_mode": true,
  "api_key": "YOUR_BYBIT_DEMO_API_KEY",
  "api_secret": "YOUR_BYBIT_DEMO_API_SECRET"
}
```

API check:

```bash
python local-signals-app/test_bybit_api.py
```

## Useful Scripts

- `local-signals-app/start.bat` - quick Windows start
- `local-signals-app/diagnose.bat` - environment diagnostics
- `local-signals-app/check_api.py` - API connectivity check

## Project Layout

- `local-signals-app/run.py` - app entry point
- `local-signals-app/ui/terminal_window.py` - main terminal UI
- `local-signals-app/strategies/` - strategy logic and manager
- `local-signals-app/core/` - config and market helpers
- `local-signals-app/data/` - runtime data (equity/events)

## Risk Notice

This is trading software. Any trading can cause losses. Use demo/test mode before real funds.
