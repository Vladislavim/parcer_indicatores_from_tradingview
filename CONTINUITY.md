Goal (incl. success criteria):
- Keep project stable and usable as a Bybit trading terminal.
- Current goal: make terminal configurable for exchange/trading while enforcing safer production-like execution defaults.
- Success criteria:
  - persistent local storage in C: (not git repo) for journal/runtime,
  - Demo/Mainnet switch available in UI,
  - strict close policy defaults to Manual/SL/TP,
  - leverage defaults to 10x in strict mode,
  - app starts successfully.

Constraints/Assumptions:
- Do not commit without explicit user command.
- Cannot guarantee profit; only reduce avoidable risk via execution rules.

Key decisions:
- Added centralized storage paths in `C:\LocalSignalsPro` with one-time migration from legacy project files.
- Exposed network switch Demo/Mainnet in API card and persisted selection to config.
- Defaulted signal-based auto-closing to disabled (`allow_signal_close=false`), keeping Manual/SL/TP exits as primary behavior.
- Added strict 10x leverage default/override path (`strict_force_leverage_10x=true`).

State:
- Done:
  - Added `local-signals-app/core/storage.py`.
  - Updated journal path in `local-signals-app/ui/trade_journal.py` to persistent C: storage.
  - Updated runtime event/equity paths in `local-signals-app/ui/terminal_window.py` to persistent C: storage + migration.
  - Enabled Demo/Mainnet combo and sync with config in connection flow.
  - Updated auto/multi leverage defaults to 10x and wired strict-force leverage flag.
  - Disabled close-on-opposite-signal by default through settings plumbing.
  - Verified syntax via `python -m py_compile ...`.
  - Started app successfully (`STARTED_PID:18164`).
  - Verified files now present in `C:\LocalSignalsPro\...`.
- Now:
  - Local app launch checks on demand; latest user request was project start.
- Next:
  - Continue run/debug requests and packaging as needed.

Open questions (UNCONFIRMED if needed):
- UNCONFIRMED: user-preferred default for Mainnet switch safety (manual confirmation dialog before connect).

Working set (files/ids/commands):
- Files:
  - `CONTINUITY.md`
  - `local-signals-app/core/storage.py`
  - `local-signals-app/ui/trade_journal.py`
  - `local-signals-app/ui/terminal_window.py`
- Commands:
  - `python -m py_compile local-signals-app/ui/terminal_window.py local-signals-app/ui/trade_journal.py local-signals-app/core/storage.py`
  - `Start-Process python local-signals-app/run.py`
  - `Get-ChildItem C:\LocalSignalsPro -Recurse`
  - `python -m PyInstaller --noconfirm --windowed --name "Bybit Trading Terminal" --add-data "content;content" --add-data "config.json;." run.py`

Update 2026-02-20:
- Applied hard RR fix in terminal: TP is now always 2x SL distance (1:2) for auto/manual refined entries and Smart AI entries.
- Recompiled local-signals-app/ui/terminal_window.py successfully.
- App launch check OK: STARTED_PID:20292.

Update 2026-02-20 (precision hotfix):
- SL/TP normalization now uses exchange tick precision via price_to_precision fallbacking to market precision.
- Removed hard ound(..., 2) from strict order SL/TP trigger prices.
- _refine_sl_tp_prices now outputs exchange-precision prices (not fixed 2 decimals).
- UI/log formatting for low-priced coins switched to adaptive _fmt_price to avoid misleading same-looking prices.
- Verified with python -m py_compile local-signals-app/ui/terminal_window.py and app launch STARTED_PID:18828.

Update 2026-02-20 (mac package):
- Built mac handoff package at C:\Users\viman\OneDrive\Рабочий стол\mac for renatus\LocalSignalsPro-mac-20260220_190932.
- Added helper scripts: un_mac.command, uild_mac_app.command, README_MAC.md.
- Sanitized shipped config (config.json) with placeholder keys; cleared journal/runtime logs in package.
- Created transfer archive: C:\Users\viman\OneDrive\Рабочий стол\mac for renatus\LocalSignalsPro-mac-20260220_190932_bundle.zip.

Update 2026-02-20 (multi demo keys):
- API key loading order changed in ui/terminal_window.py: saved profile/QSettings first, config.json only fallback.
- This prevents config.json key from overwriting selected/default demo profile on startup.
- Verified compile and startup: python -m py_compile ... OK, app STARTED_PID:11376.

Update 2026-02-20 (key validation):
- Checked provided key against Bybit modes via ccxt.
- Result: DEMO -> etCode 10003 API key is invalid; MAINNET -> etch_balance OK.
- Conclusion: key belongs to Mainnet, not Demo.

