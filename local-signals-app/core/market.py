from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple
import ccxt

@dataclass
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

def _norm_symbol_input(s: str) -> str:
    return s.strip().upper()

def tv_to_ccxt_symbol_bybit_perp(tv_symbol: str, markets: Dict) -> str:
    """
    TradingView Bybit perp: BTCUSDT.P
    ccxt bybit swap symbol is usually like: BTC/USDT:USDT
    We match by market['id'] == 'BTCUSDT' and swap+linear.
    """
    s = _norm_symbol_input(tv_symbol)
    base = s.replace(".P", "")
    candidates = []
    for sym, m in markets.items():
        if not m.get("swap"):
            continue
        if m.get("linear") is False:
            continue
        if m.get("id") == base:
            candidates.append(sym)
    if not candidates:
        raise ValueError(f"Bybit perp не найден для {tv_symbol}. Проверь символ.")
    return candidates[0]

def tv_to_ccxt_symbol_binance_spot(tv_symbol: str, markets: Dict) -> str:
    """
    TradingView Binance spot: BTCUSDT
    ccxt expects BTC/USDT
    """
    s = _norm_symbol_input(tv_symbol)
    s = s.replace(".P", "")  # убираем .P для Bybit символов
    
    # Специальная обработка для 1000PEPE и подобных
    if s.startswith("1000"):
        s = s[4:]  # убираем префикс 1000
    
    # BTCUSDT -> BTC/USDT
    if "/" in s:
        sym = s
    else:
        if not s.endswith("USDT"):
            raise ValueError(f"Поддерживается только USDT формат типа BTCUSDT: {tv_symbol}")
        base = s[:-4]
        sym = f"{base}/USDT"
    
    # Проверяем наличие символа в markets
    if sym not in markets:
        # Пробуем альтернативные варианты
        alternatives = [
            sym,
            f"{base}USDT",  # без слэша
            f"{base.upper()}/USDT",
            f"{base.lower()}/USDT"
        ]
        
        for alt in alternatives:
            if alt in markets:
                return alt
                
        # Если ничего не найдено, возвращаем оригинальный символ
        # Это позволит избежать краша и показать ошибку в логах
        return sym
    return sym

def tv_to_ccxt_symbol_binance_demo(tv_symbol: str, markets: Dict) -> str:
    """
    Binance Demo Futures: BTCUSDT -> BTC/USDT:USDT
    """
    s = _norm_symbol_input(tv_symbol)
    s = s.replace(".P", "")  # убираем .P для Bybit символов
    
    # Специальная обработка для 1000PEPE и подобных
    if s.startswith("1000"):
        s = s[4:]  # убираем префикс 1000
    
    # BTCUSDT -> BTC/USDT:USDT (futures format)
    if ":" in s:
        sym = s
    else:
        if not s.endswith("USDT"):
            raise ValueError(f"Поддерживается только USDT формат типа BTCUSDT: {tv_symbol}")
        base = s[:-4]
        sym = f"{base}/USDT:USDT"
    
    # Проверяем наличие символа в markets
    if sym not in markets:
        # Пробуем альтернативные варианты
        alternatives = [
            sym,
            f"{base}/USDT",  # spot format
            f"{base.upper()}/USDT:USDT",
            f"{base.lower()}/USDT:USDT"
        ]
        
        for alt in alternatives:
            if alt in markets:
                return alt
                
        return sym
    return sym

def make_exchange(source: str, api_key: str = None, api_secret: str = None, demo_mode: bool = False):
    """
    source: 'BYBIT_PERP', 'BYBIT_DEMO', 'BINANCE_SPOT', or 'BINANCE_DEMO'
    api_key, api_secret: API credentials for trading
    demo_mode: use demo/sandbox endpoints
    """
    if source in ("BYBIT_PERP", "BYBIT_DEMO"):
        use_testnet = bool(demo_mode) and source == "BYBIT_PERP"
        use_demo_trading = source == "BYBIT_DEMO"
        ex = ccxt.bybit({
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "accountType": "unified",
                "enableUnifiedAccount": True,
                "enableUnifiedMargin": False,
                "unifiedMarginStatus": 6,
            },
        })
        if api_key and api_secret:
            ex.apiKey = api_key
            ex.secret = api_secret
        if use_testnet:
            ex.set_sandbox_mode(True)
        if use_demo_trading:
            # Bybit demo trading keys from bybit.com work via api-demo domain.
            ex.enable_demo_trading(True)
        return ex

    if source == "BINANCE_SPOT":
        ex = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if api_key and api_secret:
            ex.apiKey = api_key
            ex.secret = api_secret
        if demo_mode:
            ex.set_sandbox_mode(True)
        return ex
    
    if source == "BINANCE_DEMO":
        # Binance Futures Demo для демо-торговли
        ex = ccxt.binance({
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",  # futures для demo
            },
        })
        if api_key and api_secret:
            ex.apiKey = api_key
            ex.secret = api_secret
        # Устанавливаем demo/sandbox режим
        ex.set_sandbox_mode(True)
        return ex

    raise ValueError(f"Unknown source: {source}")

def map_symbols(source: str, tv_symbols: List[str], markets: Dict) -> List[Tuple[str, str]]:
    """
    returns list of (tv_symbol, ccxt_symbol)
    """
    out = []
    for s in tv_symbols:
        if not s.strip():
            continue
        if source in ("BYBIT_PERP", "BYBIT_DEMO"):
            ccxt_sym = tv_to_ccxt_symbol_bybit_perp(s, markets)
        elif source == "BINANCE_DEMO":
            ccxt_sym = tv_to_ccxt_symbol_binance_demo(s, markets)
        else:
            ccxt_sym = tv_to_ccxt_symbol_binance_spot(s, markets)
        out.append((s.strip(), ccxt_sym))
    return out

def fetch_closed_ohlcv(ex, ccxt_symbol: str, timeframe: str, limit: int = 500) -> List[Candle]:
    """
    Fetch candles and drop the last one (often forming).
    """
    raw = ex.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit)
    if len(raw) < 5:
        return []
    raw = raw[:-1]
    return [Candle(ts=x[0], o=float(x[1]), h=float(x[2]), l=float(x[3]), c=float(x[4]), v=float(x[5])) for x in raw]
