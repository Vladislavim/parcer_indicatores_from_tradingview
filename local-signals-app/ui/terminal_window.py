"""
Bybit Trading Terminal - Полноценный торговый терминал
Автоторговля по стратегии с индикаторами
"""
from __future__ import annotations

import math
import json
import csv
import os
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict
from decimal import Decimal

from PySide6.QtCore import Qt, QTimer, QSettings, QThread, Signal, QObject
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPixmap, QPen
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QDialog,
    QLabel, QPushButton, QFrame, QLineEdit, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGraphicsDropShadowEffect, QMessageBox, 
    QScrollArea, QApplication, QComboBox, QGridLayout, QGroupBox, QFileDialog
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

try:
    import ccxt
except ImportError:
    ccxt = None

from ui.styles import COLORS, get_current_theme

TOP_SYMBOLS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT",
    "ADA/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT", "DOT/USDT:USDT", "LTC/USDT:USDT",
    "BCH/USDT:USDT", "TRX/USDT:USDT", "UNI/USDT:USDT", "APT/USDT:USDT", "ARB/USDT:USDT",
    "OP/USDT:USDT", "SUI/USDT:USDT", "TON/USDT:USDT", "NEAR/USDT:USDT", "PEPE/USDT:USDT",
]
TOP_COINS = [s.split("/")[0] for s in TOP_SYMBOLS]


# Bybit logo URL
BYBIT_LOGO_URL = "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png"


def _bybit_market_id(exchange, symbol: str) -> str:
    try:
        m = exchange.market(symbol)
        if isinstance(m, dict) and m.get("id"):
            return str(m.get("id"))
    except Exception:
        pass
    s = str(symbol or "").upper().strip()
    if "/" in s:
        base, rest = s.split("/", 1)
        quote = rest.split(":", 1)[0]
        return f"{base}{quote}"
    return s.split(":", 1)[0]


def _call_set_trading_stop(exchange, symbol: str, stop_loss: float | None = None, take_profit: float | None = None):
    """
    Совместимый вызов установки SL/TP для разных версий ccxt.bybit.
    """
    sl = None
    tp = None
    if stop_loss is not None:
        sl = round(float(stop_loss), 2)
    if take_profit is not None:
        tp = round(float(take_profit), 2)
    if sl is None and tp is None:
        raise ValueError("set_trading_stop called without SL/TP values")

    high_level_params = {"positionIdx": 0}
    if sl is not None:
        high_level_params["stopLoss"] = sl
    if tp is not None:
        high_level_params["takeProfit"] = tp

    errors = []
    for method_name in ("set_trading_stop", "setTradingStop"):
        method = getattr(exchange, method_name, None)
        if not callable(method):
            continue
        try:
            method(symbol, high_level_params)
            return
        except Exception as e:
            errors.append(f"{method_name}: {e}")

    market_id = _bybit_market_id(exchange, symbol)
    payload_v5 = {
        "category": "linear",
        "symbol": market_id,
        "tpslMode": "Full",
        "positionIdx": 0,
    }
    if sl is not None:
        payload_v5["stopLoss"] = str(sl)
    if tp is not None:
        payload_v5["takeProfit"] = str(tp)

    payload_v3 = {
        "symbol": market_id,
        "positionIdx": 0,
    }
    if sl is not None:
        payload_v3["stopLoss"] = str(sl)
    if tp is not None:
        payload_v3["takeProfit"] = str(tp)

    method_payload_pairs = [
        ("private_post_v5_position_trading_stop", payload_v5),
        ("privatePostV5PositionTradingStop", payload_v5),
        ("private_post_unified_v3_private_position_trading_stop", payload_v3),
        ("privatePostUnifiedV3PrivatePositionTradingStop", payload_v3),
        ("private_post_contract_v3_private_position_trading_stop", payload_v3),
        ("privatePostContractV3PrivatePositionTradingStop", payload_v3),
    ]
    for method_name, payload in method_payload_pairs:
        method = getattr(exchange, method_name, None)
        if not callable(method):
            continue
        try:
            method(payload)
            return
        except Exception as e:
            errors.append(f"{method_name}: {e}")

    details = "; ".join(errors[-3:]) if errors else "no suitable trading-stop method found"
    raise RuntimeError(details)


class AutoTradeWorker(QThread):
    """
    Воркер для автоторговли в отдельном потоке.
    
    Комбинированная защита позиций:
    1. SL/TP ордера на бирже — жёсткий стоп и тейк (выставляются при открытии)
    2. Автозакрытие по сигналу — если индикаторы развернулись (конфлюенс 2/3)
    3. Trailing Stop — подтягивает стоп в безубыток при профите >= 2%
    """
    log_signal = Signal(str)
    profit_signal = Signal(float)
    refresh_signal = Signal()
    open_position_signal = Signal(str, str, float, float, float, int)  # symbol, side, size, sl, tp, leverage
    close_position_signal = Signal(str, float, str)  # symbol, size, side
    journal_signal = Signal(dict)  # Сигнал для записи в журнал
    
    def __init__(self, exchange, settings: dict, get_signal_func, get_htf_func):
        super().__init__()
        self.exchange = exchange
        self.settings = settings  # leverage, risk_pct, tf, selected_coins
        self.get_signal = get_signal_func
        self.get_htf = get_htf_func
        self._stop = False
        self._trailing_activated = {}  # Отслеживаем для каких позиций уже активирован trailing
        self._last_entry_ts: Dict[str, float] = {}
        self._opposite_hits: Dict[str, int] = {}
        self._session_start_equity: Optional[float] = None
        self._session_peak_equity: Optional[float] = None
        self._risk_pause_until_ts: float = 0.0
        self._risk_pause_announced = False

    @staticmethod
    def _clamp(v: float, low: float, high: float) -> float:
        return max(low, min(high, v))

    def _estimate_sl_tp(self, symbol: str, timeframe: str, price: float) -> tuple[float, float, str]:
        """
        Профессиональный расчёт SL/TP:
        ATR-волатильность + сила тренда (EMA20/EMA50) + адаптивный RR.
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=90)
            if not ohlcv or len(ohlcv) < 30:
                return 1.0, 2.3, "fallback"

            highs = [float(x[2]) for x in ohlcv]
            lows = [float(x[3]) for x in ohlcv]
            closes = [float(x[4]) for x in ohlcv]

            trs = []
            for i in range(1, len(closes)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
                trs.append(tr)
            if not trs:
                return 1.0, 2.3, "fallback"

            atr = sum(trs[-14:]) / min(14, len(trs))
            atr_pct = (atr / price) * 100.0 if price > 0 else 0.0

            # EMA20/EMA50 gap как proxy силы направленного движения.
            def ema(vals: list[float], period: int) -> list[float]:
                if len(vals) < period:
                    return []
                mult = 2 / (period + 1)
                out = [sum(vals[:period]) / period]
                for v in vals[period:]:
                    out.append((v - out[-1]) * mult + out[-1])
                return out

            ema20 = ema(closes, 20)
            ema50 = ema(closes, 50)
            trend_gap_pct = 0.0
            if ema20 and ema50 and price > 0:
                trend_gap_pct = abs(ema20[-1] - ema50[-1]) / price * 100.0

            if atr_pct < 0.65:
                vol_state = "low-vol"
                sl_mult = 1.45
            elif atr_pct > 1.70:
                vol_state = "high-vol"
                sl_mult = 1.05
            else:
                vol_state = "normal-vol"
                sl_mult = 1.25

            if trend_gap_pct >= 0.90:
                rr = 3.0
            elif trend_gap_pct >= 0.45:
                rr = 2.4
            else:
                rr = 1.9

            if vol_state == "high-vol":
                rr -= 0.25
            elif vol_state == "low-vol":
                rr += 0.20
            rr = self._clamp(rr, 1.6, 3.2)

            sl_pct = self._clamp(atr_pct * sl_mult, 0.45, 2.8)
            tp_pct = self._clamp(sl_pct * rr, 1.0, 7.5)
            model = f"{vol_state}, gap={trend_gap_pct:.2f}%, RR=1:{rr:.2f}"
            return sl_pct, tp_pct, model
        except Exception:
            return 1.0, 2.3, "fallback"
        
    def stop(self):
        self._stop = True
        
    def _update_trailing_stop(self, symbol: str, new_sl: float, side: str, coin: str):
        """Обновляет trailing stop для позиции"""
        # Проверяем, не активировали ли уже trailing для этой позиции
        if symbol in self._trailing_activated:
            return
            
        try:
            _call_set_trading_stop(self.exchange, symbol, stop_loss=float(new_sl), take_profit=None)
            self._trailing_activated[symbol] = True
            self.log_signal.emit(f"🔒 {coin} Trailing: SL → ${new_sl:,.2f} (безубыток)")
        except Exception as e:
            # Если API не поддерживает, просто логируем
            if "not supported" not in str(e).lower():
                self.log_signal.emit(f"⚠️ Trailing {coin}: {e}")
        
    def run(self):
        """Выполняет проверку сигналов в отдельном потоке"""
        try:
            self._check_signals()
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка автоторговли: {e}")
            
    def _check_signals(self):
        if not self.exchange:
            return
            
        # Тихая проверка — логируем только важное
        
        leverage = int(self._clamp(float(self.settings['leverage']), 5, 10))
        risk_pct = float(self._clamp(float(self.settings['risk_pct']), 0.5, 5.0))
        tf = self.settings['tf']
        selected_coins = self.settings['selected_coins']
        max_positions = int(self._clamp(float(self.settings.get('max_positions', 0)), 0, 200))
        min_confluence = int(self._clamp(float(self.settings.get('min_confluence', 3)), 2, 3))
        entry_cooldown_sec = int(self.settings.get('entry_cooldown_sec', 15 * 60))
        max_spread_pct = float(self._clamp(float(self.settings.get('max_spread_pct', 0.12)), 0.02, 1.0))
        min_quote_volume = float(max(0.0, float(self.settings.get('min_quote_volume', 3_000_000))))
        max_drawdown_pct = float(self._clamp(float(self.settings.get('max_drawdown_pct', 6.0)), 1.0, 50.0))
        hard_stop_pct = float(self._clamp(float(self.settings.get('hard_stop_pct', 10.0)), 1.0, 80.0))
        risk_pause_minutes = int(self._clamp(float(self.settings.get('risk_pause_minutes', 60)), 5, 480))
        
        # Получаем баланс
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            available = float(usdt.get('free') or 0)
        except Exception as e:
            return  # Тихо пропускаем
        
        if available < 10:
            return  # Тихо пропускаем
        
        if not selected_coins:
            return  # Тихо пропускаем
        
        # === TRAILING STOP ===
        # Подтягиваем стоп-лосс при достижении профита
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]
        except Exception as e:
            open_positions = []
        open_position_coins = set()
        for p in open_positions:
            symbol_raw = str(p.get('symbol') or '')
            if not symbol_raw:
                continue
            if '/' in symbol_raw:
                coin_key = symbol_raw.split('/')[0]
            else:
                coin_key = symbol_raw.split(':')[0].replace("USDT", "")
            if coin_key:
                open_position_coins.add(coin_key)

        # === ПРОФИ-РИСК ДВИЖОК ===
        # Ведём контроль просадки по equity и автоматически снижаем/останавливаем риск.
        unrealized = sum(float(p.get('unrealizedPnl') or 0) for p in open_positions)
        equity_now = max(0.0, available + unrealized)
        if self._session_start_equity is None:
            self._session_start_equity = equity_now
            self._session_peak_equity = equity_now
        self._session_peak_equity = max(self._session_peak_equity or equity_now, equity_now)

        peak = max(1e-9, float(self._session_peak_equity or equity_now))
        start = max(1e-9, float(self._session_start_equity or equity_now))
        dd_from_peak_pct = ((peak - equity_now) / peak) * 100.0
        dd_from_start_pct = ((start - equity_now) / start) * 100.0

        now_ts = time.time()
        if now_ts < self._risk_pause_until_ts:
            if not self._risk_pause_announced:
                mins_left = int(max(1, (self._risk_pause_until_ts - now_ts) // 60))
                self.log_signal.emit(
                    f"⏸️ Risk pause активен: {mins_left} мин (просадка {dd_from_peak_pct:.2f}%)"
                )
                self._risk_pause_announced = True
            # Во время паузы новые позиции не открываем, но обновления/закрытия продолжаются.
            return
        self._risk_pause_announced = False

        if dd_from_peak_pct >= max_drawdown_pct or dd_from_start_pct >= hard_stop_pct:
            self._risk_pause_until_ts = now_ts + risk_pause_minutes * 60
            self.log_signal.emit(
                f"🛑 Risk breaker: просадка peak={dd_from_peak_pct:.2f}% / start={dd_from_start_pct:.2f}%."
                f" Пауза {risk_pause_minutes} мин."
            )
            return

        # Адаптивное снижение риска при просадке
        drawdown_ratio = min(1.0, dd_from_peak_pct / max(max_drawdown_pct, 1e-9))
        risk_multiplier = max(0.35, 1.0 - drawdown_ratio * 0.65)
        risk_pct *= risk_multiplier
        
        for pos in open_positions:
            if self._stop:
                return
            
            pos_symbol = pos.get('symbol', '')
            pos_side = (pos.get('side') or '').lower()
            pos_pnl_pct = float(pos.get('percentage') or 0)
            entry_price = float(pos.get('entryPrice') or 0)
            
            coin_from_pos = pos_symbol.split('/')[0] if '/' in pos_symbol else pos_symbol.replace('USDT', '')
            
            if coin_from_pos not in selected_coins:
                continue
            
            # Trailing Stop: если профит >= 2%, подтягиваем SL в безубыток + 0.5%
            if pos_pnl_pct >= 2.0 and entry_price > 0:
                try:
                    ticker = self.exchange.fetch_ticker(pos_symbol)
                    current_price = ticker['last']
                    
                    if pos_side == "long":
                        # Новый SL = entry + 0.5%
                        new_sl = entry_price * 1.005
                        if current_price > new_sl:
                            self._update_trailing_stop(pos_symbol, new_sl, pos_side, coin_from_pos)
                    else:
                        # Для шорта: новый SL = entry - 0.5%
                        new_sl = entry_price * 0.995
                        if current_price < new_sl:
                            self._update_trailing_stop(pos_symbol, new_sl, pos_side, coin_from_pos)
                except:
                    pass
        
        # === АВТОЗАКРЫТИЕ ПО СИГНАЛУ ===
        auto_owned_symbols = set(self.settings.get("auto_owned_symbols", []))
        close_on_strong_opposite = bool(self.settings.get("close_on_strong_opposite", True))
        opposite_min_confluence = int(self._clamp(float(self.settings.get("opposite_min_confluence", 3)), 2, 3))
        opposite_confirmations = int(self._clamp(float(self.settings.get("opposite_confirmations", 2)), 1, 3))
        
        for pos in open_positions:
            if self._stop:
                return
                
            pos_symbol = pos.get('symbol', '')
            pos_side = (pos.get('side') or '').lower()
            pos_size = float(pos.get('contracts') or 0)
            pos_pnl = float(pos.get('unrealizedPnl') or 0)
            
            coin_from_pos = pos_symbol.split('/')[0] if '/' in pos_symbol else pos_symbol.replace('USDT', '')
            
            if coin_from_pos not in selected_coins:
                continue
            if pos_symbol not in auto_owned_symbols:
                continue
            if not close_on_strong_opposite:
                continue
            
            try:
                signal, strength, details = self.get_signal(coin_from_pos)
            except:
                continue
            try:
                htf_trend = self.get_htf(coin_from_pos, tf)
            except:
                htf_trend = "neutral"
            
            should_close = False
            opposite = (
                (pos_side == "long" and signal == "sell" and htf_trend == "bear")
                or (pos_side == "short" and signal == "buy" and htf_trend == "bull")
            )
            key = f"{pos_symbol}:{pos_side}"
            if opposite and strength >= opposite_min_confluence:
                self._opposite_hits[key] = self._opposite_hits.get(key, 0) + 1
            else:
                self._opposite_hits[key] = 0
            
            if self._opposite_hits.get(key, 0) >= opposite_confirmations:
                should_close = True
                self._opposite_hits[key] = 0
                self.log_signal.emit(
                    f"🔄 Закрываю {coin_from_pos} {pos_side.upper()} — сильный противоположный сигнал "
                    f"({strength}/3, {opposite_confirmations} подтверждения)"
                )
            
            if should_close:
                try:
                    entry_price = float(pos.get('entryPrice') or 0)
                    leverage = int(pos.get('leverage') or 1)
                    
                    if pos_side == "long":
                        self.exchange.create_market_sell_order(pos_symbol, pos_size, {"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(pos_symbol, pos_size, {"reduceOnly": True})
                    
                    # Получаем цену выхода
                    ticker = self.exchange.fetch_ticker(pos_symbol)
                    exit_price = ticker['last']
                    
                    pnl_str = f"{'+'if pos_pnl>=0 else ''}${pos_pnl:.2f}"
                    self.log_signal.emit(f"✅ Закрыто {coin_from_pos} | PnL: {pnl_str}")
                    
                    # Отправляем в журнал
                    self.journal_signal.emit({
                        'symbol': pos_symbol,
                        'side': pos_side,
                        'strategy': 'AutoTrade (Индикаторы)',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'size': pos_size,
                        'leverage': leverage,
                        'pnl_usd': pos_pnl,
                        'close_reason': 'Signal'
                    })
                    
                    if pos_pnl >= 5:
                        self.profit_signal.emit(pos_pnl)
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка закрытия: {e}")
        
        # === ОТКРЫТИЕ НОВЫХ ПОЗИЦИЙ ===
        # Лимит применяется только если задан явно (>0). 0 = без лимита.
        if max_positions > 0 and len(open_positions) >= max_positions:
            self.refresh_signal.emit()
            return
            
        for coin in selected_coins:
            if self._stop:
                return
                
            symbol = f"{coin}/USDT:USDT"

            if coin in open_position_coins:
                continue
            
            now = time.time()
            if (now - self._last_entry_ts.get(coin, 0)) < entry_cooldown_sec:
                continue
            
            try:
                signal, strength, details = self.get_signal(coin)
            except Exception as e:
                continue  # Тихо пропускаем ошибки
            
            # Пропускаем если нет сигнала или слабый конфлюенс
            if signal not in ["buy", "sell"] or strength < min_confluence:
                continue
                
            try:
                htf_trend = self.get_htf(coin, tf)
            except:
                htf_trend = "neutral"
            
            # СТРОГИЙ HTF фильтр: торгуем ТОЛЬКО по тренду
            if signal == "buy" and htf_trend != "bull":
                continue  # Тихо пропускаем
            if signal == "sell" and htf_trend != "bear":
                continue  # Тихо пропускаем
            
            htf_emoji = "🟢" if htf_trend == "bull" else "🔴" if htf_trend == "bear" else "⚪"
            
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                price = ticker['last']
                bid = float(ticker.get('bid') or 0)
                ask = float(ticker.get('ask') or 0)

                # Liquidity/spread safety filter
                if bid > 0 and ask > 0 and price > 0:
                    spread_pct = ((ask - bid) / price) * 100.0
                    if spread_pct > max_spread_pct:
                        self.log_signal.emit(f"⚠️ {coin} пропуск: высокий спред {spread_pct:.2f}%")
                        continue

                quote_volume = float(ticker.get('quoteVolume') or 0)
                if quote_volume > 0 and quote_volume < min_quote_volume:
                    self.log_signal.emit(
                        f"⚠️ {coin} пропуск: низкая ликвидность (vol={quote_volume:,.0f})"
                    )
                    continue
                
                position_usdt = available * (risk_pct / 100)
                max_position_cap = available * 0.30
                position_usdt = min(position_usdt, max_position_cap)
                size = (position_usdt * leverage) / price
                
                if coin == "BTC":
                    size = round(size, 3)
                elif coin in ["ETH", "SOL"]:
                    size = round(size, 2)
                else:
                    size = round(size, 1)
                    
                notional_usdt = size * price
                if size < 0.001 or notional_usdt < 5:
                    continue
                
                # Volatility-adjusted SL/TP with sane bounds
                sl_pct, tp_pct, sltp_model = self._estimate_sl_tp(symbol, tf, price)
                
                direction = "ЛОНГ 📈" if signal == "buy" else "ШОРТ 📉"
                self.log_signal.emit(f"🔥 КОНФЛЮЕНС {direction} {coin} ({strength}/3) {htf_emoji}HTF")
                self.log_signal.emit(f"   {details}")
                self.log_signal.emit(
                    f"   Размер: {size} | Плечо: {leverage}x | SL {sl_pct:.2f}% / TP {tp_pct:.2f}% | {sltp_model}"
                )
                
                # Отправляем сигнал для открытия в главном потоке
                self.open_position_signal.emit(symbol, signal, size, sl_pct, tp_pct, leverage)
                self._last_entry_ts[coin] = now
                open_position_coins.add(coin)
                
            except Exception as e:
                self.log_signal.emit(f"❌ Ошибка открытия {coin}: {e}")
        
        self.refresh_signal.emit()


class ConnectWorker(QThread):
    """Воркер для подключения к API в отдельном потоке"""
    success = Signal(object)  # exchange object
    error = Signal(str)
    log = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str, is_mainnet: bool = False):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_mainnet = is_mainnet
        
    def run(self):
        try:
            # Определяем тип биржи из конфига
            from core.config import config
            exchange_type = config.data.get("exchange", "BYBIT_DEMO")
            demo_mode = config.data.get("demo_mode", False)
            
            if exchange_type == "BYBIT_PERP" or exchange_type == "BYBIT_DEMO":
                use_testnet = bool(demo_mode) and exchange_type == "BYBIT_PERP"
                use_demo_trading = exchange_type == "BYBIT_DEMO"
                if use_demo_trading:
                    network_name = "Bybit Demo"
                elif use_testnet:
                    network_name = "Bybit Testnet"
                else:
                    network_name = "Bybit Mainnet"
                self.log.emit(f"🔄 Подключение к {network_name}...")
                
                exchange = ccxt.bybit({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'swap',
                        'accountType': 'unified',
                        # Avoid permission check endpoint (/user/*/query-api) for demo keys.
                        'enableUnifiedAccount': True,
                        'enableUnifiedMargin': False,
                        'unifiedMarginStatus': 6,
                    },
                })
                
                if use_testnet:
                    exchange.set_sandbox_mode(True)
                if use_demo_trading:
                    exchange.enable_demo_trading(True)
                # Force unified state to avoid /user/v3/private/query-api permission checks.
                exchange.options['enableUnifiedAccount'] = True
                exchange.options['enableUnifiedMargin'] = False
                exchange.options['unifiedMarginStatus'] = 6
                exchange.is_unified_enabled = (lambda params={}: [False, True])
                
            elif exchange_type == "BINANCE_DEMO":
                network_name = "Bybit Demo"
                self.log.emit(f"🔄 Подключение к {network_name}...")
                
                exchange = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'},
                    'urls': {
                        'api': {
                            'public': 'https://demo-fapi.binance.com/fapi/v1',
                            'private': 'https://demo-fapi.binance.com/fapi/v1',
                        }
                    },
                })
            else:
                # По умолчанию Bybit
                network_name = "Bybit"
                self.log.emit(f"🔄 Подключение к {network_name}...")
                
                exchange = ccxt.bybit({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'swap',
                        'accountType': 'unified',
                        'enableUnifiedAccount': True,
                        'enableUnifiedMargin': False,
                        'unifiedMarginStatus': 6,
                    },
                })
                exchange.options['enableUnifiedAccount'] = True
                exchange.options['enableUnifiedMargin'] = False
                exchange.options['unifiedMarginStatus'] = 6
                exchange.is_unified_enabled = (lambda params={}: [False, True])
            
            # Проверяем подключение
            exchange.fetch_balance()
            
            self.success.emit(exchange)
            
        except Exception as e:
            self.error.emit(str(e))


class RefreshWorker(QThread):
    """Воркер для обновления данных в отдельном потоке"""
    data_ready = Signal(float, float, float, list)  # available, total, pnl, positions
    price_ready = Signal(float)  # current price
    error = Signal(str)
    
    def __init__(self, exchange, symbol: str = None):
        super().__init__()
        self.exchange = exchange
        self.symbol = symbol
        
    def run(self):
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            
            available = float(usdt.get('free') or 0)
            total = float(usdt.get('total') or 0)
            
            positions = self.exchange.fetch_positions()
            open_pos = [p for p in positions if float(p.get('contracts') or 0) > 0]
            
            total_pnl = sum(float(p.get('unrealizedPnl') or 0) for p in open_pos)
            
            self.data_ready.emit(available, total, total_pnl, open_pos)
            
            # Получаем цену если указан символ
            if self.symbol:
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.price_ready.emit(ticker['last'])
                except:
                    pass
                    
        except Exception as e:
            self.error.emit(str(e))


class AsyncCloseWorker(QThread):
    """Асинхронное закрытие позиции, чтобы не блокировать UI."""
    success = Signal(dict)  # payload
    error = Signal(str, str, str)  # symbol, close_reason, error

    def __init__(self, exchange, symbol: str, side: str, size: float, close_reason: str):
        super().__init__()
        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.size = size
        self.close_reason = close_reason

    def run(self):
        try:
            if self.side == "long":
                self.exchange.create_market_sell_order(self.symbol, self.size, {"reduceOnly": True})
            else:
                self.exchange.create_market_buy_order(self.symbol, self.size, {"reduceOnly": True})

            ticker = self.exchange.fetch_ticker(self.symbol)
            payload = {
                "symbol": self.symbol,
                "exit_price": float(ticker.get('last') or 0),
                "close_reason": self.close_reason,
            }
            self.success.emit(payload)
        except Exception as e:
            self.error.emit(self.symbol, self.close_reason, str(e))


class AsyncStopSyncWorker(QThread):
    """Асинхронная синхронизация SL/TP на бирже."""
    success = Signal(str, float, float)  # symbol, sl, tp
    error = Signal(str, str)  # symbol, error

    def __init__(self, exchange, symbol: str, sl_price: float, tp_price: float):
        super().__init__()
        self.exchange = exchange
        self.symbol = symbol
        self.sl_price = float(sl_price)
        self.tp_price = float(tp_price)

    def run(self):
        try:
            _call_set_trading_stop(
                self.exchange,
                self.symbol,
                stop_loss=float(self.sl_price),
                take_profit=float(self.tp_price),
            )
            self.success.emit(self.symbol, self.sl_price, self.tp_price)
        except Exception as e:
            self.error.emit(self.symbol, str(e))


class LogoLoader:
    """Загрузчик логотипа"""
    _pixmap: Optional[QPixmap] = None
    _manager: Optional[QNetworkAccessManager] = None
    _callbacks: List = []
    
    @classmethod
    def load(cls, callback):
        if cls._pixmap:
            callback(cls._pixmap)
            return
            
        cls._callbacks.append(callback)
        
        if cls._manager is None:
            from PySide6.QtCore import QUrl
            cls._manager = QNetworkAccessManager()
            request = QNetworkRequest(QUrl(BYBIT_LOGO_URL))
            reply = cls._manager.get(request)
            reply.finished.connect(lambda: cls._on_loaded(reply))
    
    @classmethod        
    def _on_loaded(cls, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data.data())
            if not pixmap.isNull():
                cls._pixmap = pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        for cb in cls._callbacks:
            cb(cls._pixmap)
        cls._callbacks.clear()
        reply.deleteLater()


class InstructionDialog(QDialog):
    """Диалог с инструкцией"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка Bybit API")
        self.setFixedSize(450, 420)
        self.setStyleSheet(f"background: {COLORS['bg_dark']};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("🔑 Получение API ключей Bybit Demo")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(title)
        
        steps = QLabel(
            "1. Перейди на <b>bybit.com/app/user/api-management</b><br><br>"
            "2. Переключи аккаунт в режим <b>Demo Trading</b><br><br>"
            "3. Создай API ключ в разделе <b>API Management</b><br><br>"
            "4. Тип: <b>System-generated API Keys</b><br><br>"
            "5. Разрешения: <b>Read-Write</b> + доступ к ордерам<br><br>"
            "6. Ограничение IP: отключено (или добавь свой IP)<br><br>"
            "7. Вставь <b>API Key</b> и <b>Secret</b> в терминал"
        )
        steps.setStyleSheet(f"""
            font-size: 13px; color: {COLORS['text_muted']}; 
            background: {COLORS['bg_card']}; 
            padding: 16px; border-radius: 12px;
        """)
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.RichText)
        layout.addWidget(steps)
        
        link_btn = QPushButton("🌐 Открыть API Management")
        link_btn.setCursor(Qt.PointingHandCursor)
        link_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {COLORS['accent']};
                border-radius: 10px;
                color: {COLORS['accent']};
                font-size: 13px;
                padding: 10px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}
        """)
        link_btn.clicked.connect(self._open_link)
        layout.addWidget(link_btn)
        
        layout.addStretch()
        
        self.dont_show = QCheckBox("Больше не показывать")
        self.dont_show.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.dont_show)
        
        ok_btn = QPushButton("Понятно")
        ok_btn.setFixedHeight(44)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        
    def _open_link(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://www.bybit.com/app/user/api-management"))


class TerminalBackground(QWidget):
    """Анимированный фон"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time = 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)
        
    def _animate(self):
        # Пауза анимации при сворачивании/неактивном окне снижает лаги при Alt+Tab.
        win = self.window()
        if win and (win.isMinimized() or not win.isVisible() or not win.isActiveWindow()):
            return
        self.time += 0.012
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        w, h = self.width(), self.height()

        hue_a = int((math.sin(self.time * 0.33) * 0.5 + 0.5) * 359)
        hue_b = (hue_a + 110) % 360
        hue_c = (hue_a + 220) % 360
        
        # Base dark layer
        bg = QLinearGradient(0, 0, w, h)
        c0 = QColor.fromHsv(hue_a, 65, 20, 255)
        c1 = QColor.fromHsv(hue_b, 70, 26, 255)
        c2 = QColor.fromHsv(hue_c, 75, 18, 255)
        bg.setColorAt(0.0, c0)
        bg.setColorAt(0.45, c1)
        bg.setColorAt(1.0, c2)
        painter.fillRect(self.rect(), bg)
        
        # Animated color wash (shader-like sweep)
        sweep_shift = int((math.sin(self.time * 0.9) * 0.2 + 0.2) * w)
        sweep = QLinearGradient(-w * 0.2 + sweep_shift, 0, w + sweep_shift, h)
        sweep.setColorAt(0.0, QColor(0, 0, 0, 0))
        sweep.setColorAt(0.35, QColor.fromHsv((hue_a + 40) % 360, 220, 255, 28))
        sweep.setColorAt(0.62, QColor.fromHsv((hue_b + 20) % 360, 220, 255, 22))
        sweep.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), sweep)

        # Light blobs
        orbs = [
            (0.10, 0.16, 320, (0, 210, 255, 34), 1.1),
            (0.86, 0.20, 280, (255, 104, 162, 30), 1.5),
            (0.22, 0.82, 300, (129, 85, 255, 26), 1.9),
            (0.90, 0.86, 360, (255, 178, 68, 24), 1.3),
        ]
        
        for ox, oy, radius, color, phase in orbs:
            drift_x = int(math.sin(self.time * 0.7 + phase) * 20)
            drift_y = int(math.cos(self.time * 0.9 + phase) * 14)
            cx, cy = int(ox * w) + drift_x, int(oy * h) + drift_y
            pulse = 1 + 0.12 * math.sin(self.time * 1.7 + phase * 3.0)
            r = int(radius * pulse)
            
            gradient = QRadialGradient(cx, cy, r)
            gradient.setColorAt(0, QColor(*color))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # 3D perspective grid
        horizon = int(h * 0.56)
        center_x = int(w * 0.52)

        # Horizontal perspective lines
        for i in range(1, 13):
            t = i / 12.0
            y = int(horizon + (t * t) * (h - horizon))
            alpha = int(70 * (1 - t) + 8)
            pen = QPen(QColor(83, 150, 255, alpha))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(0, y, w, y)

        # Vertical convergence lines
        for j in range(-12, 13):
            x_bottom = int(center_x + j * (w * 0.065))
            x_top = int(center_x + j * 3)
            alpha = max(12, 36 - abs(j))
            pen = QPen(QColor(0, 212, 255, alpha))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(x_top, horizon, x_bottom, h)

        # Subtle vignette for depth
        vignette = QRadialGradient(w * 0.5, h * 0.45, max(w, h) * 0.75)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        painter.setPen(Qt.NoPen)
        painter.setBrush(vignette)
        painter.drawRect(self.rect())


