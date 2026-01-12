from __future__ import annotations

import re
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from core.market import fetch_closed_ohlcv, make_exchange, map_symbols
from indicators.base import IndicatorBase


# ==========================
# Runtime helpers & caching
# ==========================

_lock = threading.Lock()

# source -> ccxt exchange
_ex_cache: Dict[str, Any] = {}
# source -> markets dict
_markets_cache: Dict[str, Dict[str, Any]] = {}
# (source, tv_symbol) -> ccxt_symbol
_symbol_cache: Dict[Tuple[str, str], str] = {}

# (indicator_key, source, timeframe, symbol) -> state
_state_cache: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}


def timeframe_to_ms(tf: str) -> int:
    """Best-effort timeframe parsing for bar-distance calculations."""
    s = (tf or "").strip().lower()
    m = re.fullmatch(r"(\d+)([mhdw])", s)
    if not m:
        # fallback: assume 1 minute
        return 60_000
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return n * 60_000
    if unit == "h":
        return n * 60 * 60_000
    if unit == "d":
        return n * 24 * 60 * 60_000
    if unit == "w":
        return n * 7 * 24 * 60 * 60_000
    return 60_000


def _get_exchange(source: str):
    with _lock:
        ex = _ex_cache.get(source)
        markets = _markets_cache.get(source)
        if ex is None or markets is None:
            ex = make_exchange(source)
            markets = ex.load_markets()
            _ex_cache[source] = ex
            _markets_cache[source] = markets
        return ex, markets


def _tv_to_ccxt_symbol(source: str, tv_symbol: str) -> str:
    key = (source, tv_symbol)
    with _lock:
        if key in _symbol_cache:
            return _symbol_cache[key]

    ex, markets = _get_exchange(source)
    mapped = map_symbols(source, [tv_symbol], markets)
    if not mapped:
        raise ValueError(f"Не удалось сопоставить символ: {tv_symbol}")
    ccxt_symbol = mapped[0][1]

    with _lock:
        _symbol_cache[key] = ccxt_symbol
    return ccxt_symbol


def _compact(text: str, max_len: int = 64) -> str:
    t = (text or "").strip().replace("\r", "")
    if not t:
        return ""
    first = t.split("\n", 1)[0].strip()
    if len(first) <= max_len:
        return first
    return first[: max_len - 1] + "…"


def run_indicator_get_signal(
    indicator: IndicatorBase,
    indicator_key: str,
    symbol: str,
    timeframe: str,
    source: str,
    *,
    status_from_state: Optional[Callable[[Dict[str, Any], Any], Optional[str]]] = None,
    detail_from_state: Optional[Callable[[Dict[str, Any], Any], Optional[str]]] = None,
    limit: int = 500,
) -> Tuple[str, str]:
    """
    Unified wrapper expected by core.worker:
      get_signal(symbol, timeframe, source) -> (status, detail)

    - status: bull / bear / neutral / na
    - detail: short string for UI/Telegram
    """

    state_key = (indicator_key, source, timeframe, symbol)
    with _lock:
        st = _state_cache.setdefault(state_key, {})

    # meta state (we keep algo state separate)
    meta = st.setdefault("meta", {})
    algo_state = st.setdefault("algo", {})
    meta.setdefault("tf_ms", timeframe_to_ms(timeframe))
    # give algo-state access to timeframe length (used by some indicators for cooloffs)
    algo_state.setdefault("tf_ms", meta["tf_ms"])

    # fetch candles
    try:
        ex, _ = _get_exchange(source)
        ccxt_symbol = _tv_to_ccxt_symbol(source, symbol)
        candles = fetch_closed_ohlcv(ex, ccxt_symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        return "na", f"data error: {e}"

    if not candles:
        return "na", "no candles"

    # compute
    try:
        params = indicator.default_params()
        signals = indicator.compute(candles, algo_state, params) or []
    except Exception as e:
        return "na", f"calc error: {e}"

    if signals:
        last = signals[-1]
        if last.type.upper() == "BUY":
            status = "bull"
        elif last.type.upper() == "SELL":
            status = "bear"
        else:
            status = "neutral"

        detail = _compact(last.message) or _compact(f"{last.name}: {last.type}")
        meta["last_status"] = status
        meta["last_detail"] = detail
        meta["last_signal_ts"] = getattr(last, "ts_ms", None)
        return status, detail

    # no new signal -> keep last known status if present
    status = str(meta.get("last_status") or "neutral")
    detail = str(meta.get("last_detail") or "")

    # optional: derive status/detail from current algo_state
    if status_from_state is not None:
        try:
            s2 = status_from_state(algo_state, candles)
            if s2:
                status = s2
        except Exception:
            pass
    if detail_from_state is not None and not detail:
        try:
            d2 = detail_from_state(algo_state, candles)
            if d2:
                detail = _compact(d2)
        except Exception:
            pass

    if not detail:
        detail = "—"

    meta["last_status"] = status
    meta["last_detail"] = detail
    return status, detail