Update 2026-02-20 (GitHub macOS build CI):
- Added workflow .github/workflows/build-macos-app.yml.
- Triggers: manual (workflow_dispatch) and push to main for local-signals-app/** changes.
- Uses macos-14 + Python 3.11, installs deps + PyInstaller, builds Bybit Trading Terminal.app.
- Sanitizes config.json and runtime/journal files before build to avoid shipping secrets in artifacts.
- Uploads zip artifact Bybit-Trading-Terminal-macOS.zip and raw .app as Actions artifact.

Update 2026-02-20 (workflow pushed):
- Committed macOS build workflow: 821161a (ci: add macOS app build workflow).
- Pushed to origin/main successfully (e8a5ad8..821161a).
- GitHub Actions Build macOS App should now appear in repository Actions tab.

Update 2026-02-24 (Windows exe guide):
- Added local-signals-app/WINDOWS_EXE_BUILD.md with Windows install/run/build .exe instructions (PyInstaller, troubleshooting, zip packaging).

Update 2026-02-24 (journal files check):
- User provided four 	rade_journal*.json files from Telegram Desktop.
- All four files are empty arrays ([], 7 bytes each), so no trades available for PnL/plus-minus analysis.
- Need non-empty journal file (e.g. C:\LocalSignalsPro\trade_journal.json) to compute table/stats.

Update 2026-02-25 (Windows handoff exe):
- User requested a Desktop folder with a shareable Windows `.exe` build.
- Prepared sanitized staging package on Desktop: `C:\Users\viman\OneDrive\Рабочий стол\Bybit-Terminal-Windows-EXE-20260225_090926`.
- Installed `pyinstaller` for current local Python.
- Built from `Bybit Trading Terminal.spec` successfully.
- Created handoff folder: `C:\Users\viman\OneDrive\Рабочий стол\Bybit-Terminal-Windows-EXE-READY-20260225_091536`.
- Created zip for transfer: `C:\Users\viman\OneDrive\Рабочий стол\Bybit-Terminal-Windows-EXE-READY-20260225_091536\Bybit Trading Terminal.zip`.
- Verified built exe launches: `STARTED_PID:1360`.

Update 2026-02-25 (run request):
- Started local project via `python local-signals-app/run.py`.
- Launch check OK: `STARTED_PID:20376`.

Update 2026-02-25 (run request repeat):
- Started local project via `python local-signals-app/run.py`.
- Launch check OK: `STARTED_PID:12372`.

Update 2026-02-25 (logic check long/short):
- Reviewed `ui/terminal_window.py` long/short branches for entry, SL/TP calculation, local TP/SL hit checks, and strict order open flow.
- Core price logic is mirrored for `buy`/`sell` and `long`/`short` (including RR 1:2 and low-price precision normalization).
- Remaining practical risk is exchange mode/permissions/hedge-mode behavior, not local long/short arithmetic symmetry.

Update 2026-02-25 (UX persistence + journal detail):
- Added immediate QSettings persistence for UI state: right-side tab, manual order inputs (symbol/size/leverage/SL/TP), auto panel selections, and multi-strategy selections (coins/strategies/risk/leverage) without requiring start/stop.
- Expanded open positions area (`positions_scroll` min height 260 and higher layout stretch) to reduce scrolling.
- Position rows now display richer reason text (open reason + risk model when available).
- Journal entries now store richer notes on close (strategy/open reason/risk model/close details) via `_build_trade_notes(...)`.
- Trade journal UI enhanced with close-reason summary line and extra columns for entry reason and premises/details parsed from notes.
- Verified syntax: `python -m py_compile local-signals-app/ui/terminal_window.py` and `.../trade_journal.py`.
- App launch check OK after changes: `STARTED_PID:12928`.

Update 2026-02-25 (new strategy: Gold/BTC inverse):
- Added optional strategy `gold_btc_inverse` in `local-signals-app/strategies/gold_btc_inverse.py`.
- Strategy logic: trades BTC only, uses gold (`XAUT/USDT:USDT`) regime as thesis filter plus BTC confirmation (EMA/RSI/return), ATR SL and fixed RR 1:2.
- Registered strategy in `local-signals-app/strategies/manager.py` (`STRATEGIES`).
- Verified compile and list visibility via `get_all_strategies()`; strategy id appears in UI source list.

Update 2026-02-25 (run after gold/btc strategy):
- Started local project via `python local-signals-app/run.py`.
- Launch check OK: `STARTED_PID:20432`.

Update 2026-02-25 (run request after timestamp issue):
- Started local project via `python local-signals-app/run.py`.
- Launch check OK: `STARTED_PID:21304`.

Update 2026-02-25 (MetaTrader integration question):
- User asked whether MetaTrader can be integrated as a separate window in current terminal.
- Feasible path identified: add optional MT tab/window bridge (launch MT terminal process and/or connect via MT5 Python API), separate from Bybit key flow.
- Constraint: MT demo/live uses account login/password/server, not Bybit API keys.