class BalanceWidget(QFrame):
    """Виджет баланса"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(24)
        
        # Available
        avail_layout = QVBoxLayout()
        avail_layout.setSpacing(2)
        avail_title = QLabel("Доступно")
        avail_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        avail_layout.addWidget(avail_title)
        self.avail_lbl = QLabel("$0.00")
        self.avail_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        avail_layout.addWidget(self.avail_lbl)
        layout.addLayout(avail_layout)
        
        # Equity
        equity_layout = QVBoxLayout()
        equity_layout.setSpacing(2)
        equity_title = QLabel("Эквити")
        equity_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        equity_layout.addWidget(equity_title)
        self.equity_lbl = QLabel("$0.00")
        self.equity_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        equity_layout.addWidget(self.equity_lbl)
        layout.addLayout(equity_layout)
        
        # Unrealized PnL
        pnl_layout = QVBoxLayout()
        pnl_layout.setSpacing(2)
        pnl_title = QLabel("Нереализ. PnL")
        pnl_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        pnl_layout.addWidget(pnl_title)
        self.pnl_lbl = QLabel("$0.00")
        self.pnl_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        pnl_layout.addWidget(self.pnl_lbl)
        layout.addLayout(pnl_layout)
        
        layout.addStretch()
        
    def update_balance(self, available: float, equity: float, pnl: float):
        self.avail_lbl.setText(f"${available:,.2f}")
        self.equity_lbl.setText(f"${equity:,.2f}")
        
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        pnl_sign = "+" if pnl >= 0 else ""
        self.pnl_lbl.setText(f"{pnl_sign}${pnl:,.2f}")
        self.pnl_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {pnl_color};")


class PositionRow(QFrame):
    """Строка позиции"""
    
    close_clicked = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = ""
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        self.setFixedHeight(82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)

        self.symbol_lbl = QLabel("—")
        self.symbol_lbl.setFixedWidth(74)
        self.symbol_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text']};")
        top.addWidget(self.symbol_lbl)

        self.side_lbl = QLabel("—")
        self.side_lbl.setFixedWidth(62)
        top.addWidget(self.side_lbl)

        self.pnl_lbl = QLabel("—")
        self.pnl_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        top.addWidget(self.pnl_lbl, 1)

        self.leverage_lbl = QLabel("—")
        self.leverage_lbl.setFixedWidth(44)
        self.leverage_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['warning']};")
        top.addWidget(self.leverage_lbl)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setFixedSize(92, 36)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['danger']};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #ff5555; }}
        """)
        self.close_btn.clicked.connect(lambda: self.close_clicked.emit(self.symbol))
        top.addWidget(self.close_btn)

        layout.addLayout(top)

        self.meta_lbl = QLabel("—")
        self.meta_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        layout.addWidget(self.meta_lbl)

        self.reason_lbl = QLabel("—")
        self.reason_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        self.reason_lbl.setWordWrap(False)
        self.reason_lbl.setToolTip("")
        layout.addWidget(self.reason_lbl)
        
    def update_data(
        self,
        symbol: str,
        side: str,
        size: float,
        entry: float,
        mark: float,
        pnl: float,
        pnl_pct: float,
        leverage: int,
        strategy: str = "",
        open_reason: str = "",
    ):
        self.symbol = symbol
        
        self.symbol_lbl.setText(symbol.replace("/USDT:USDT", ""))
        
        side_color = COLORS['success'] if side == "long" else COLORS['danger']
        self.side_lbl.setText("ЛОНГ" if side == "long" else "ШОРТ")
        self.side_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {side_color};")
        
        # Считаем процент вручную: PnL% = (PnL / маржа) * 100
        # Маржа = (размер * цена входа) / плечо
        if entry > 0 and leverage > 0:
            margin = (size * entry) / leverage
            if margin > 0:
                pnl_pct = (pnl / margin) * 100
        
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        pnl_sign = "+" if pnl >= 0 else ""
        self.pnl_lbl.setText(f"{pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.1f}%)")
        self.pnl_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {pnl_color};")
        
        self.leverage_lbl.setText(f"{leverage}x")
        self.meta_lbl.setText(
            f"Размер: {size:.4f} | Вход: ${entry:,.2f} | Марк: ${mark:,.2f}"
        )
        details = ""
        if strategy:
            details = strategy
        if open_reason:
            details = f"{details}: {open_reason}" if details else open_reason
        if len(details) > 85:
            details_short = details[:82] + "..."
        else:
            details_short = details or "—"
        self.reason_lbl.setText(details_short)
        self.reason_lbl.setToolTip(details if details else "")


