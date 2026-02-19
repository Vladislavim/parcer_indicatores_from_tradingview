<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:F7A600,100:FF6B6B&height=190&section=header&text=LOCAL%20SIGNALS%20PRO&fontSize=44&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Bybit%20Trading%20Terminal&descSize=18&descAlignY=58" width="100%">

<a href="../../releases"><img src="https://img.shields.io/badge/Download-Releases-F7A600?style=for-the-badge&logo=github&logoColor=white" alt="Download"></a>
<a href="../../issues"><img src="https://img.shields.io/badge/Report-Issue-FF6B6B?style=for-the-badge&logo=github&logoColor=white" alt="Issues"></a>
<a href="../../stargazers"><img src="https://img.shields.io/badge/GitHub-Star-181717?style=for-the-badge&logo=github&logoColor=white" alt="Star"></a>

<br>
<br>

<img src="https://img.shields.io/github/stars/Vladislavim/parcer_indicatores_from_tradingview?style=for-the-badge&logo=github&label=Stars&color=181717" alt="Stars">
<img src="https://img.shields.io/github/forks/Vladislavim/parcer_indicatores_from_tradingview?style=for-the-badge&logo=github&label=Forks&color=24292e" alt="Forks">
<img src="https://img.shields.io/github/issues/Vladislavim/parcer_indicatores_from_tradingview?style=for-the-badge&logo=github&label=Issues&color=FF6B6B" alt="Issues Count">
<img src="https://img.shields.io/github/last-commit/Vladislavim/parcer_indicatores_from_tradingview?style=for-the-badge&logo=git&label=Last%20Commit&color=00D9A5" alt="Last Commit">

<br>

<img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Qt-PySide6-41CD52?style=flat-square&logo=qt&logoColor=white" alt="Qt">
<img src="https://img.shields.io/badge/ccxt-Bybit%20API-F7A600?style=flat-square&logoColor=white" alt="Bybit API">
<img src="https://img.shields.io/badge/Mode-Demo%2FTest-00D9A5?style=flat-square&logo=marketo&logoColor=white" alt="Mode">
<img src="https://img.shields.io/badge/Safety-Strict%20SL%2FTP-7D4CDB?style=flat-square&logo=shield&logoColor=white" alt="Safety">
<img src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Windows">

<br>

<a href="local-signals-app/BINANCE_DEMO_SETUP.md"><img src="https://img.shields.io/badge/Setup-Bybit%20Demo-0EA5E9?style=flat-square&logo=readme&logoColor=white" alt="Setup Guide"></a>
<a href="local-signals-app/run.py"><img src="https://img.shields.io/badge/Entry-run.py-111827?style=flat-square&logo=python&logoColor=white" alt="Entry"></a>
<a href="local-signals-app/ui/terminal_window.py"><img src="https://img.shields.io/badge/UI-terminal_window.py-4B5563?style=flat-square&logo=qt&logoColor=white" alt="Terminal UI"></a>

<br>
<br>

<img src="local-signals-app/content/ui%20git.jpg" alt="Local Signals Pro UI" width="90%">

</div>

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