class OrderPanel(QFrame):
    """Панель создания ордера как на Bybit"""
    
    order_submitted = Signal(str, str, float, float, float, int)  # symbol, side, size, sl, tp, leverage
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_price = 0.0
        self.setStyleSheet(f"""
            QFrame#OrderPanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("OrderPanel")
        self.setMinimumHeight(480)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("📊 Новый ордер")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: white; background: transparent;")
        layout.addWidget(title)
        
        # Монета
        layout.addWidget(self._create_field_group("Монета", self._create_combo()))
        
        # Плечо
        layout.addWidget(self._create_field_group("Плечо", self._create_leverage_spin()))
        
        # Размер позиции (в USDT)
        layout.addWidget(self._create_field_group("Размер позиции (USDT)", self._create_position_spin()))
        
        # Расчёт (информационный блок)
        self.calc_label = QLabel("Маржа: $0 | Кол-во: 0")
        self.calc_label.setStyleSheet("""
            font-size: 12px; color: #00D9A5; 
            background: #1a2a25; 
            padding: 10px 12px; border-radius: 8px;
            border: 1px solid #00D9A5;
        """)
        self.calc_label.setWordWrap(True)
        layout.addWidget(self.calc_label)
        
        # SL и TP
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addWidget(self._create_field_group("Stop Loss", self._create_sl_spin()))
        row2.addWidget(self._create_field_group("Take Profit", self._create_tp_spin()))
        layout.addLayout(row2)
        
        # Buttons
        layout.addSpacing(8)
        btns = QHBoxLayout()
        btns.setSpacing(12)
        
        self.long_btn = QPushButton("ЛОНГ 📈")
        self.long_btn.setFixedHeight(48)
        self.long_btn.setCursor(Qt.PointingHandCursor)
        self.long_btn.setEnabled(False)
        self.long_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #00c9a7; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.long_btn.clicked.connect(lambda: self._submit("buy"))
        btns.addWidget(self.long_btn)
        
        self.short_btn = QPushButton("ШОРТ 📉")
        self.short_btn.setFixedHeight(48)
        self.short_btn.setCursor(Qt.PointingHandCursor)
        self.short_btn.setEnabled(False)
        self.short_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['danger']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #ff4444; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.short_btn.clicked.connect(lambda: self._submit("sell"))
        btns.addWidget(self.short_btn)
        
        layout.addLayout(btns)
        
    def _create_field_group(self, label_text: str, widget: QWidget) -> QWidget:
        """Создаёт группу: лейбл + поле ввода"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; color: #888; font-weight: 500; background: transparent;")
        vbox.addWidget(label)
        vbox.addWidget(widget)
        
        return container
        
    def _create_combo(self) -> QComboBox:
        self.symbol_combo = QComboBox()
        self.symbol_combo.setFixedHeight(50)
        self.symbol_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox::down-arrow { 
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #aaa;
            }
            QComboBox QAbstractItemView {
                background: #2a2a35;
                color: #ffffff;
                selection-background-color: #6C5CE7;
            }
        """)
        for sym in TOP_SYMBOLS:
            self.symbol_combo.addItem(sym.replace("/USDT:USDT", ""), sym)
        return self.symbol_combo
        
    def _create_size_spin(self) -> QDoubleSpinBox:
        """Старый метод для совместимости"""
        return self._create_position_spin()
        
    def _create_position_spin(self) -> QDoubleSpinBox:
        """Размер позиции в USDT (как на Bybit)"""
        self.position_input = QDoubleSpinBox()
        self.position_input.setFixedHeight(50)
        self.position_input.setRange(10, 1000000)
        self.position_input.setValue(1000)
        self.position_input.setDecimals(0)
        self.position_input.setSingleStep(100)
        self.position_input.setPrefix("$")
        self.position_input.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        self.position_input.valueChanged.connect(self._update_calc)
        return self.position_input
        
    def _create_leverage_spin(self) -> QSpinBox:
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setFixedHeight(50)
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(10)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setStyleSheet("""
            QSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        self.leverage_spin.valueChanged.connect(self._update_calc)
        return self.leverage_spin
        
    def _create_sl_spin(self) -> QDoubleSpinBox:
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setFixedHeight(50)
        self.sl_spin.setRange(0.5, 50)
        self.sl_spin.setValue(2.0)
        self.sl_spin.setDecimals(1)
        self.sl_spin.setSuffix("%")
        self.sl_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.sl_spin
        
    def _create_tp_spin(self) -> QDoubleSpinBox:
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setFixedHeight(50)
        self.tp_spin.setRange(0.5, 100)
        self.tp_spin.setValue(4.0)
        self.tp_spin.setDecimals(1)
        self.tp_spin.setSuffix("%")
        self.tp_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.tp_spin
        
    def _submit(self, side: str):
        position_usdt = self.position_input.value()
        leverage = self.leverage_spin.value()
        # Передаём размер позиции в USDT (не маржу!)
        self.order_submitted.emit(
            self.symbol_combo.currentData(),
            side,
            position_usdt,  # размер позиции в USDT
            self.sl_spin.value(),
            self.tp_spin.value(),
            leverage
        )
        
    def _update_calc(self):
        """Обновляет расчёт маржи и количества монет"""
        if not hasattr(self, 'calc_label') or not hasattr(self, 'position_input'):
            return
            
        position_usdt = self.position_input.value()
        leverage = self.leverage_spin.value()
        
        # Маржа = позиция / плечо
        margin = position_usdt / leverage
        
        # Количество монет (если есть цена)
        if self.current_price > 0:
            qty = position_usdt / self.current_price
            coin = self.symbol_combo.currentText()
            self.calc_label.setText(
                f"Маржа: ${margin:,.0f} | Позиция: ${position_usdt:,.0f}\n"
                f"Кол-во: {qty:,.4f} {coin} @ ${self.current_price:,.2f}"
            )
        else:
            self.calc_label.setText(f"Маржа: ${margin:,.0f} | Позиция: ${position_usdt:,.0f}")
    
    def set_price(self, price: float):
        """Устанавливает текущую цену для расчёта"""
        self.current_price = price
        self._update_calc()
        
    def set_enabled(self, enabled: bool):
        self.long_btn.setEnabled(enabled)
        self.short_btn.setEnabled(enabled)


class AutoTradePanel(QFrame):
    """Панель автоторговли по сигналам"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame#AutoTradePanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("AutoTradePanel")
        self.setMinimumHeight(340)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("🤖 Автоторговля")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        
        self.status_lbl = QLabel("⚪ Выкл")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        header.addWidget(self.status_lbl)
        layout.addLayout(header)
        
        # Info
        info = QLabel("Конфлюенс: EMA + Smart Money + Trend\nHTF фильтр | Вход только 3/3 | SL/TP от волатильности")
        info.setStyleSheet("""
            font-size: 12px; color: #888; 
            background: #1a1a22; 
            padding: 12px; border-radius: 8px;
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Settings row
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.addWidget(self._create_field_group("Таймфрейм", self._create_tf_combo()))
        row1.addWidget(self._create_field_group("Плечо", self._create_leverage_spin()))
        row1.addWidget(self._create_field_group("% баланса", self._create_risk_spin()))
        layout.addLayout(row1)
        
        # Coins
        coins_lbl = QLabel("Монеты:")
        coins_lbl.setStyleSheet("font-size: 13px; color: #888; font-weight: 500; background: transparent;")
        layout.addWidget(coins_lbl)
        
        coins_row = QHBoxLayout()
        coins_row.setSpacing(12)
        self.coin_checks: Dict[str, QCheckBox] = {}
        
        for coin in TOP_COINS:
            cb = QCheckBox(coin)
            cb.setChecked(coin in ["BTC", "ETH", "SOL", "XRP", "DOGE"])
            cb.setStyleSheet("""
                QCheckBox {
                    color: white; 
                    font-size: 13px;
                    spacing: 6px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 2px solid #444;
                    background: #1a1a22;
                }
                QCheckBox::indicator:checked {
                    background: #6C5CE7;
                    border-color: #6C5CE7;
                }
            """)
            self.coin_checks[coin] = cb
            coins_row.addWidget(cb)
        coins_row.addStretch()
        layout.addLayout(coins_row)
        
        # Button
        layout.addSpacing(4)
        self.toggle_btn = QPushButton("▶ Запустить автоторговлю")
        self.toggle_btn.setFixedHeight(48)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        layout.addWidget(self.toggle_btn)
        
    def _create_field_group(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 12px; color: #888; font-weight: 500; background: transparent;")
        vbox.addWidget(label)
        vbox.addWidget(widget)
        
        return container
        
    def _create_tf_combo(self) -> QComboBox:
        self.tf_combo = QComboBox()
        self.tf_combo.setFixedHeight(46)
        self.tf_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow { 
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
            }
            QComboBox QAbstractItemView {
                background: #2a2a35;
                color: #ffffff;
                selection-background-color: #6C5CE7;
            }
        """)
        for tf, name in [("1h", "1 час"), ("4h", "4 часа"), ("1d", "1 день")]:
            self.tf_combo.addItem(name, tf)
        return self.tf_combo
        
    def _create_leverage_spin(self) -> QSpinBox:
        self.auto_leverage = QSpinBox()
        self.auto_leverage.setFixedHeight(46)
        self.auto_leverage.setRange(5, 10)
        self.auto_leverage.setValue(5)
        self.auto_leverage.setSuffix("x")
        self.auto_leverage.setStyleSheet("""
            QSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.auto_leverage
        
    def _create_risk_spin(self) -> QDoubleSpinBox:
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setFixedHeight(46)
        self.risk_spin.setRange(0.5, 5.0)
        self.risk_spin.setValue(2.0)
        self.risk_spin.setDecimals(1)
        self.risk_spin.setSingleStep(0.5)
        self.risk_spin.setSuffix("%")
        self.risk_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.risk_spin
        
    def set_enabled(self, enabled: bool):
        self.toggle_btn.setEnabled(enabled)
        
    def set_running(self, running: bool):
        if running:
            self.status_lbl.setText("🟢 Активна")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #00D9A5; background: transparent;")
            self.toggle_btn.setText("⏹ Остановить")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['danger']};
                    border: none;
                    border-radius: 10px;
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: #ff4444; }}
            """)
        else:
            self.status_lbl.setText("⚪ Выкл")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
            self.toggle_btn.setText("▶ Запустить автоторговлю")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent']};
                    border: none;
                    border-radius: 10px;
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            """)


class TradeHistoryTable(QFrame):
    """Таблица истории сделок"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        title = QLabel("📜 История сделок")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Время", "Монета", "Тип", "Размер", "Цена", "PnL"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: transparent;
                border: none;
                color: {COLORS['text']};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background: {COLORS['bg_hover']};
                color: {COLORS['text_muted']};
                border: none;
                padding: 6px;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)
        
    def add_trade(self, time: str, symbol: str, side: str, size: float, price: float, pnl: float):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(time))
        self.table.setItem(row, 1, QTableWidgetItem(symbol))
        
        side_item = QTableWidgetItem("ЛОНГ" if side == "buy" else "ШОРТ")
        side_item.setForeground(QColor(COLORS['success'] if side == "buy" else COLORS['danger']))
        self.table.setItem(row, 2, side_item)
        
        self.table.setItem(row, 3, QTableWidgetItem(f"{size:.4f}"))
        self.table.setItem(row, 4, QTableWidgetItem(f"${price:,.2f}"))
        
        pnl_item = QTableWidgetItem(f"{'+'if pnl>=0 else ''}${pnl:.2f}")
        pnl_item.setForeground(QColor(COLORS['success'] if pnl >= 0 else COLORS['danger']))
        self.table.setItem(row, 5, pnl_item)


class BybitTerminal(QMainWindow):
    """Полноценный терминал Bybit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bybit Trading Terminal")
        self.setMinimumSize(1100, 700)
        
        self.exchange = None
        self.positions: List[dict] = []
        self.settings = QSettings("LocalSignals", "Terminal")
        self.auto_trading = False
        self.position_rows: List[PositionRow] = []
        self._auto_owned_symbols: set = set()
        self._strategy_symbol_locks: Dict[str, set] = {}
        self._inflight_symbol_keys: set = set()
        self._rule_closing_symbols: set = set()
        self._global_opposite_hits: Dict[str, int] = {}
        self._close_workers: Dict[str, AsyncCloseWorker] = {}
        self._stop_workers: Dict[str, AsyncStopSyncWorker] = {}
        self._stop_sync_last: Dict[str, tuple[float, float, float]] = {}
        self._stop_sync_error_until: Dict[str, float] = {}
        self._last_stop_sync_ts = 0.0
        self._stop_sync_interval_sec = 3.0
        self._stop_sync_min_update_sec = 45.0
        self._max_stop_updates_per_tick = 4
        self._last_exit_signal_scan_ts = 0.0
        self._exit_signal_scan_interval_sec = 10.0
        self._max_signal_checks_per_tick = 2
        self._exit_signal_rr_cursor = 0
        self._exit_rules_busy = False
        self._signal_cache: Dict[str, tuple[float, tuple]] = {}
        self._htf_cache: Dict[str, tuple[float, str]] = {}
        self._signal_cache_ttl_sec = 10.0
        self._htf_cache_ttl_sec = 20.0
        self._cache_lock = threading.Lock()
        self._auto_tf_cached = "1h"
        self._event_buffer: List[str] = []
        self._equity_buffer: List[list] = []
        self._io_lock = threading.Lock()
        self._last_snapshot_ts = 0.0
        self._last_refresh_ts = 0.0
        self._refresh_pending = False
        self._refresh_min_interval_sec = 0.8
        
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.events_file = os.path.join(self.data_dir, "runtime_events.jsonl")
        self.equity_file = os.path.join(self.data_dir, "equity_snapshots.csv")
        self._init_runtime_storage()
        self.io_flush_timer = QTimer(self)
        self.io_flush_timer.setTimerType(Qt.CoarseTimer)
        self.io_flush_timer.timeout.connect(self._flush_runtime_buffers)
        self.io_flush_timer.start(1200)
        
        self._setup_ui()
        
        # Начальный лог
        QTimer.singleShot(100, lambda: self._log("Подключись к Bybit Demo для начала торговли"))
        
        # Адаптивный размер - на весь экран
        screen = QApplication.primaryScreen().geometry()
        w = max(1100, int(screen.width() * 0.85))
        h = max(700, int(screen.height() * 0.8))
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        
        # Показываем инструкцию при первом запуске
        if not self.settings.value("instruction_shown", False):
            QTimer.singleShot(500, self._show_instruction)
        
        # Автоподключение по профилю/ключу
        QTimer.singleShot(800, self._try_auto_connect)
        
    def _show_instruction(self):
        dialog = InstructionDialog(self)
        if dialog.exec():
            if dialog.dont_show.isChecked():
                self.settings.setValue("instruction_shown", True)
                
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        # Фон
        self.bg = TerminalBackground(central)
        
        # Контент
        content = QWidget(central)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content
        main = QHBoxLayout()
        main.setSpacing(16)
        
        # Left column - Trading
        left = QVBoxLayout()
        left.setSpacing(12)
        
        # API Connection
        api_card = self._create_api_card()
        left.addWidget(api_card)
        
        # Order panel
        self.order_panel = OrderPanel()
        self.order_panel.order_submitted.connect(self._submit_order)
        left.addWidget(self.order_panel)

        # Multi-strategy panel (основной рабочий блок слева)
        from ui.strategy_panel import StrategyPanel
        self.strategy_panel = StrategyPanel()
        self.strategy_panel.start_clicked.connect(self._start_multi_strategies)
        self.strategy_panel.stop_clicked.connect(self._stop_multi_strategies)
        left.addWidget(self.strategy_panel)

        # Служебные панели создаём, но не показываем в UI.
        # Это сохраняет совместимость логики без загромождения интерфейса.
        self.auto_panel = AutoTradePanel()
        self.auto_panel.toggle_btn.clicked.connect(self._toggle_auto_trade)
        self.auto_panel.setVisible(False)

        from ui.grid_panel import GridPanel
        self.grid_panel = GridPanel()
        self.grid_panel.start_clicked.connect(self._start_grid_bot)
        self.grid_panel.stop_clicked.connect(self._stop_grid_bot)
        self.grid_panel.setVisible(True)
        left.addWidget(self.grid_panel)
        
        from ui.smart_ai_panel import SmartAIPanel
        self.smart_ai_panel = SmartAIPanel()
        self.smart_ai_panel.analyze_clicked.connect(self._analyze_smart_ai)
        self.smart_ai_panel.trade_clicked.connect(self._trade_smart_ai)
        self.smart_ai_panel.setVisible(False)
        
        # Загружаем стратегии
        self._load_strategies()
        
        # Загружаем сохранённые настройки автоторговли
        self._load_auto_settings()
        self._load_multi_settings()
        
        left.addStretch()
        
        # Wrap left column in scroll area
        left_content = QWidget()
        left_content.setLayout(left)
        left_content.setStyleSheet("background: transparent;")
        
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_content)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(440)
        left_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main.addWidget(left_scroll)
        
        # Right column - Info
        right = QVBoxLayout()
        right.setSpacing(12)
        
        # Balance
        self.balance_widget = BalanceWidget()
        right.addWidget(self.balance_widget)
        
        # === ВКЛАДКИ ===
        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {COLORS['bg_card']};
                color: {COLORS['text_muted']};
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['accent']};
                color: white;
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {COLORS['border']};
            }}
        """)
        
        # === TAB 1: Позиции ===
        positions_tab = QWidget()
        positions_layout = QVBoxLayout(positions_tab)
        positions_layout.setContentsMargins(0, 8, 0, 0)
        positions_layout.setSpacing(8)
        
        # Positions header
        pos_header = QHBoxLayout()
        pos_title = QLabel("📈 Открытые позиции")
        pos_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        pos_header.addWidget(pos_title)
        pos_header.addStretch()
        
        self.pos_count = QLabel("0")
        self.pos_count.setAlignment(Qt.AlignCenter)
        self.pos_count.setMinimumWidth(34)
        self.pos_count.setStyleSheet(f"""
            font-size: 11px; color: white;
            background: {COLORS['accent']}; padding: 3px 10px; border-radius: 6px;
        """)
        pos_header.addWidget(self.pos_count)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_data)
        pos_header.addWidget(self.refresh_btn)
        
        positions_layout.addLayout(pos_header)

        pos_cols = QLabel("Монета | Сторона | PnL | Плечо | Закрыть | Ниже: размер / вход / марк / причина")
        pos_cols.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; padding: 0 8px;")
        positions_layout.addWidget(pos_cols)
        
        # Positions scroll
        self.positions_scroll = QScrollArea()
        self.positions_scroll.setWidgetResizable(True)
        self.positions_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {COLORS['bg_card']}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['accent']}; border-radius: 3px;
            }}
        """)
        self.positions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.positions_scroll.setMinimumHeight(150)
        
        self.positions_widget = QWidget()
        self.positions_inner_layout = QVBoxLayout(self.positions_widget)
        self.positions_inner_layout.setSpacing(8)
        self.positions_inner_layout.setContentsMargins(0, 0, 0, 0)
        
        self.no_pos_lbl = QLabel("Нет открытых позиций")
        self.no_pos_lbl.setAlignment(Qt.AlignCenter)
        self.no_pos_lbl.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; padding: 30px;")
        self.positions_inner_layout.addWidget(self.no_pos_lbl)
        self.positions_inner_layout.addStretch()
        
        self.positions_scroll.setWidget(self.positions_widget)
        positions_layout.addWidget(self.positions_scroll)
        
        # Trade history (последние сделки)
        self.history_table = TradeHistoryTable()
        positions_layout.addWidget(self.history_table, 1)
        
        self.right_tabs.addTab(positions_tab, "📈 Позиции")
        
        # === TAB 2: Журнал сделок ===
        from ui.trade_journal import TradeJournalWidget
        self.journal_widget = TradeJournalWidget()
        self.right_tabs.addTab(self.journal_widget, "📊 Журнал")

        # === TAB 3: Монитор ===
        self.monitor_tab = QWidget()
        mon_layout = QVBoxLayout(self.monitor_tab)
        mon_layout.setContentsMargins(12, 12, 12, 12)
        mon_layout.setSpacing(10)

        self.mon_conn_lbl = QLabel("Подключение: —")
        self.mon_conn_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        mon_layout.addWidget(self.mon_conn_lbl)

        self.mon_pos_lbl = QLabel("Позиции: —")
        self.mon_pos_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        mon_layout.addWidget(self.mon_pos_lbl)

        self.mon_grid_lbl = QLabel("Grid Bot: —")
        self.mon_grid_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        mon_layout.addWidget(self.mon_grid_lbl)

        self.mon_strat_lbl = QLabel("Стратегии: —")
        self.mon_strat_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        mon_layout.addWidget(self.mon_strat_lbl)

        self.mon_risk_lbl = QLabel("Риск-контроль: —")
        self.mon_risk_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        mon_layout.addWidget(self.mon_risk_lbl)
        mon_layout.addStretch()

        self.right_tabs.addTab(self.monitor_tab, "🧭 Монитор")
        
        right.addWidget(self.right_tabs, 1)
        
        # Для совместимости со старым кодом
        self.positions_layout = self.positions_inner_layout
        
        main.addLayout(right, 1)
        layout.addLayout(main, 1)
        
        # Log panel - полноценная панель логов
        log_frame = QFrame()
        log_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        log_frame.setFixedHeight(120)
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 8, 12, 8)
        log_layout.setSpacing(4)
        
        log_header = QHBoxLayout()
        log_title = QLabel("📋 Логи торговли")
        log_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        log_header.addWidget(log_title)
        log_header.addStretch()
        
        # Profit badge
        self.profit_badge = QLabel("")
        self.profit_badge.setStyleSheet(f"""
            font-size: 11px; font-weight: 700; color: {COLORS['success']};
            background: rgba(0, 217, 165, 0.15); padding: 4px 10px; border-radius: 6px;
        """)
        self.profit_badge.hide()
        log_header.addWidget(self.profit_badge)
        
        log_layout.addLayout(log_header)
        
        # Log scroll area
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 2px; }}
        """)
        
        self.log_widget = QWidget()
        self.log_layout = QVBoxLayout(self.log_widget)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(2)
        self.log_layout.addStretch()
        
        self.log_scroll.setWidget(self.log_widget)
        log_layout.addWidget(self.log_scroll)
        
        layout.addWidget(log_frame)
        
        # Для совместимости
        self.log_lbl = None
        self.log_messages = []
        
        # Root layout
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content)
        
    def _create_header(self):
        header = QFrame()
        header.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Logo
        self.logo_lbl = QLabel()
        self.logo_lbl.setFixedSize(28, 28)
        LogoLoader.load(self._set_logo)
        layout.addWidget(self.logo_lbl)
        
        title = QLabel("Bybit Trading Terminal")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text']}; margin-left: 8px;")
        layout.addWidget(title)
        
        demo_badge = QLabel("DEMO")
        demo_badge.setStyleSheet(f"""
            font-size: 10px; font-weight: 700; color: {COLORS['warning']};
            background: rgba(253, 203, 110, 0.2);
            padding: 4px 10px; border-radius: 6px;
            margin-left: 12px;
        """)
        layout.addWidget(demo_badge)
        
        layout.addStretch()
        
        # Status
        self.status_lbl = QLabel("⚪ Не подключено")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['text_muted']};
            background: {COLORS['bg_hover']}; padding: 6px 14px; border-radius: 8px;
        """)
        layout.addWidget(self.status_lbl)
        
        export_btn = QPushButton("Экспорт")
        export_btn.setFixedHeight(28)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text']};
                font-size: 11px;
                padding: 0 10px;
            }}
            QPushButton:hover {{ border-color: {COLORS['accent']}; color: white; }}
        """)
        export_btn.clicked.connect(self._export_runtime_data)
        layout.addWidget(export_btn)
        
        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(28, 28)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 14px;
                color: {COLORS['text_muted']};
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}
        """)
        help_btn.clicked.connect(self._show_instruction)
        layout.addWidget(help_btn)
        
        return header
        
    def _set_logo(self, pixmap):
        if pixmap:
            self.logo_lbl.setPixmap(pixmap)
        else:
            self.logo_lbl.setText("🟠")
            self.logo_lbl.setStyleSheet("font-size: 20px;")
            
    def _create_api_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header с переключателем сети
        header = QHBoxLayout()
        title = QLabel("🔑 Подключение")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        header.addWidget(title)
        header.addStretch()
        
        # Скрываем переключатель - всегда Bybit Demo
        self.network_combo = QComboBox()
        self.network_combo.addItem("🧪 Demo", "demo")
        self.network_combo.setFixedWidth(110)
        self.network_combo.setVisible(False)  # Скрываем выбор
        self.network_combo.setCurrentIndex(0)
        header.addWidget(self.network_combo)
        layout.addLayout(header)
        
        # Убираем предупреждение для mainnet
        self.mainnet_warning = QLabel("")
        self.mainnet_warning.setVisible(False)
        layout.addWidget(self.mainnet_warning)
        
        # Профили API
        profiles_row = QHBoxLayout()
        profiles_row.setSpacing(8)
        self.profile_combo = QComboBox()
        self.profile_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_hover']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 8px;
                color: {COLORS['text']};
                font-size: 11px;
            }}
        """)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profiles_row.addWidget(self.profile_combo, 1)
        
        self.save_profile_btn = QPushButton("Сохранить")
        self.save_profile_btn.setFixedHeight(28)
        self.save_profile_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text']};
                font-size: 11px;
                padding: 0 8px;
            }}
            QPushButton:hover {{ border-color: {COLORS['accent']}; }}
        """)
        self.save_profile_btn.clicked.connect(self._save_profile_from_inputs)
        profiles_row.addWidget(self.save_profile_btn)
        
        self.default_profile_btn = QPushButton("По умолч.")
        self.default_profile_btn.setFixedHeight(28)
        self.default_profile_btn.setStyleSheet(self.save_profile_btn.styleSheet())
        self.default_profile_btn.clicked.connect(self._set_default_profile_from_combo)
        profiles_row.addWidget(self.default_profile_btn)
        layout.addLayout(profiles_row)
        
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("API Key")
        self.api_key.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 11px;
                color: {COLORS['text']};
            }}
        """)
        # Загружаем ключ: приоритет у config.json, затем QSettings
        cfg_key = ""
        cfg_secret = ""
        try:
            from core.config import config
            cfg_key, cfg_secret = config.get_api_credentials()
        except Exception:
            cfg_key, cfg_secret = "", ""
        saved_key = self.settings.value("api_key", "")
        if cfg_key:
            self.api_key.setText(cfg_key)
            self.settings.setValue("api_key", cfg_key)
        elif saved_key:
            self.api_key.setText(saved_key)
        layout.addWidget(self.api_key)
        
        self.api_secret = QLineEdit()
        self.api_secret.setPlaceholderText("API Secret")
        self.api_secret.setEchoMode(QLineEdit.Password)
        self.api_secret.setStyleSheet(self.api_key.styleSheet())
        # Загружаем секрет: приоритет у config.json, затем QSettings
        saved_secret = self.settings.value("api_secret", "")
        if cfg_secret:
            self.api_secret.setText(cfg_secret)
            self.settings.setValue("api_secret", cfg_secret)
        elif saved_secret:
            self.api_secret.setText(saved_secret)
        layout.addWidget(self.api_secret)
        
        self._load_api_profiles(cfg_key, cfg_secret)
        
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(34)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
        """)
        self.connect_btn.clicked.connect(self._connect)
        layout.addWidget(self.connect_btn)
        
        return card

    def _load_api_profiles(self, cfg_key: str = "", cfg_secret: str = ""):
        raw = self.settings.value("api_profiles_json", "[]")
        try:
            profiles = json.loads(raw) if raw else []
        except Exception:
            profiles = []
        if not isinstance(profiles, list):
            profiles = []
        
        # Ensure current config key exists as a profile.
        if cfg_key and cfg_secret:
            if not any((p.get("api_key") == cfg_key) for p in profiles if isinstance(p, dict)):
                profiles.insert(0, {
                    "name": "Config Key",
                    "api_key": cfg_key,
                    "api_secret": cfg_secret,
                })
                self.settings.setValue("api_profiles_json", json.dumps(profiles, ensure_ascii=False))
        
        self.api_profiles = [p for p in profiles if isinstance(p, dict) and p.get("api_key") and p.get("api_secret")]
        default_name = str(self.settings.value("api_default_profile", "") or "")
        
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("Текущий ключ", "__current__")
        default_index = 0
        for i, p in enumerate(self.api_profiles, start=1):
            name = str(p.get("name") or f"Profile {i}")
            key = str(p.get("api_key"))
            masked = f"{name} ({key[:6]}...{key[-4:]})" if len(key) > 10 else name
            self.profile_combo.addItem(masked, name)
            if name == default_name:
                default_index = i
        self.profile_combo.setCurrentIndex(default_index)
        self.profile_combo.blockSignals(False)
    
    def _on_profile_changed(self, index: int):
        data = self.profile_combo.itemData(index)
        if data == "__current__":
            return
        name = str(data or "")
        for p in getattr(self, "api_profiles", []):
            if str(p.get("name")) == name:
                self.api_key.setText(str(p.get("api_key") or ""))
                self.api_secret.setText(str(p.get("api_secret") or ""))
                return
    
    def _save_profile_from_inputs(self):
        key = self.api_key.text().strip()
        secret = self.api_secret.text().strip()
        if not key or not secret:
            self._log("⚠️ Нельзя сохранить пустой профиль")
            return
        name = f"Key {key[:6]}"
        profiles = getattr(self, "api_profiles", [])
        replaced = False
        for p in profiles:
            if p.get("api_key") == key:
                p["api_secret"] = secret
                p["name"] = str(p.get("name") or name)
                replaced = True
                break
        if not replaced:
            profiles.append({"name": name, "api_key": key, "api_secret": secret})
        self.settings.setValue("api_profiles_json", json.dumps(profiles, ensure_ascii=False))
        self.api_profiles = profiles
        self._load_api_profiles()
        self._log("💾 Профиль API сохранён")
    
    def _set_default_profile_from_combo(self):
        index = self.profile_combo.currentIndex()
        data = self.profile_combo.itemData(index)
        if data == "__current__":
            # Save current as profile and set it default
            self._save_profile_from_inputs()
            index = self.profile_combo.currentIndex()
            data = self.profile_combo.itemData(index)
            if data == "__current__":
                self._log("⚠️ Выберите профиль для установки по умолчанию")
                return
        self.settings.setValue("api_default_profile", str(data))
        self._log(f"✅ Профиль по умолчанию: {data}")
    
    def _try_auto_connect(self):
        if self.exchange:
            return
        auto = self.settings.value("api_auto_connect", "true")
        if not (auto == "true" or auto is True):
            return
        
        # Prefer default profile if exists.
        default_name = str(self.settings.value("api_default_profile", "") or "")
        selected = None
        for p in getattr(self, "api_profiles", []):
            if str(p.get("name")) == default_name:
                selected = p
                break
        if selected is None and getattr(self, "api_profiles", []):
            selected = self.api_profiles[0]
        
        if selected:
            self.api_key.setText(str(selected.get("api_key") or ""))
            self.api_secret.setText(str(selected.get("api_secret") or ""))
        
        if self.api_key.text().strip() and self.api_secret.text().strip():
            self._log("🔐 Автоподключение по сохранённому ключу...")
            self._connect()
    
    def _on_network_changed(self, index):
        """Обработка смены сети"""
        network = self.network_combo.currentData()
        self.mainnet_warning.setVisible(network == "mainnet")
        self.settings.setValue("network", network)
        
        # Отключаемся если были подключены
        if self.exchange:
            self.exchange = None
            self._log("🔄 Сеть изменена — переподключитесь")
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bg'):
            self.bg.setGeometry(self.centralWidget().rect())
            
    def _log(self, msg: str, msg_type: str = "info"):
        """Добавляет сообщение в лог. msg_type: info, error, profit"""
        time_str = datetime.now().strftime('%H:%M:%S')
        
        # Время всегда серым
        time_color = COLORS['text_muted']
        text_color = COLORS['text']
        
        # Если есть PnL — красим только сумму
        if "PnL:" in msg:
            import re
            # Ищем PnL: $... или PnL: +$... или PnL: -$...
            match = re.search(r'(PnL:\s*)([+\-]?\$[\d.,]+)', msg)
            if match:
                before_pnl = msg[:match.start()]
                pnl_label = match.group(1)  # "PnL: "
                pnl_value = match.group(2)  # "+$10.15" или "$-1.03"
                after_pnl = msg[match.end():]
                
                # Определяем цвет PnL
                if '-' in pnl_value or pnl_value.startswith('$-'):
                    pnl_color = COLORS['danger']  # Красный для минуса
                else:
                    pnl_color = COLORS['success']  # Зелёный для плюса
                
                html = (f'<span style="color: {time_color};">[{time_str}]</span> '
                       f'<span style="color: {text_color};">{before_pnl}{pnl_label}</span>'
                       f'<span style="color: {pnl_color};">{pnl_value}</span>'
                       f'<span style="color: {text_color};">{after_pnl}</span>')
            else:
                html = f'<span style="color: {time_color};">[{time_str}]</span> <span style="color: {text_color};">{msg}</span>'
        elif "❌" in msg:
            # Ошибки красным
            html = f'<span style="color: {time_color};">[{time_str}]</span> <span style="color: {COLORS["danger"]};">{msg}</span>'
        else:
            # Обычные сообщения
            html = f'<span style="color: {time_color};">[{time_str}]</span> <span style="color: {text_color};">{msg}</span>'
        
        log_entry = QLabel(html)
        log_entry.setTextFormat(Qt.RichText)
        log_entry.setStyleSheet(f"font-size: 11px; padding: 2px 0;")
        log_entry.setWordWrap(True)
        
        # Добавляем в начало (перед stretch)
        self.log_layout.insertWidget(self.log_layout.count() - 1, log_entry)
        
        # Ограничиваем количество логов
        if self.log_layout.count() > 51:  # 50 логов + stretch
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Скроллим вниз
        QTimer.singleShot(50, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()
        ))
        self._append_event("log", {"msg": msg, "type": msg_type})
        
    def _show_profit(self, pnl: float):
        """Показывает бейдж с профитом если он хороший"""
        if pnl >= 5:  # Если профит >= $5
            self.profit_badge.setText(f"🎉 +${pnl:.2f}")
            self.profit_badge.show()
            # Скрываем через 10 секунд
            QTimer.singleShot(10000, self.profit_badge.hide)
        
    def _connect(self):
        if ccxt is None:
            QMessageBox.critical(self, "Ошибка", "pip install ccxt")
            return
            
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Ошибка", "Введи API Key и Secret")
            return
        
        # Проверяем сеть - всегда demo
        is_mainnet = False
        
        # Убираем предупреждение для mainnet
        
        # Показываем что идёт подключение
        network_name = "Bybit Demo"
        
        # Защита от повторного запуска
        if hasattr(self, 'connect_worker') and self.connect_worker and self.connect_worker.isRunning():
            self._log("⚠️ Подключение уже выполняется")
            return
        
        self.connect_btn.setText("⏳ Подключение...")
        self.connect_btn.setEnabled(False)
        self.status_lbl.setText(f"🔄 Подключение к {network_name}...")
        
        # Запускаем воркер
        self.connect_worker = ConnectWorker(api_key, api_secret, is_mainnet)
        self.connect_worker.success.connect(lambda ex: self._on_connect_success(ex, is_mainnet))
        self.connect_worker.error.connect(self._on_connect_error)
        self.connect_worker.log.connect(self._log)
        self.connect_worker.start()
        
    def _on_connect_success(self, exchange, is_mainnet: bool = False):
        """Вызывается при успешном подключении"""
        self.exchange = exchange
        self.is_mainnet = is_mainnet
        
        # Сохраняем ключи
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()
        self.settings.setValue("api_key", api_key)
        self.settings.setValue("api_secret", api_secret)
        self.settings.setValue("api_auto_connect", "true")
        
        network_name = "Bybit Demo 🧪"
        status_color = COLORS['success']
        
        self.status_lbl.setText(f"🟢 {network_name}")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {status_color};
            background: rgba(0, 217, 165, 0.15); padding: 6px 14px; border-radius: 8px;
        """)
        
        self.connect_btn.setText(f"✓ {network_name}")
        self.connect_btn.setEnabled(False)
        
        self.order_panel.set_enabled(True)
        self.auto_panel.set_enabled(True)
        self.strategy_panel.set_enabled(True)
        self.grid_panel.set_enabled(True)
        self.smart_ai_panel.set_enabled(True)
        self.refresh_btn.setEnabled(True)
        
        # Передаём exchange в Smart AI Panel для авто-режима
        from strategies.smart_ai_bot import SmartAIBot
        smart_bot = SmartAIBot(exchange)
        self.smart_ai_panel.set_bot(smart_bot, exchange)
        self.smart_ai_panel.log_signal.connect(self._log)
        
        self._log(f"✅ Успешно подключено к Bybit Demo!")
        self._refresh_data()
        self._update_monitor()
        
        # Auto refresh каждые 5 сек
        if not hasattr(self, 'refresh_timer') or self.refresh_timer is None:
            self.refresh_timer = QTimer(self)
            self.refresh_timer.setTimerType(Qt.CoarseTimer)
            self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(5000)

        # Exit-rules тикер: отдельный цикл, чтобы не блокировать refresh-отрисовку.
        if not hasattr(self, 'exit_rules_timer') or self.exit_rules_timer is None:
            self.exit_rules_timer = QTimer(self)
            self.exit_rules_timer.setTimerType(Qt.CoarseTimer)
            self.exit_rules_timer.timeout.connect(self._run_exit_rules_tick)
        self.exit_rules_timer.start(1200)
        
        # Автозапуск автоторговли если была включена
        was_auto_trading = self.settings.value("auto_trading", "false")
        if was_auto_trading == "true" or was_auto_trading == True:
            self._log("🔄 Восстанавливаю автоторговлю...")
            QTimer.singleShot(2000, self._start_auto_trade)  # Запускаем через 2 сек
        
        multi_enabled = self.settings.value("multi_enabled", "false")
        if multi_enabled == "true" or multi_enabled is True:
            self._log("🔄 Восстанавливаю мульти-стратегии...")
            QTimer.singleShot(3000, self._restore_multi_strategies)
        
        if not hasattr(self, "strategy_watchdog"):
            self.strategy_watchdog = QTimer(self)
            self.strategy_watchdog.timeout.connect(self._strategy_watchdog_tick)
        self.strategy_watchdog.start(60000)
            
    def _start_auto_trade(self):
        """Запускает автоторговлю (без toggle)"""
        if self.auto_trading:
            return  # Уже запущена
            
        self.auto_trading = True
        self.auto_panel.set_running(True)
        self._save_auto_settings()
        
        self._log("🤖 Автоторговля запущена - торгую на 5-10% от баланса")
        
        # Проверяем есть ли открытые позиции от бота
        bot_coins = self.settings.value("auto_coins", "").split(",")
        if bot_coins:
            for pos in self.positions:
                coin = pos.get('symbol', '').split('/')[0]
                if coin in bot_coins:
                    self._log(f"📍 Найдена позиция бота: {coin}")
        
        if not hasattr(self, 'auto_timer'):
            self.auto_timer = QTimer()
            self.auto_timer.timeout.connect(self._run_auto_worker)
        self.auto_timer.start(60000)
        QTimer.singleShot(1000, self._run_auto_worker)
        
    def _on_connect_error(self, error: str):
        """Вызывается при ошибке подключения"""
        self.connect_btn.setText("🔌 Подключить")
        self.connect_btn.setEnabled(True)
        self.status_lbl.setText("⚪ Не подключено")
        self._log(f"❌ Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка подключения", error)
            
    def _refresh_data(self):
        if not self.exchange:
            return

        now = time.time()
        delta = now - float(self._last_refresh_ts or 0.0)
        if delta < self._refresh_min_interval_sec:
            if not self._refresh_pending:
                self._refresh_pending = True
                wait_ms = int((self._refresh_min_interval_sec - delta) * 1000) + 40
                QTimer.singleShot(max(80, wait_ms), self._refresh_data)
            return
        
        # Если уже идёт обновление - пропускаем
        if hasattr(self, 'refresh_worker') and self.refresh_worker.isRunning():
            if not self._refresh_pending:
                self._refresh_pending = True
                QTimer.singleShot(180, self._refresh_data)
            return

        self._refresh_pending = False
        self._last_refresh_ts = now
        symbol = self.order_panel.symbol_combo.currentData()
        self.refresh_worker = RefreshWorker(self.exchange, symbol)
        self.refresh_worker.data_ready.connect(self._on_data_ready)
        self.refresh_worker.price_ready.connect(self._on_price_ready)
        self.refresh_worker.error.connect(lambda e: self._log(f"Ошибка обновления: {e}"))
        self.refresh_worker.start()
        
    def _on_data_ready(self, available: float, total: float, pnl: float, positions: list):
        """Вызывается когда данные готовы"""
        self.balance_widget.update_balance(available, total, pnl)
        
        # Отслеживаем закрытые позиции для журнала
        self._check_closed_positions(positions)
        
        self._update_positions(positions)
        if positions:
            self._sync_protective_stops(positions)
        self._update_monitor(available, total, pnl, positions)
        self._record_equity_snapshot(available, total, pnl, len(positions))

    def _run_exit_rules_tick(self):
        if self._exit_rules_busy:
            return
        if not self.exchange:
            return
        if not self.positions:
            return
        self._exit_rules_busy = True
        try:
            self._sync_protective_stops(list(self.positions))
            self._enforce_position_exit_rules(list(self.positions))
        finally:
            self._exit_rules_busy = False

    def _update_monitor(self, available: float = 0.0, total: float = 0.0, pnl: float = 0.0, positions: list | None = None):
        """Обновляет вкладку мониторинга состояния терминала."""
        if not hasattr(self, "mon_conn_lbl"):
            return

        is_connected = self.exchange is not None
        self.mon_conn_lbl.setText(
            f"Подключение: {'✅ Bybit Demo' if is_connected else '❌ Не подключено'} | "
            f"Доступно ${available:,.2f} | Эквити ${total:,.2f} | PnL ${pnl:,.2f}"
        )

        positions = positions or []
        gross_exposure = 0.0
        for p in positions:
            qty = float(p.get('contracts') or 0)
            mark = float(p.get('markPrice') or 0)
            gross_exposure += abs(qty * mark)
        self.mon_pos_lbl.setText(
            f"Позиции: {len(positions)} | Валовая экспозиция: ${gross_exposure:,.2f}"
        )

        if hasattr(self, 'grid_bot'):
            try:
                s = self.grid_bot.get_stats()
                status = "🟢 Работает" if s.get("is_running") else "⚪ Выкл"
                self.mon_grid_lbl.setText(
                    f"Grid Bot: {status} | Profit ${float(s.get('total_profit', 0)):,.2f} | "
                    f"Trades {int(s.get('trades_count', 0))} | Orders {int(s.get('active_orders', 0))} | Levels {int(s.get('grid_levels', 0))}"
                )
            except Exception:
                self.mon_grid_lbl.setText("Grid Bot: ⚪ Выкл")
        else:
            self.mon_grid_lbl.setText("Grid Bot: ⚪ Выкл")

        active_strats = 0
        if hasattr(self, 'strategy_manager') and self.strategy_manager and getattr(self.strategy_manager, 'active_strategies', None):
            active_strats = len(self.strategy_manager.active_strategies)
        self.mon_strat_lbl.setText(
            f"Стратегии: {active_strats} активных | Автоторговля: {'ON' if self.auto_trading else 'OFF'}"
        )

        tracked = getattr(self, '_tracked_positions', {})
        local_protected = sum(
            1 for v in tracked.values()
            if (v.get('sl_price') or 0) > 0 and (v.get('tp_price') or 0) > 0 and not bool(v.get('sl_tp_on_exchange', False))
        )
        self.mon_risk_lbl.setText(
            f"Риск-контроль: локальная защита SL/TP для {local_protected} поз."
        )

    def _close_position_by_rules(
        self,
        pos: dict,
        close_reason: str,
        notes: str = "",
    ) -> bool:
        return self._request_rule_close(pos, close_reason, notes)

    def _request_rule_close(self, pos: dict, close_reason: str, notes: str = "") -> bool:
        if not self.exchange:
            return False

        symbol = str(pos.get('symbol') or '')
        side = (pos.get('side') or '').lower()
        size = float(pos.get('contracts') or 0)
        if not symbol or size <= 0 or side not in ("long", "short"):
            return False
        if symbol in self._rule_closing_symbols:
            return False
        if symbol in self._close_workers:
            return False

        self._rule_closing_symbols.add(symbol)
        pos_copy = dict(pos)
        pos_copy["_notes"] = notes or ""
        pos_copy["_close_reason"] = close_reason

        worker = AsyncCloseWorker(self.exchange, symbol, side, size, close_reason)
        self._close_workers[symbol] = worker
        worker.success.connect(lambda payload, p=pos_copy: self._on_rule_close_success(payload, p))
        worker.error.connect(self._on_rule_close_error)
        worker.finished.connect(lambda s=symbol: self._close_workers.pop(s, None))
        worker.start()
        return True

    def _on_rule_close_success(self, payload: dict, pos: dict):
        symbol = str(payload.get("symbol") or pos.get('symbol') or '')
        close_reason = str(payload.get("close_reason") or pos.get("_close_reason") or "Rule")
        exit_price = float(payload.get("exit_price") or 0)
        side = (pos.get('side') or '').lower()
        size = float(pos.get('contracts') or 0)
        pnl = float(pos.get('unrealizedPnl') or 0)
        entry_price = float(pos.get('entryPrice') or 0)
        leverage = int(pos.get('leverage') or 1)
        notes = str(pos.get("_notes") or "")

        coin = self._symbol_key(symbol) or symbol.split('/')[0]
        pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}"
        self._log(f"✅ Закрыто {coin} по {close_reason} | PnL: {pnl_str}", "error" if pnl < 0 else "info")
        if notes:
            self._log(f"   {notes}")

        if symbol in self._auto_owned_symbols:
            self._auto_owned_symbols.discard(symbol)

        meta = self._get_position_meta(symbol) if hasattr(self, "_get_position_meta") else {}
        strategy = str(meta.get('strategy') or 'System')
        sl_price = float(meta.get('sl_price') or 0)
        tp_price = float(meta.get('tp_price') or 0)
        timestamp_open = meta.get('timestamp_open')

        self.history_table.add_trade(
            datetime.now().strftime("%H:%M:%S"),
            coin,
            "sell" if side == "long" else "buy",
            size,
            exit_price,
            pnl,
        )
        self._add_to_journal(
            symbol=symbol,
            side=side,
            strategy=strategy,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            leverage=leverage,
            pnl_usd=pnl,
            close_reason=close_reason,
            sl_price=sl_price,
            tp_price=tp_price,
            timestamp_open=timestamp_open,
            notes=notes,
        )

        if hasattr(self, '_tracked_positions'):
            self._tracked_positions.pop(symbol, None)

        key = self._symbol_key(symbol)
        for sid, lockset in self._strategy_symbol_locks.items():
            if key in lockset:
                lockset.discard(key)
        self._global_opposite_hits.pop(f"{symbol}:{side}", None)
        self._rule_closing_symbols.discard(symbol)
        self._refresh_data()

    def _on_rule_close_error(self, symbol: str, close_reason: str, error: str):
        self._rule_closing_symbols.discard(symbol)
        self._log(f"❌ Ошибка закрытия по правилу ({close_reason}) {symbol}: {error}")

    def _enforce_position_exit_rules(self, positions: list):
        """
        Закрывает позиции по правилам:
        1) SL/TP (биржевые или локально отслеживаемые)
        2) Сильный противоположный сигнал (3/3 + 2 подтверждения)
        """
        if not self.exchange or not positions:
            return

        tf = "1h"
        if hasattr(self, 'auto_panel') and self.auto_panel:
            tf = self.auto_panel.tf_combo.currentData() or "1h"
        opposite_min_confluence = 3
        opposite_confirmations = 2
        now_ts = time.time()
        signal_scan_due = (now_ts - float(self._last_exit_signal_scan_ts or 0.0)) >= self._exit_signal_scan_interval_sec
        signal_checked = 0
        signal_limit = max(1, int(self._max_signal_checks_per_tick))

        scan_positions = positions
        if signal_scan_due and positions:
            n = len(positions)
            start = self._exit_signal_rr_cursor % n
            scan_positions = positions[start:] + positions[:start]
        else:
            scan_positions = positions

        for pos in scan_positions:
            symbol = str(pos.get('symbol') or '')
            if not symbol or float(pos.get('contracts') or 0) <= 0:
                continue
            if symbol in self._rule_closing_symbols:
                continue

            side = (pos.get('side') or '').lower()
            mark = float(pos.get('markPrice') or 0)
            meta = self._get_position_meta(symbol)
            sl_price = float(meta.get('sl_price') or pos.get('stopLoss') or 0)
            tp_price = float(meta.get('tp_price') or pos.get('takeProfit') or 0)

            # Приоритет закрытия — стоп/тейк.
            if mark > 0 and sl_price > 0 and tp_price > 0:
                sl_hit = (side == "long" and mark <= sl_price) or (side == "short" and mark >= sl_price)
                tp_hit = (side == "long" and mark >= tp_price) or (side == "short" and mark <= tp_price)
                if sl_hit:
                    if self._close_position_by_rules(
                        pos,
                        close_reason="SL",
                        notes=f"Локальный/биржевой стоп: mark ${mark:,.2f} | SL ${sl_price:,.2f}",
                    ):
                        continue
                if tp_hit:
                    if self._close_position_by_rules(
                        pos,
                        close_reason="TP",
                        notes=f"Локальный/биржевой тейк: mark ${mark:,.2f} | TP ${tp_price:,.2f}",
                    ):
                        continue

            # Сильный обратный сигнал — считаем реже, чтобы не грузить UI/индикаторы.
            if not signal_scan_due:
                continue
            if signal_checked >= signal_limit:
                continue
            signal_checked += 1
            coin = self._symbol_key(symbol) or symbol.split('/')[0]
            try:
                signal, strength, details = self._get_confluence_signal(coin)
            except Exception:
                signal, strength, details = "none", 0, ""
            try:
                htf_trend = self._get_htf_trend(coin, tf)
            except Exception:
                htf_trend = "neutral"

            opposite = (
                (side == "long" and signal == "sell" and htf_trend == "bear")
                or (side == "short" and signal == "buy" and htf_trend == "bull")
            )
            hit_key = f"{symbol}:{side}"
            if opposite and int(strength) >= opposite_min_confluence:
                self._global_opposite_hits[hit_key] = self._global_opposite_hits.get(hit_key, 0) + 1
            else:
                self._global_opposite_hits[hit_key] = 0

            if self._global_opposite_hits.get(hit_key, 0) >= opposite_confirmations:
                self._global_opposite_hits[hit_key] = 0
                self._close_position_by_rules(
                    pos,
                    close_reason="Signal",
                    notes=(
                        f"Сильный противоположный сигнал ({strength}/3, {opposite_confirmations} подтверждения). "
                        f"HTF={htf_trend}. {details}"
                    ),
                )
        if signal_scan_due:
            self._last_exit_signal_scan_ts = now_ts
            if scan_positions:
                self._exit_signal_rr_cursor = (self._exit_signal_rr_cursor + signal_checked) % max(1, len(scan_positions))

    def _sync_protective_stops(self, positions: list):
        """
        Обеспечивает защиту всех позиций:
        - всегда поддерживает локальные SL/TP в tracked-meta;
        - по возможности синхронизирует SL/TP на биржу.
        """
        if not self.exchange or not positions:
            return
        now = time.time()
        force_sync_needed = any(
            float(p.get('stopLoss') or 0) <= 0 or float(p.get('takeProfit') or 0) <= 0
            for p in positions
        )
        if (not force_sync_needed) and (now - float(self._last_stop_sync_ts or 0.0)) < self._stop_sync_interval_sec:
            return
        self._last_stop_sync_ts = now

        tf = self._auto_tf_cached or "1h"
        sync_started = 0
        max_sync = max(1, int(self._max_stop_updates_per_tick))

        for pos in positions:
            if sync_started >= max_sync:
                break
            symbol = str(pos.get('symbol') or '')
            if not symbol:
                continue
            side_raw = (pos.get('side') or '').lower()
            side = "buy" if side_raw == "long" else "sell"
            entry = float(pos.get('entryPrice') or 0)
            if entry <= 0:
                continue

            exch_sl = float(pos.get('stopLoss') or 0)
            exch_tp = float(pos.get('takeProfit') or 0)
            meta = self._get_position_meta(symbol)
            meta_sl = float(meta.get('sl_price') or 0)
            meta_tp = float(meta.get('tp_price') or 0)
            model = str(meta.get('risk_model') or "cached")
            use_cached_meta = meta_sl > 0 and meta_tp > 0
            if use_cached_meta:
                refined_sl = float(meta_sl)
                refined_tp = float(meta_tp)
            else:
                base_sl = exch_sl
                base_tp = exch_tp
                refined_sl, refined_tp, model = self._refine_sl_tp_prices(
                    symbol=symbol,
                    side=side,
                    entry_price=entry,
                    sl_price=base_sl,
                    tp_price=base_tp,
                    timeframe=tf,
                )

            is_long = side == "buy"
            if is_long:
                if refined_sl >= entry:
                    refined_sl = round(entry * 0.99, 2)
                if refined_tp <= entry:
                    refined_tp = round(entry * 1.018, 2)
            else:
                if refined_sl <= entry:
                    refined_sl = round(entry * 1.01, 2)
                if refined_tp >= entry:
                    refined_tp = round(entry * 0.982, 2)

            if not hasattr(self, '_tracked_positions'):
                self._tracked_positions = {}
            if symbol not in self._tracked_positions:
                self._tracked_positions[symbol] = {
                    'entry_price': entry,
                    'side': side_raw,
                    'size': float(pos.get('contracts') or 0),
                    'leverage': int(pos.get('leverage') or 1),
                    'strategy': str(pos.get('info', {}).get('strategy', 'System')),
                    'open_reason': str(pos.get('info', {}).get('open_reason', '')),
                    'timestamp_open': datetime.now().isoformat(),
                }
            self._tracked_positions[symbol]['sl_price'] = float(refined_sl)
            self._tracked_positions[symbol]['tp_price'] = float(refined_tp)
            self._tracked_positions[symbol]['risk_model'] = model

            need_exchange_sync = (
                exch_sl <= 0
                or exch_tp <= 0
                or (entry > 0 and abs(exch_sl - refined_sl) / entry > 0.0015)
                or (entry > 0 and abs(exch_tp - refined_tp) / entry > 0.0020)
            )
            if not need_exchange_sync:
                self._tracked_positions[symbol]['sl_tp_on_exchange'] = True
                continue

            last = self._stop_sync_last.get(symbol)
            if last:
                last_ts, last_sl, last_tp = float(last[0]), float(last[1]), float(last[2])
                same_as_last = (
                    entry > 0
                    and abs(last_sl - refined_sl) / entry < 0.0008
                    and abs(last_tp - refined_tp) / entry < 0.0010
                )
                if same_as_last and (now - last_ts) < self._stop_sync_min_update_sec:
                    continue
                if (exch_sl > 0 and exch_tp > 0) and (now - last_ts) < self._stop_sync_min_update_sec:
                    continue
            if symbol in self._stop_workers:
                continue

            if now < float(self._stop_sync_error_until.get(symbol, 0.0)):
                continue

            worker = AsyncStopSyncWorker(self.exchange, symbol, refined_sl, refined_tp)
            self._stop_workers[symbol] = worker
            worker.success.connect(self._on_stop_sync_success)
            worker.error.connect(self._on_stop_sync_error)
            worker.finished.connect(lambda s=symbol: self._stop_workers.pop(s, None))
            worker.start()
            sync_started += 1

    def _on_stop_sync_success(self, symbol: str, sl_price: float, tp_price: float):
        prev = self._stop_sync_last.get(symbol)
        self._stop_sync_last[symbol] = (time.time(), float(sl_price), float(tp_price))
        if hasattr(self, '_tracked_positions') and symbol in self._tracked_positions:
            self._tracked_positions[symbol]['sl_tp_on_exchange'] = True
            self._tracked_positions[symbol]['sl_price'] = float(sl_price)
            self._tracked_positions[symbol]['tp_price'] = float(tp_price)
        changed = True
        if prev:
            changed = (
                abs(float(prev[1]) - float(sl_price)) > 0.01
                or abs(float(prev[2]) - float(tp_price)) > 0.01
            )
        if changed:
            coin = self._symbol_key(symbol) or symbol.split('/')[0]
            self._log(f"🛡️ {coin}: защитные SL/TP синхронизированы")

    def _on_stop_sync_error(self, symbol: str, error: str):
        err = str(error).lower()
        now = time.time()
        # Глушим повторные ошибки API-доступа, но локальные стопы продолжают работать.
        if ("10005" in err) or ("permission denied" in err) or ("query-api" in err):
            self._stop_sync_error_until[symbol] = now + 300
            if hasattr(self, '_tracked_positions') and symbol in self._tracked_positions:
                self._tracked_positions[symbol]['sl_tp_on_exchange'] = False
            return
        self._stop_sync_error_until[symbol] = now + 90
        if hasattr(self, '_tracked_positions') and symbol in self._tracked_positions:
            self._tracked_positions[symbol]['sl_tp_on_exchange'] = False
        coin = self._symbol_key(symbol) or symbol.split('/')[0]
        self._log(f"⚠️ {coin}: не удалось выставить SL/TP на бирже ({error})")
    
    def _check_closed_positions(self, new_positions: list):
        """Проверяет какие позиции закрылись и записывает в журнал"""
        if not hasattr(self, '_tracked_positions'):
            self._tracked_positions = {}
            
        # Текущие символы
        current_symbols = {p.get('symbol') for p in new_positions if float(p.get('contracts', 0)) > 0}
        
        # Проверяем какие позиции закрылись
        closed = []
        for symbol, pos_data in list(self._tracked_positions.items()):
            if symbol not in current_symbols:
                closed.append((symbol, pos_data))
                del self._tracked_positions[symbol]
        
        # Записываем закрытые в журнал
        for symbol, pos_data in closed:
            try:
                # Получаем текущую цену как цену выхода
                ticker = self.exchange.fetch_ticker(symbol)
                exit_price = ticker['last']
                
                entry_price = pos_data['entry_price']
                side = pos_data['side']
                size = pos_data['size']
                leverage = pos_data['leverage']
                strategy = pos_data.get('strategy', 'Unknown')
                
                # Рассчитываем PnL
                if side == "long":
                    pnl_usd = (exit_price - entry_price) * size
                else:
                    pnl_usd = (entry_price - exit_price) * size
                
                # Определяем причину закрытия
                if side == "long":
                    if exit_price <= pos_data.get('sl_price', 0):
                        close_reason = "SL"
                    elif exit_price >= pos_data.get('tp_price', float('inf')):
                        close_reason = "TP"
                    else:
                        close_reason = "Unknown"
                else:
                    if exit_price >= pos_data.get('sl_price', float('inf')):
                        close_reason = "SL"
                    elif exit_price <= pos_data.get('tp_price', 0):
                        close_reason = "TP"
                    else:
                        close_reason = "Unknown"
                
                coin = symbol.split('/')[0]
                pnl_str = f"{'+'if pnl_usd>=0 else ''}${pnl_usd:.2f}"
                self._log(f"📝 {coin} закрыто по {close_reason} | PnL: {pnl_str}")
                
                self._add_to_journal(
                    symbol=symbol,
                    side=side,
                    strategy=strategy,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    size=size,
                    leverage=leverage,
                    pnl_usd=pnl_usd,
                    close_reason=close_reason,
                    sl_price=pos_data.get('sl_price', 0),
                    tp_price=pos_data.get('tp_price', 0),
                    timestamp_open=pos_data.get('timestamp_open')
                )
            except Exception as e:
                self._log(f"⚠️ Ошибка записи в журнал: {e}")
            finally:
                if symbol in self._auto_owned_symbols:
                    self._auto_owned_symbols.discard(symbol)
                # Освобождаем locks по символу для всех стратегий, если позиция по символу закрылась.
                key = self._symbol_key(symbol)
                for sid, lockset in self._strategy_symbol_locks.items():
                    if key in lockset:
                        lockset.discard(key)
                        self._log(f"🔓 Разблокирован {symbol} для стратегии {sid}")
        
        # Обновляем отслеживаемые позиции
        for pos in new_positions:
            symbol = pos.get('symbol')
            if symbol and float(pos.get('contracts', 0)) > 0:
                if symbol not in self._tracked_positions:
                    self._tracked_positions[symbol] = {
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'side': (pos.get('side') or '').lower(),
                        'size': float(pos.get('contracts', 0)),
                        'leverage': int(pos.get('leverage', 1)),
                        'strategy': pos.get('info', {}).get('strategy', 'Manual'),
                        'open_reason': pos.get('info', {}).get('open_reason', ''),
                        'sl_price': float(pos.get('stopLoss', 0) or 0),
                        'tp_price': float(pos.get('takeProfit', 0) or 0),
                        'sl_tp_on_exchange': bool(
                            float(pos.get('stopLoss', 0) or 0) > 0 and float(pos.get('takeProfit', 0) or 0) > 0
                        ),
                        'timestamp_open': datetime.now().isoformat()
                    }
        
    def _on_price_ready(self, price: float):
        """Вызывается когда цена готова"""
        self.order_panel.set_price(price)

    def _get_position_meta(self, symbol: str) -> dict:
        """Возвращает локальные метаданные позиции (стратегия/причина открытия)."""
        if not hasattr(self, "_tracked_positions"):
            return {}
        data = self._tracked_positions.get(symbol)
        if data:
            return data
        key = self._symbol_key(symbol)
        if not key:
            return {}
        for sym, meta in self._tracked_positions.items():
            if self._symbol_key(sym) == key:
                return meta
        return {}
            
    def _update_positions(self, positions: list):
        # Clear old
        for row in self.position_rows:
            row.deleteLater()
        self.position_rows.clear()
        
        self.positions = positions
        self.pos_count.setText(str(len(positions)))
        
        if not positions:
            self.no_pos_lbl.show()
        else:
            self.no_pos_lbl.hide()
            
            for pos in positions:
                meta = self._get_position_meta(pos.get('symbol') or '')
                row = PositionRow()
                row.update_data(
                    pos.get('symbol') or '',
                    (pos.get('side') or '').lower(),
                    float(pos.get('contracts') or 0),
                    float(pos.get('entryPrice') or 0),
                    float(pos.get('markPrice') or 0),
                    float(pos.get('unrealizedPnl') or 0),
                    float(pos.get('percentage') or 0),
                    int(pos.get('leverage') or 1),
                    str(meta.get('strategy') or ''),
                    str(meta.get('open_reason') or ''),
                )
                row.close_clicked.connect(self._close_position)
                self.positions_layout.insertWidget(self.positions_layout.count() - 1, row)
                self.position_rows.append(row)
                
    def _set_leverage_safe(self, leverage: int, symbol: str):
        """Установить плечо, игнорируя ошибку если уже установлено"""
        self._ensure_bybit_unified_workaround()
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            # Игнорируем ошибку "leverage not modified" - плечо уже установлено
            err = str(e).lower()
            if ("110043" in err) or ("not modified" in err):
                return
            # Ignore Bybit permission check endpoint errors and continue with current leverage.
            if ("query-api" in err) or ("retcode':10005" in err) or ('retcode":10005' in err):
                self._log("⚠️ Не удалось изменить плечо (10005), продолжаю с текущим плечом аккаунта")
                return
            if "10005" in err and "permission denied" in err:
                self._log("⚠️ API ограничивает проверку account permissions, ордер отправляю без смены плеча")
                return
            if "110043" not in str(e) and "not modified" not in str(e).lower():
                raise e

    def _ensure_bybit_unified_workaround(self):
        """Apply Bybit UTA flags to avoid query-api permission check in some API keys."""
        if not self.exchange or getattr(self.exchange, "id", "") != "bybit":
            return
        self.exchange.options["enableUnifiedAccount"] = True
        self.exchange.options["enableUnifiedMargin"] = False
        self.exchange.options["unifiedMarginStatus"] = 6
        self.exchange.is_unified_enabled = (lambda params={}: [False, True])

    def _is_bybit_demo_exchange(self) -> bool:
        if not self.exchange or getattr(self.exchange, "id", "") != "bybit":
            return False
        try:
            from core.config import config
            return str(config.data.get("exchange", "")) == "BYBIT_DEMO"
        except Exception:
            return False

    @staticmethod
    def _symbol_key(symbol: str) -> str:
        s = (symbol or "").upper().strip()
        if not s:
            return ""
        if "/" in s:
            return s.split("/")[0]
        if ":" in s:
            s = s.split(":")[0]
        for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
            if s.endswith(quote) and len(s) > len(quote):
                return s[:-len(quote)]
        return s

    def _get_open_position_keys(self) -> set:
        keys = set()
        if not self.exchange:
            return keys
        try:
            positions = self.exchange.fetch_positions()
            for pos in positions:
                if float(pos.get('contracts') or 0) <= 0:
                    continue
                key = self._symbol_key(pos.get('symbol') or "")
                if key:
                    keys.add(key)
        except Exception:
            pass
        return keys

    def _normalize_strategy_lockset(self, strategy_id: str) -> set:
        raw = self._strategy_symbol_locks.setdefault(strategy_id, set())
        normalized = {self._symbol_key(x) for x in raw if self._symbol_key(x)}
        self._strategy_symbol_locks[strategy_id] = normalized
        return normalized

    @staticmethod
    def _calc_atr_from_ohlcv(ohlcv: list, period: int = 14) -> float:
        if not ohlcv or len(ohlcv) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(ohlcv)):
            high = float(ohlcv[i][2])
            low = float(ohlcv[i][3])
            prev_close = float(ohlcv[i - 1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        if not trs:
            return 0.0
        return sum(trs[-period:]) / min(period, len(trs))

    @staticmethod
    def _calc_ema_series(values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        multiplier = 2 / (period + 1)
        out = [sum(values[:period]) / period]
        for v in values[period:]:
            out.append((v - out[-1]) * multiplier + out[-1])
        return out

    def _estimate_professional_sl_tp_pct(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        timeframe: str = "1h",
    ) -> tuple[float, float, str]:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=90)
            if not ohlcv or len(ohlcv) < 30:
                return 1.0, 2.2, "fallback"

            closes = [float(x[4]) for x in ohlcv]
            atr = self._calc_atr_from_ohlcv(ohlcv, 14)
            atr_pct = (atr / entry_price) * 100.0 if entry_price > 0 else 0.0

            ema20 = self._calc_ema_series(closes, 20)
            ema50 = self._calc_ema_series(closes, 50)
            trend_gap_pct = 0.0
            if ema20 and ema50 and entry_price > 0:
                trend_gap_pct = abs(ema20[-1] - ema50[-1]) / entry_price * 100.0

            if atr_pct < 0.65:
                vol_state = "low-vol"
                sl_mult = 1.45
            elif atr_pct > 1.70:
                vol_state = "high-vol"
                sl_mult = 1.05
            else:
                vol_state = "normal-vol"
                sl_mult = 1.25

            if trend_gap_pct >= 0.90:
                rr = 3.0
            elif trend_gap_pct >= 0.45:
                rr = 2.4
            else:
                rr = 1.9

            if vol_state == "high-vol":
                rr -= 0.25
            elif vol_state == "low-vol":
                rr += 0.20
            rr = max(1.6, min(rr, 3.2))

            sl_pct = max(0.45, min(atr_pct * sl_mult, 2.8))
            tp_pct = max(1.0, min(sl_pct * rr, 7.5))
            model = f"{vol_state}, gap={trend_gap_pct:.2f}%, RR=1:{rr:.2f}"
            return sl_pct, tp_pct, model
        except Exception:
            return 1.0, 2.2, "fallback"

    def _refine_sl_tp_prices(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        timeframe: str = "1h",
    ) -> tuple[float, float, str]:
        side = (side or "").lower()
        market_sl_pct, market_tp_pct, model = self._estimate_professional_sl_tp_pct(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            timeframe=timeframe,
        )

        strategy_sl_pct = 0.0
        strategy_tp_pct = 0.0
        if entry_price > 0 and sl_price > 0 and tp_price > 0:
            strategy_sl_pct = abs(entry_price - float(sl_price)) / entry_price * 100.0
            strategy_tp_pct = abs(float(tp_price) - entry_price) / entry_price * 100.0

        if strategy_sl_pct > 0.05 and strategy_tp_pct > 0.10:
            sl_pct = market_sl_pct * 0.55 + strategy_sl_pct * 0.45
            tp_pct = market_tp_pct * 0.55 + strategy_tp_pct * 0.45
            src = "blend(strategy+market)"
        else:
            sl_pct = market_sl_pct
            tp_pct = market_tp_pct
            src = "market-only"

        # Базовый контроль RR как у риск-менеджмента проп-команд.
        rr_now = tp_pct / max(sl_pct, 1e-9)
        if rr_now < 1.6:
            tp_pct = sl_pct * 1.6
        elif rr_now > 3.5:
            tp_pct = sl_pct * 3.5

        sl_pct = max(0.45, min(sl_pct, 3.0))
        tp_pct = max(1.0, min(tp_pct, 8.0))

        if side == "buy":
            refined_sl = entry_price * (1 - sl_pct / 100.0)
            refined_tp = entry_price * (1 + tp_pct / 100.0)
        else:
            refined_sl = entry_price * (1 + sl_pct / 100.0)
            refined_tp = entry_price * (1 - tp_pct / 100.0)

        return round(refined_sl, 2), round(refined_tp, 2), f"{src}; {model}"

    def _ensure_exchange_sltp(self, symbol: str, sl_price: float, tp_price: float) -> bool:
        """Гарантированно пытается поставить SL/TP на бирже для уже открытой позиции."""
        try:
            _call_set_trading_stop(
                self.exchange,
                symbol,
                stop_loss=float(sl_price),
                take_profit=float(tp_price),
            )
            return True
        except Exception as e:
            self._log(f"❌ {symbol}: не удалось выставить SL/TP на бирже ({e})")
            return False

    def _emergency_close_unprotected(self, symbol: str, side: str, size_hint: float):
        """Экстренно закрывает позицию, если защиту SL/TP поставить не удалось."""
        try:
            qty = max(0.0, float(size_hint or 0))
            if qty <= 0:
                positions = self.exchange.fetch_positions([symbol])
                for p in positions or []:
                    contracts = float(p.get('contracts') or 0)
                    if contracts > 0:
                        qty = contracts
                        break
            if qty <= 0:
                return

            if side == "buy":
                self.exchange.create_market_sell_order(symbol, qty, {"reduceOnly": True})
            else:
                self.exchange.create_market_buy_order(symbol, qty, {"reduceOnly": True})
            self._log(f"🛑 {symbol}: позиция закрыта, так как SL/TP не установились")
        except Exception as e:
            self._log(f"❌ {symbol}: аварийное закрытие не удалось ({e})")

    def _open_order_strict_sltp(
        self,
        symbol: str,
        side: str,
        size: float,
        sl_price: float,
        tp_price: float,
        source: str,
    ) -> bool:
        """
        Строгое открытие: позиция может остаться открытой только если SL/TP установлены на бирже.
        """
        params = {
            'stopLoss': {'type': 'market', 'triggerPrice': round(float(sl_price), 2)},
            'takeProfit': {'type': 'market', 'triggerPrice': round(float(tp_price), 2)},
        }
        opened = False
        try:
            if side == "buy":
                self.exchange.create_market_buy_order(symbol, size, params)
            else:
                self.exchange.create_market_sell_order(symbol, size, params)
            opened = True
        except Exception as e:
            err = str(e).lower()
            if (
                "stoploss" in err
                or "takeprofit" in err
                or "sl" in err
                or "tp" in err
                or "permission denied" in err
                or "10005" in err
            ):
                self._log(f"⚠️ {source}: биржа не приняла SL/TP в ордере, пробую отдельно через set_trading_stop...")
                if side == "buy":
                    self.exchange.create_market_buy_order(symbol, size)
                else:
                    self.exchange.create_market_sell_order(symbol, size)
                opened = True
            else:
                raise

        if not opened:
            return False

        protected = self._ensure_exchange_sltp(symbol, sl_price, tp_price)
        if not protected:
            self._emergency_close_unprotected(symbol, side, size)
            return False
        return True
                
    def _submit_order(self, symbol: str, side: str, position_usdt: float, sl_pct: float, tp_pct: float, leverage: int):
        """
        Создаёт ордер с SL/TP на бирже.
        position_usdt - размер позиции в USDT (НЕ маржа!)
        Маржа = position_usdt / leverage
        
        Комбинированная защита:
        1. SL/TP ордера на бирже — жёсткий стоп и тейк
        2. Автозакрытие по сигналу — если индикаторы развернулись (в AutoTradeWorker)
        """
        if not self.exchange:
            return
            
        try:
            self._ensure_bybit_unified_workaround()
            # Set leverage
            self._set_leverage_safe(leverage, symbol)
            
            # Get current price
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # Расчёт как на Bybit:
            # position_usdt = размер позиции в долларах
            # margin = position_usdt / leverage (сколько спишется с баланса)
            # qty = position_usdt / price (сколько монет купим)
            
            margin = position_usdt / leverage
            qty = position_usdt / price
            
            # Округляем количество
            coin = symbol.split('/')[0]
            if coin == "BTC":
                qty = round(qty, 3)
            elif coin == "ETH":
                qty = round(qty, 2)
            elif coin in ["SOL"]:
                qty = round(qty, 1)
            else:
                qty = round(qty, 0)  # XRP, DOGE - целые числа
            
            self._log("────────────────────────────")
            self._log(f"📊 {'ЛОНГ 📈' if side == 'buy' else 'ШОРТ 📉'} {coin}")
            self._log(f"   Позиция: ${position_usdt:,.0f}")
            self._log(f"   Маржа: ${margin:,.0f} (плечо {leverage}x)")
            self._log(f"   Кол-во: {qty} {coin} @ ${price:,.2f}")
            
            # Профессиональный пересчёт SL/TP (адаптация к волатильности/тренду)
            requested_sl_pct = float(sl_pct)
            requested_tp_pct = float(tp_pct)
            if side == "buy":
                requested_sl_price = price * (1 - requested_sl_pct / 100)
                requested_tp_price = price * (1 + requested_tp_pct / 100)
            else:
                requested_sl_price = price * (1 + requested_sl_pct / 100)
                requested_tp_price = price * (1 - requested_tp_pct / 100)
            strategy_tf = self._auto_tf_cached or "1h"
            sl_price, tp_price, sltp_model = self._refine_sl_tp_prices(
                symbol=symbol,
                side=side,
                entry_price=float(price),
                sl_price=float(requested_sl_price),
                tp_price=float(requested_tp_price),
                timeframe=strategy_tf,
            )
            actual_sl_pct = (abs(float(price) - float(sl_price)) / float(price) * 100.0) if price > 0 else 0.0
            actual_tp_pct = (abs(float(tp_price) - float(price)) / float(price) * 100.0) if price > 0 else 0.0
            self._log(f"   🧠 SL/TP модель: {sltp_model}")
            self._log(f"   🛡️ SL: ${sl_price:,.2f} ({actual_sl_pct:.2f}%)")
            self._log(f"   🎯 TP: ${tp_price:,.2f} ({actual_tp_pct:.2f}%)")

            sl_tp_set = self._open_order_strict_sltp(
                symbol=symbol,
                side=side,
                size=qty,
                sl_price=sl_price,
                tp_price=tp_price,
                source="Ручной ордер",
            )
            if not sl_tp_set:
                raise RuntimeError("SL/TP не установлены — ордер отклонён строгим режимом")
            self._log("✅ Ордер исполнен! SL/TP установлены")

            if not hasattr(self, '_tracked_positions'):
                self._tracked_positions = {}
            self._tracked_positions[symbol] = {
                'entry_price': float(price),
                'side': "long" if side == "buy" else "short",
                'size': float(qty),
                'leverage': int(leverage),
                'strategy': 'Manual',
                'open_reason': 'Ручной вход',
                'risk_model': sltp_model,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'sl_tp_on_exchange': True,
                'timestamp_open': datetime.now().isoformat()
            }
            
            # Add to history
            self.history_table.add_trade(
                datetime.now().strftime("%H:%M:%S"),
                coin,
                side,
                qty,
                price,
                0
            )
            
            self._last_stop_sync_ts = 0.0
            self._refresh_data()
            
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")
            QMessageBox.critical(self, "Ошибка ордера", str(e))
            
    def _close_position(self, symbol: str):
        if not self.exchange:
            return
            
        for pos in self.positions:
            if pos.get('symbol') == symbol:
                self._close_position_by_rules(pos, close_reason="Manual", notes="Закрыто пользователем")
                break
    
    def _add_to_journal(self, symbol: str, side: str, strategy: str, 
                        entry_price: float, exit_price: float, size: float,
                        leverage: int, pnl_usd: float, close_reason: str,
                        sl_price: float = 0, tp_price: float = 0,
                        timestamp_open: str = None, notes: str = ""):
        """Добавляет сделку в журнал"""
        from ui.trade_journal import Trade, get_journal
        import uuid
        
        # Рассчитываем PnL %
        if entry_price > 0 and size > 0:
            margin = (size * entry_price) / leverage
            pnl_pct = (pnl_usd / margin) * 100 if margin > 0 else 0
        else:
            pnl_pct = 0
        
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            timestamp_open=timestamp_open or datetime.now().isoformat(),
            timestamp_close=datetime.now().isoformat(),
            symbol=symbol,
            side=side,
            strategy=strategy,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            leverage=leverage,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            fees=0,  # TODO: получить комиссии
            sl_price=sl_price,
            tp_price=tp_price,
            close_reason=close_reason,
            notes=notes
        )
        
        journal = get_journal()
        journal.add_trade(trade)
        
        # Обновляем виджет журнала
        if hasattr(self, 'journal_widget'):
            self.journal_widget._refresh()
                
    def _toggle_auto_trade(self):
        self.auto_trading = not self.auto_trading
        self.auto_panel.set_running(self.auto_trading)
        
        # Сохраняем настройки
        self._save_auto_settings()
        
        if self.auto_trading:
            # Интервал проверки зависит от таймфрейма
            tf = self.auto_panel.tf_combo.currentData() or "1h"
            interval_map = {
                "1m": 60000,      # 1 минута
                "5m": 300000,     # 5 минут
                "15m": 900000,    # 15 минут
                "1h": 1800000,    # 30 минут (проверяем 2 раза за свечу)
                "4h": 3600000,    # 1 час
                "1d": 14400000,   # 4 часа
            }
            interval = interval_map.get(tf, 1800000)
            interval_min = interval // 60000
            
            self._log(f"🤖 Автоторговля запущена | ТФ: {tf} | Проверка каждые {interval_min} мин")
            
            if not hasattr(self, 'auto_timer'):
                self.auto_timer = QTimer()
                self.auto_timer.timeout.connect(self._run_auto_worker)
            self.auto_timer.start(interval)
            # Сразу проверяем
            QTimer.singleShot(1000, self._run_auto_worker)
        else:
            self._log("🤖 Автоторговля остановлена")
            if hasattr(self, 'auto_timer'):
                self.auto_timer.stop()
            if hasattr(self, 'auto_worker') and self.auto_worker.isRunning():
                self.auto_worker.stop()
    
    def _save_auto_settings(self):
        """Сохраняет настройки автоторговли"""
        self.settings.setValue("auto_trading", "true" if self.auto_trading else "false")
        self.settings.setValue("auto_leverage", self.auto_panel.auto_leverage.value())
        self.settings.setValue("auto_risk", self.auto_panel.risk_spin.value())
        self.settings.setValue("auto_tf", self.auto_panel.tf_combo.currentData())
        
        # Сохраняем выбранные монеты
        selected = [coin for coin, cb in self.auto_panel.coin_checks.items() if cb.isChecked()]
        self.settings.setValue("auto_coins", ",".join(selected))
    
    def _save_multi_settings(self, enabled: bool):
        selected_strategies = self.strategy_panel.get_selected_strategies()
        selected_coins = self.strategy_panel.get_selected_coins()
        self.settings.setValue("multi_enabled", "true" if enabled else "false")
        self.settings.setValue("multi_strategies", ",".join(selected_strategies))
        self.settings.setValue("multi_coins", ",".join(selected_coins))
        self.settings.setValue("multi_risk", float(self.strategy_panel.get_risk_pct()))
        self.settings.setValue("multi_leverage", int(self.strategy_panel.get_leverage()))
    
    def _load_multi_settings(self):
        risk = self.settings.value("multi_risk", 2.0, type=float)
        leverage = self.settings.value("multi_leverage", 5, type=int)
        self.strategy_panel.risk_spin.setValue(risk)
        self.strategy_panel.leverage_spin.setValue(leverage)
        
        saved_coins = self.settings.value("multi_coins", "BTC,ETH,SOL,XRP,DOGE,ADA,AVAX,LINK")
        coin_set = set(saved_coins.split(",")) if saved_coins else set()
        for coin, cb in self.strategy_panel.coin_checks.items():
            cb.setChecked(coin in coin_set)
        
        saved_strategies = self.settings.value("multi_strategies", "")
        strat_set = set(saved_strategies.split(",")) if saved_strategies else set()
        for sid, card in self.strategy_panel.strategy_cards.items():
            card.set_enabled(sid in strat_set)
    
    def _restore_multi_strategies(self):
        if not self.exchange:
            return
        self._load_multi_settings()
        if not self.strategy_panel.get_selected_strategies():
            return
        self._start_multi_strategies()
    
    def _get_strategy_interval_ms(self, tf: str) -> int:
        interval_map = {
            "15m": 300000,
            "1h": 1800000,
            "4h": 3600000,
            "1d": 14400000,
        }
        return interval_map.get(tf, 1800000)
    
    def _strategy_watchdog_tick(self):
        if not self.exchange:
            return
        if not hasattr(self, "strategy_manager") or not self.strategy_manager.active_strategies:
            return
        if not hasattr(self, "strategy_timers"):
            self.strategy_timers = {}
        
        for strategy_id, cfg in list(self.strategy_manager.active_strategies.items()):
            tf = cfg.get("timeframe", "1h")
            interval = self._get_strategy_interval_ms(tf)
            timer = self.strategy_timers.get(strategy_id)
            if timer is None or not timer.isActive():
                t = QTimer()
                t.timeout.connect(lambda sid=strategy_id: self._run_strategy_check(sid))
                t.start(interval)
                self.strategy_timers[strategy_id] = t
                self._log(f"♻️ Watchdog восстановил таймер стратегии: {strategy_id}")
            self._run_strategy_check(strategy_id)
        
    def _load_auto_settings(self):
        """Загружает настройки автоторговли"""
        # Плечо
        leverage = self.settings.value("auto_leverage", 5, type=int)
        self.auto_panel.auto_leverage.setValue(leverage)
        
        # Риск
        risk = self.settings.value("auto_risk", 2.0, type=float)
        self.auto_panel.risk_spin.setValue(risk)
        
        # Таймфрейм
        tf = self.settings.value("auto_tf", "1h")
        idx = self.auto_panel.tf_combo.findData(tf)
        if idx >= 0:
            self.auto_panel.tf_combo.setCurrentIndex(idx)
        self._auto_tf_cached = tf
        
        # Монеты
        coins_str = self.settings.value("auto_coins", "BTC,ETH,SOL,XRP,DOGE")
        selected_coins = coins_str.split(",") if coins_str else []
        for coin, cb in self.auto_panel.coin_checks.items():
            cb.setChecked(coin in selected_coins)
                
    def _run_auto_worker(self):
        """Запускает воркер автоторговли в отдельном потоке"""
        if not self.auto_trading or not self.exchange:
            return
            
        # Если предыдущий воркер ещё работает - пропускаем
        if hasattr(self, 'auto_worker') and self.auto_worker.isRunning():
            return
        
        # Собираем настройки из UI в главном потоке
        settings = {
            'leverage': self.auto_panel.auto_leverage.value(),
            'risk_pct': self.auto_panel.risk_spin.value(),
            'tf': self.auto_panel.tf_combo.currentData() or "1m",
            'selected_coins': [coin for coin, cb in self.auto_panel.coin_checks.items() if cb.isChecked()],
            'max_positions': 0,
            'min_confluence': 3,
            'entry_cooldown_sec': 20 * 60,
            'auto_owned_symbols': list(self._auto_owned_symbols),
            'close_on_strong_opposite': True,
            'opposite_min_confluence': 3,
            'opposite_confirmations': 2,
            'max_spread_pct': 0.12,
            'min_quote_volume': 3_000_000,
            'max_drawdown_pct': 6.0,
            'hard_stop_pct': 10.0,
            'risk_pause_minutes': 60,
        }
        self._auto_tf_cached = settings['tf']
            
        self.auto_worker = AutoTradeWorker(
            self.exchange,
            settings,
            self._get_confluence_signal,
            self._get_htf_trend
        )
        self.auto_worker.log_signal.connect(self._log)
        self.auto_worker.profit_signal.connect(self._show_profit)
        self.auto_worker.refresh_signal.connect(self._refresh_data)
        self.auto_worker.open_position_signal.connect(self._auto_open_position)
        self.auto_worker.journal_signal.connect(self._on_journal_entry)
        self.auto_worker.start()
    
    def _on_journal_entry(self, data: dict):
        """Обработка записи в журнал из воркера"""
        self._add_to_journal(**data)
                
    def _get_indicator_source(self) -> str:
        """Source used by indicator wrappers inside terminal."""
        from core.config import config
        exchange_type = str(config.data.get("exchange", "BYBIT_DEMO"))
        return "BYBIT_DEMO" if exchange_type == "BYBIT_DEMO" else "BYBIT_PERP"

    def _get_htf_trend(self, coin: str, tf: str) -> str:
        """Получает тренд на старшем таймфрейме для фильтрации"""
        cache_key = f"{coin}:{tf}"
        now = time.time()
        with self._cache_lock:
            cached = self._htf_cache.get(cache_key)
        if cached and (now - cached[0]) < self._htf_cache_ttl_sec:
            return cached[1]

        # Маппинг на старший ТФ
        htf_map = {
            "1m": "15m",
            "5m": "1h", 
            "15m": "4h",
            "1h": "4h",
            "4h": "1d",
            "1d": "1w",
        }
        htf = htf_map.get(tf, "4h")
        
        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            
            symbol = f"{coin}USDT.P"
            res = ema_get_signal(symbol, htf, self._get_indicator_source())
            
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                trend = str(res[0])
            else:
                trend = "neutral"
            with self._cache_lock:
                self._htf_cache[cache_key] = (now, trend)
            return trend
        except:
            return "neutral"
            
    def _get_confluence_signal(self, coin: str) -> tuple:
        """
        Получает торговый сигнал по конфлюенс стратегии (3 индикатора).
        Возвращает: (signal, strength, details)
        - signal: "buy", "sell", "none"
        - strength: 0-3 (сколько индикаторов согласны)
        - details: строка с деталями
        """
        tf = self._auto_tf_cached or "1m"
        source = self._get_indicator_source()
        cache_key = f"{coin}:{tf}:{source}"
        now = time.time()
        with self._cache_lock:
            cached = self._signal_cache.get(cache_key)
        if cached and (now - cached[0]) < self._signal_cache_ttl_sec:
            return cached[1]

        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            from indicators.algoalpha_smart_money_breakout import get_signal as sm_get_signal
            from indicators.algoalpha_trend_targets import get_signal as tt_get_signal
        except ImportError:
            return "none", 0, "Индикаторы не найдены"
            
        symbol = f"{coin}USDT.P"
        
        results = {}
        
        # EMA Market Structure
        try:
            res = ema_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["EMA"] = str(res[0])
            else:
                results["EMA"] = "neutral"
        except:
            results["EMA"] = "neutral"
            
        # Smart Money Breakout
        try:
            res = sm_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["SM"] = str(res[0])
            else:
                results["SM"] = "neutral"
        except:
            results["SM"] = "neutral"
            
        # Trend Targets
        try:
            res = tt_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["Trend"] = str(res[0])
            else:
                results["Trend"] = "neutral"
        except:
            results["Trend"] = "neutral"
            
        # Считаем конфлюенс
        bulls = sum(1 for v in results.values() if v == "bull")
        bears = sum(1 for v in results.values() if v == "bear")
        
        # Формируем детали
        emoji_map = {"bull": "🟢", "bear": "🔴", "neutral": "⚪"}
        details = " | ".join([f"{emoji_map.get(v, '⚪')}{k}" for k, v in results.items()])
        
        if bulls >= 2 and bulls > bears:
            out = ("buy", bulls, details)
        elif bears >= 2 and bears > bulls:
            out = ("sell", bears, details)
        else:
            out = ("none", 0, details)

        with self._cache_lock:
            self._signal_cache[cache_key] = (now, out)
        return out
            
    def _calc_ema(self, data: list, period: int) -> list:
        """Рассчитывает EMA"""
        ema = []
        multiplier = 2 / (period + 1)
        
        # Первое значение = SMA
        sma = sum(data[:period]) / period
        ema.append(sma)
        
        for price in data[period:]:
            ema_val = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)
            
        return ema
        
    def _auto_open_position(self, symbol: str, side: str, size: float, sl_pct: float, tp_pct: float, leverage: int):
        """
        Открывает позицию автоматически с SL/TP на бирже.
        
        Комбинированная защита:
        1. SL/TP ордера на бирже — жёсткий стоп и тейк
        2. Автозакрытие по сигналу — если индикаторы развернулись (в AutoTradeWorker)
        """
        try:
            self._ensure_bybit_unified_workaround()
            # Устанавливаем плечо
            self._set_leverage_safe(leverage, symbol)
            
            # Получаем цену
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # Профессиональный пересчёт SL/TP (адаптация к волатильности/тренду)
            requested_sl_pct = float(sl_pct)
            requested_tp_pct = float(tp_pct)
            if side == "buy":
                requested_sl_price = price * (1 - requested_sl_pct / 100)
                requested_tp_price = price * (1 + requested_tp_pct / 100)
            else:
                requested_sl_price = price * (1 + requested_sl_pct / 100)
                requested_tp_price = price * (1 - requested_tp_pct / 100)
            strategy_tf = self._auto_tf_cached or "1h"
            sl_price, tp_price, sltp_model = self._refine_sl_tp_prices(
                symbol=symbol,
                side=side,
                entry_price=float(price),
                sl_price=float(requested_sl_price),
                tp_price=float(requested_tp_price),
                timeframe=strategy_tf,
            )
            
            sl_tp_set = self._open_order_strict_sltp(
                symbol=symbol,
                side=side,
                size=size,
                sl_price=sl_price,
                tp_price=tp_price,
                source="Авто-ордер",
            )
            if not sl_tp_set:
                raise RuntimeError("SL/TP не установлены — авто-вход отклонён строгим режимом")
                
            coin = symbol.split('/')[0]
            self._log(f"✅ АВТО {'ЛОНГ' if side == 'buy' else 'ШОРТ'} {size} {coin} @ ${price:,.2f}")
            self._log(f"   🧠 SL/TP модель: {sltp_model}")
            self._log(f"   🛡️ SL: ${sl_price:,.2f} | 🎯 TP: ${tp_price:,.2f}")
            
            self._auto_owned_symbols.add(symbol)
            if not hasattr(self, '_tracked_positions'):
                self._tracked_positions = {}
            self._tracked_positions[symbol] = {
                'entry_price': float(price),
                'side': "long" if side == "buy" else "short",
                'size': float(size),
                'leverage': int(leverage),
                'strategy': 'AutoTrade',
                'open_reason': 'EMA + Smart Money + Trend (конфлюенс)',
                'risk_model': sltp_model,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'sl_tp_on_exchange': True,
                'timestamp_open': datetime.now().isoformat()
            }
            
            # Добавляем в историю
            self.history_table.add_trade(
                datetime.now().strftime("%H:%M:%S"),
                coin,
                side,
                size,
                price,
                0
            )
            
            self._last_stop_sync_ts = 0.0
            self._refresh_data()
            
        except Exception as e:
            self._log(f"❌ Ошибка авто-ордера: {e}")

    # ==================== МУЛЬТИ-СТРАТЕГИИ ====================
    
    def _load_strategies(self):
        """Загружает список стратегий в панель"""
        try:
            from strategies.manager import get_all_strategies
            strategies = get_all_strategies()
            self.strategy_panel.load_strategies(strategies)
        except Exception as e:
            self._log(f"⚠️ Ошибка загрузки стратегий: {e}")
            
    def _start_multi_strategies(self):
        """Запускает выбранные стратегии"""
        if not self.exchange:
            self._log("❌ Сначала подключитесь к API")
            return
        
        if hasattr(self, "strategy_manager") and self.strategy_manager.active_strategies:
            self._log("⚠️ Мульти-стратегии уже запущены")
            return
            
        selected = self.strategy_panel.get_selected_strategies()
        if not selected:
            self._log("⚠️ Выберите хотя бы одну стратегию")
            return
            
        coins = self.strategy_panel.get_selected_coins()
        if not coins:
            self._log("⚠️ Выберите хотя бы одну монету")
            return
            
        risk_pct = max(0.5, min(float(self.strategy_panel.get_risk_pct()), 5.0))
        leverage = max(5, min(int(self.strategy_panel.get_leverage()), 10))
        
        # Создаём менеджер если нет
        if not hasattr(self, 'strategy_manager'):
            from strategies.manager import MultiStrategyManager
            self.strategy_manager = MultiStrategyManager(self.exchange)
            
        # Запускаем таймеры для каждой стратегии
        if not hasattr(self, 'strategy_timers'):
            self.strategy_timers = {}
            
        from strategies.manager import STRATEGIES
        
        for idx, strategy_id in enumerate(selected):
            if strategy_id not in self._strategy_symbol_locks:
                self._strategy_symbol_locks[strategy_id] = set()
            # Получаем таймфрейм стратегии
            strategy_cls = STRATEGIES.get(strategy_id)
            if not strategy_cls:
                continue
                
            instance = strategy_cls(self.exchange)
            tf = instance.config.timeframe
            
            # Интервал проверки
            interval_map = {
                "15m": 300000,    # 5 минут
                "1h": 1800000,    # 30 минут
                "4h": 3600000,    # 1 час
                "1d": 14400000,   # 4 часа
            }
            interval = interval_map.get(tf, 1800000)
            
            # Создаём таймер
            timer = QTimer()
            timer.timeout.connect(lambda sid=strategy_id: self._run_strategy_check(sid))
            stagger_ms = min(idx * 1200, 5000)
            timer.start(interval + stagger_ms)
            self.strategy_timers[strategy_id] = timer
            
            # Сохраняем настройки
            self.strategy_manager.active_strategies[strategy_id] = {
                "coins": coins,
                "risk_pct": risk_pct,
                "leverage": leverage,
                "timeframe": tf
            }
            
            self._log(f"🎯 Запущена стратегия: {instance.config.name}")
            
        # Сразу проверяем
        for idx, strategy_id in enumerate(selected):
            QTimer.singleShot(1000 + idx * 350, lambda sid=strategy_id: self._run_strategy_check(sid))
            
        self.strategy_panel.set_running(True)
        self._save_multi_settings(True)
        self._log(f"🚀 Запущено {len(selected)} стратегий | Риск: {risk_pct}% | Плечо: {leverage}x")
        
    def _stop_multi_strategies(self):
        """Останавливает все стратегии"""
        if hasattr(self, 'strategy_timers'):
            for timer in self.strategy_timers.values():
                timer.stop()
            self.strategy_timers.clear()
        
        # Останавливаем воркеры
        if hasattr(self, 'strategy_workers'):
            for worker in self.strategy_workers.values():
                if worker.isRunning():
                    worker.stop()
                    worker.wait(1000)
            self.strategy_workers.clear()
            
        if hasattr(self, 'strategy_manager'):
            self.strategy_manager.active_strategies.clear()
        
        self._strategy_symbol_locks.clear()
            
        self.strategy_panel.set_running(False)
        self._save_multi_settings(False)
        self._log("⏹ Все стратегии остановлены")
        
    def _run_strategy_check(self, strategy_id: str):
        """Запускает проверку для одной стратегии"""
        if not hasattr(self, 'strategy_manager'):
            return
            
        if strategy_id not in self.strategy_manager.active_strategies:
            return
        
        # Храним воркеры чтобы они не удалялись
        if not hasattr(self, 'strategy_workers'):
            self.strategy_workers = {}
            
        # Если предыдущий воркер ещё работает — пропускаем
        if strategy_id in self.strategy_workers:
            old_worker = self.strategy_workers[strategy_id]
            if old_worker.isRunning():
                return
            
        config = self.strategy_manager.active_strategies[strategy_id]
        
        # Создаём воркер
        from strategies.manager import StrategyWorker
        
        worker = StrategyWorker(
            self.exchange,
            strategy_id,
            config['coins'],
            config['risk_pct'],
            config['leverage']
        )
        worker.log_signal.connect(self._on_strategy_log)
        worker.trade_signal.connect(self._on_strategy_trade)
        worker.close_signal.connect(self._on_strategy_close)
        
        # Сохраняем ссылку
        self.strategy_workers[strategy_id] = worker
        worker.start()

    def _on_strategy_log(self, message: str, strategy_id: str):
        """Обработка лога от стратегии."""
        self._log(f"[{strategy_id}] {message}")

    def _on_strategy_trade(self, strategy_id: str, symbol: str, side: str, 
                           size: float, sl_price: float, tp_price: float, 
                           leverage: int, reason: str):
        """Обработка сигнала открытия от стратегии."""
        key = self._symbol_key(symbol)
        if key in self._inflight_symbol_keys:
            self._log(f"⏭️ [{strategy_id}] Пропуск {key}: ордер уже отправляется")
            return

        self._inflight_symbol_keys.add(key)
        try:
            coin = key or symbol.split('/')[0]
            self._ensure_bybit_unified_workaround()

            # Не доливаем существующую позицию по символу: Bybit объединяет входы в одну строку.
            open_keys = self._get_open_position_keys()
            if key and key in open_keys:
                self._log(
                    f"⏭️ [{strategy_id}] Пропуск {coin}: по монете уже есть открытая позиция "
                    f"(доливка отключена, чтобы не раздувать объем)"
                )
                return

            lockset = self._normalize_strategy_lockset(strategy_id)
            if key and key in lockset:
                self._log(f"⏭️ [{strategy_id}] Пропуск {coin}: у стратегии уже есть активная сделка")
                return

            self._set_leverage_safe(leverage, symbol)
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            strategy_tf = "1h"
            if hasattr(self, "strategy_manager") and self.strategy_manager:
                cfg = self.strategy_manager.active_strategies.get(strategy_id, {})
                strategy_tf = str(cfg.get("timeframe") or "1h")
            sl_price, tp_price, sltp_meta = self._refine_sl_tp_prices(
                symbol=symbol,
                side=side,
                entry_price=float(price),
                sl_price=float(sl_price or 0),
                tp_price=float(tp_price or 0),
                timeframe=strategy_tf,
            )

            sl_tp_ok = self._open_order_strict_sltp(
                symbol=symbol,
                side=side,
                size=size,
                sl_price=sl_price,
                tp_price=tp_price,
                source=f"Стратегия {strategy_id}",
            )
            if not sl_tp_ok:
                raise RuntimeError("SL/TP не установлены — вход стратегии отклонён строгим режимом")

            direction = "ЛОНГ" if side == "buy" else "ШОРТ"
            self._log(f"🎯 [{strategy_id}] {direction} {coin} @ ${price:,.2f}")
            self._log(f"   {reason}")
            self._log(f"   🧠 SL/TP модель: {sltp_meta}")
            self._log(f"   🛡️ SL: ${sl_price:,.2f} | 🎯 TP: ${tp_price:,.2f}")
            if not hasattr(self, '_tracked_positions'):
                self._tracked_positions = {}
            self._tracked_positions[symbol] = {
                'entry_price': float(price),
                'side': "long" if side == "buy" else "short",
                'size': float(size),
                'leverage': int(leverage),
                'strategy': strategy_id,
                'open_reason': reason or 'Сигнал стратегии',
                'risk_model': sltp_meta,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'sl_tp_on_exchange': True,
                'timestamp_open': datetime.now().isoformat()
            }
            if key:
                lockset.add(key)
            self.history_table.add_trade(
                datetime.now().strftime("%H:%M:%S"),
                coin,
                side,
                size,
                price,
                0.0,
            )

            self._last_stop_sync_ts = 0.0
            self._refresh_data()

        except Exception as e:
            self._log(f"❌ [{strategy_id}] Ошибка: {e}")
        finally:
            if key:
                self._inflight_symbol_keys.discard(key)

    def _on_strategy_close(self, strategy_id: str, symbol: str, reason: str):
        """Обработка сигнала на закрытие от стратегии — ОТКЛЮЧЕНО"""
        # Стратегии НЕ закрывают позиции автоматически
        # Закрытие происходит только через SL/TP на бирже
        # Это предотвращает конфликты между стратегиями
        pass

    # ==================== GRID BOT ====================
    
    def _start_grid_bot(self, config: dict):
        """Запускает Grid бота"""
        if not self.exchange:
            self._log("❌ Сначала подключитесь к API")
            return
            
        try:
            from strategies.grid_bot import GridBot, GridConfig, GridMode
            
            # Создаём конфиг
            grid_config = GridConfig(
                symbol=config['symbol'],
                mode=GridMode.AI if config['mode'] == 'ai' else GridMode.MANUAL,
                upper_price=config['upper_price'],
                lower_price=config['lower_price'],
                grid_count=config['grid_count'],
                total_investment=config['investment'],
                leverage=config['leverage'],
            )
            
            # Создаём бота
            self.grid_bot = GridBot(self.exchange, grid_config)
            
            # Настраиваем сетку
            self._log(f"📊 Настройка Grid бота для {config['symbol']}...")
            
            if config['mode'] == 'ai':
                self._log("🤖 AI анализирует волатильность...")
                
            levels = self.grid_bot.setup_grid()
            self._log(f"📊 Создано {len(levels)} уровней сетки")
            
            if levels:
                self._log(f"   Диапазон: ${levels[0].price:,.2f} — ${levels[-1].price:,.2f}")
            
            # Размещаем ордера
            self._log("📝 Размещаю ордера...")
            orders = self.grid_bot.place_grid_orders()
            self._log(f"✅ Размещено {len(orders)} ордеров")
            
            # Запускаем таймер проверки
            self.grid_timer = QTimer()
            self.grid_timer.timeout.connect(self._check_grid_orders)
            self.grid_timer.start(10000)  # Каждые 10 сек
            
            self.grid_panel.set_running(True)
            self.grid_panel.update_stats(0, 0, len(orders), len(levels))
            self._update_monitor()
            
            self._log("🚀 Grid бот запущен!")
            
        except Exception as e:
            self._log(f"❌ Ошибка запуска Grid: {e}")
            
    def _stop_grid_bot(self):
        """Останавливает Grid бота"""
        if hasattr(self, 'grid_timer'):
            self.grid_timer.stop()
            
        if hasattr(self, 'grid_bot'):
            self._log("⏹ Отменяю ордера Grid...")
            self.grid_bot.cancel_all_orders()
            
            stats = self.grid_bot.get_stats()
            self._log(f"📊 Grid остановлен | Профит: ${stats['total_profit']:.2f} | Сделок: {stats['trades_count']}")
            
        self.grid_panel.set_running(False)
        self._update_monitor()
        self._log("⏹ Grid бот остановлен")
        
    def _check_grid_orders(self):
        """Проверяет и обновляет ордера Grid"""
        if not hasattr(self, 'grid_bot') or not self.grid_bot.is_running:
            return
            
        try:
            new_orders = self.grid_bot.check_and_replace_orders()
            
            if new_orders:
                self._log(f"🔄 Grid: {len(new_orders)} ордеров переставлено")
                
            # Обновляем статистику
            stats = self.grid_bot.get_stats()
            self.grid_panel.update_stats(
                stats['total_profit'],
                stats['trades_count'],
                stats['active_orders'],
                stats['grid_levels']
            )
            self._update_monitor()
            
        except Exception as e:
            self._log(f"⚠️ Grid ошибка: {e}")

    # ==================== SMART AI BOT ====================
    
    def _analyze_smart_ai(self, symbol: str):
        """Запускает анализ Smart AI"""
        if not self.exchange:
            self._log("❌ Сначала подключитесь к API")
            self.smart_ai_panel.analyze_btn.setText("🔍 Анализировать рынок")
            self.smart_ai_panel.analyze_btn.setEnabled(True)
            return
        
        # Защита от повторного запуска
        if hasattr(self, 'ai_worker') and self.ai_worker and self.ai_worker.isRunning():
            self._log("⚠️ Анализ уже запущен")
            return
            
        self._log(f"🧠 Smart AI анализирует {symbol}...")
        
        # Запускаем в отдельном потоке
        from PySide6.QtCore import QThread, Signal as QtSignal
        
        class AnalyzeWorker(QThread):
            result = QtSignal(object)
            
            def __init__(self, exchange, symbol):
                super().__init__()
                self.exchange = exchange
                self.symbol = symbol
                
            def run(self):
                try:
                    from strategies.smart_ai_bot import SmartAIBot
                    bot = SmartAIBot(self.exchange)
                    signal = bot.get_signal(self.symbol)
                    self.result.emit(signal)
                except Exception as e:
                    print(f"Smart AI error: {e}")
                    self.result.emit(None)
        
        self.ai_worker = AnalyzeWorker(self.exchange, symbol)
        self.ai_worker.result.connect(self._on_smart_ai_result)
        self.ai_worker.start()
        
    def _on_smart_ai_result(self, signal):
        """Обработка результата анализа"""
        self.smart_ai_panel.update_analysis(signal)
        
        if signal and signal.action != "wait":
            analysis = signal.analysis
            self._log(f"🧠 AI: {signal.action.upper()} | Confidence: {signal.confidence}%")
            self._log(f"   MTF: HTF={analysis.htf_trend} MTF={analysis.mtf_trend} LTF={analysis.ltf_trend}")
            self._log(f"   Bull: {analysis.bull_score} | Bear: {analysis.bear_score}")
            self._log(f"   Entry: ${signal.entry_price:,.2f} | SL: ${signal.stop_loss:,.2f}")
        else:
            self._log("🧠 AI: Ожидание лучшего момента")
            
    def _trade_smart_ai(self, config: dict):
        """Открывает сделку по сигналу Smart AI"""
        if not self.exchange:
            return
            
        signal = config['signal']
        symbol = config['symbol']
        side = config['side']
        leverage = config['leverage']
        
        try:
            self._ensure_bybit_unified_workaround()
            # Устанавливаем плечо
            self._set_leverage_safe(leverage, symbol)
            
            # Получаем баланс
            balance = self.exchange.fetch_balance()
            available = float(balance.get('USDT', {}).get('free') or 0)
            
            # Размер позиции
            position_usdt = available * (signal.position_size_pct / 100)
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            size = position_usdt / price
            coin = symbol.split('/')[0]
            if coin == "BTC":
                size = round(size, 3)
            elif coin in ["ETH", "SOL"]:
                size = round(size, 2)
            else:
                size = round(size, 1)
            
            sl_tp_ok = self._open_order_strict_sltp(
                symbol=symbol,
                side=side,
                size=size,
                sl_price=float(signal.stop_loss),
                tp_price=float(signal.take_profit_2),
                source="Smart AI",
            )
            if not sl_tp_ok:
                raise RuntimeError("SL/TP не установлены — Smart AI вход отклонён строгим режимом")
                
            direction = "ЛОНГ 📈" if side == "buy" else "ШОРТ 📉"
            self._log(f"🧠 Smart AI {direction} {coin} @ ${price:,.2f}")
            self._log(f"   Confidence: {signal.confidence}% | Size: {size}")
            self._log(f"   🛡️ SL: ${signal.stop_loss:,.2f} | 🎯 TP: ${signal.take_profit_2:,.2f}")

            if not hasattr(self, '_tracked_positions'):
                self._tracked_positions = {}
            self._tracked_positions[symbol] = {
                'entry_price': float(price),
                'side': "long" if side == "buy" else "short",
                'size': float(size),
                'leverage': int(leverage),
                'strategy': 'SmartAI',
                'open_reason': f"Smart AI signal ({signal.confidence}% confidence)",
                'risk_model': 'smart-ai-signal',
                'sl_price': float(signal.stop_loss),
                'tp_price': float(signal.take_profit_2),
                'sl_tp_on_exchange': True,
                'timestamp_open': datetime.now().isoformat()
            }
            
            self._last_stop_sync_ts = 0.0
            self._refresh_data()
            
        except Exception as e:
            self._log(f"❌ Smart AI ошибка: {e}")
    
    def _init_runtime_storage(self):
        if not os.path.exists(self.equity_file):
            with open(self.equity_file, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "available", "total", "unrealized_pnl", "open_positions"])
        if not os.path.exists(self.events_file):
            with open(self.events_file, "w", encoding="utf-8") as f:
                f.write("")

    def _append_event(self, event_type: str, payload: dict):
        try:
            row = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "payload": payload,
            }
            line = json.dumps(row, ensure_ascii=False)
            with self._io_lock:
                self._event_buffer.append(line)
                if len(self._event_buffer) > 2000:
                    self._event_buffer = self._event_buffer[-1200:]
        except Exception:
            pass
    
    def _record_equity_snapshot(self, available: float, total: float, pnl: float, open_positions: int):
        now = time.time()
        if (now - self._last_snapshot_ts) < 30:
            return
        self._last_snapshot_ts = now
        try:
            row = [
                datetime.now().isoformat(),
                f"{available:.8f}",
                f"{total:.8f}",
                f"{pnl:.8f}",
                str(open_positions),
            ]
            with self._io_lock:
                self._equity_buffer.append(row)
                if len(self._equity_buffer) > 200:
                    self._equity_buffer = self._equity_buffer[-120:]
        except Exception:
            pass

    def _flush_runtime_buffers(self):
        events = []
        equities = []
        try:
            with self._io_lock:
                if self._event_buffer:
                    events = self._event_buffer[:]
                    self._event_buffer.clear()
                if self._equity_buffer:
                    equities = self._equity_buffer[:]
                    self._equity_buffer.clear()
        except Exception:
            return

        if events:
            try:
                with open(self.events_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(events) + "\n")
            except Exception:
                pass
        if equities:
            try:
                with open(self.equity_file, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerows(equities)
            except Exception:
                pass
    
    def _export_runtime_data(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка для экспорта данных")
        if not folder:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            self._flush_runtime_buffers()
            from ui.trade_journal import get_journal
            journal = get_journal()
            journal.export_csv(os.path.join(folder, f"trades_{stamp}.csv"))
            journal.export_json(os.path.join(folder, f"trades_{stamp}.json"))
            
            import shutil
            shutil.copy2(self.equity_file, os.path.join(folder, f"equity_{stamp}.csv"))
            shutil.copy2(self.events_file, os.path.join(folder, f"events_{stamp}.jsonl"))
            QMessageBox.information(self, "Экспорт", f"Данные экспортированы в:\n{folder}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))
    
    def closeEvent(self, event):
        """Корректно останавливаем все воркеры при закрытии"""
        # Останавливаем автоторговлю
        if hasattr(self, 'auto_timer') and self.auto_timer:
            self.auto_timer.stop()
        
        if hasattr(self, 'auto_worker') and self.auto_worker and self.auto_worker.isRunning():
            self.auto_worker.stop()
            self.auto_worker.wait(1000)
        
        # Останавливаем воркеры Smart AI панели
        if hasattr(self, 'smart_ai_panel') and self.smart_ai_panel:
            self.smart_ai_panel.stop_all_workers()
        
        # Останавливаем воркеры стратегий
        if hasattr(self, 'strategy_workers'):
            for worker in self.strategy_workers.values():
                if worker.isRunning():
                    worker.stop()
                    worker.wait(500)
        
        # Останавливаем менеджер стратегий
        if hasattr(self, 'strategy_manager'):
            self.strategy_manager.stop_all()
        
        if hasattr(self, 'strategy_watchdog') and self.strategy_watchdog:
            self.strategy_watchdog.stop()
        if hasattr(self, 'exit_rules_timer') and self.exit_rules_timer:
            self.exit_rules_timer.stop()
        if hasattr(self, 'io_flush_timer') and self.io_flush_timer:
            self.io_flush_timer.stop()
        
        # Останавливаем AI воркер
        if hasattr(self, 'ai_worker') and self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.wait(500)
        
        # Останавливаем refresh воркер
        if hasattr(self, 'refresh_worker') and self.refresh_worker and self.refresh_worker.isRunning():
            self.refresh_worker.wait(500)
        
        # Останавливаем connect воркер
        if hasattr(self, 'connect_worker') and self.connect_worker and self.connect_worker.isRunning():
            self.connect_worker.wait(500)

        if hasattr(self, '_close_workers'):
            for worker in list(self._close_workers.values()):
                if worker and worker.isRunning():
                    worker.wait(400)
            self._close_workers.clear()

        self._flush_runtime_buffers()
        
        event.accept()

