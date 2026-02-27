"""
Gold -> BTC inverse regime strategy (optional thesis-based strategy).

Idea:
- When gold (XAUTUSDT) shows a confirmed downside regime, BTC more often trades in risk-on mode.
- When gold shows a confirmed upside regime, BTC can weaken.

This is NOT a deterministic relation, so the strategy uses BTC confirmation and ATR-based SL/TP.
"""
from typing import Optional

from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal


CONFIG = StrategyConfig(
    name="🥇↔₿ Gold/BTC Inverse",
    description="Тезисная стратегия: золото как risk-off фильтр, BTC как risk-on. Вход только с подтверждением на BTC.",
    timeframe="4h",
    sl_pct=1.8,
    tp_pct=3.6,
    risk_reward="1:2",
    avg_monthly_return="8-20%",
    win_rate="42-58%",
    trades_per_month="4-12",
    risk_level="Средний",
)


class GoldBtcInverseStrategy(BaseStrategy):
    """Стратегия для BTC на основе направления золота (XAUTUSDT) + подтверждения BTC."""

    GOLD_CANDIDATES = [
        "XAUT/USDT:USDT",  # Bybit perp style
        "XAUTUSDT",        # fallback raw id if ccxt mapping differs
    ]

    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        self._gold_symbol_cache: Optional[str] = None

    @staticmethod
    def _symbol_key(symbol: str) -> str:
        s = (symbol or "").upper()
        if "/" in s:
            s = s.split("/")[0]
        if ":" in s:
            s = s.split(":")[0]
        return s

    def _resolve_gold_symbol(self) -> Optional[str]:
        if self._gold_symbol_cache:
            return self._gold_symbol_cache
        if not self.exchange:
            return None
        for candidate in self.GOLD_CANDIDATES:
            try:
                # If market exists or ticker fetch works, cache it.
                self.exchange.fetch_ticker(candidate)
                self._gold_symbol_cache = candidate
                return candidate
            except Exception:
                continue
        return None

    @staticmethod
    def _pct_change(values: list[float], lookback: int) -> float:
        if len(values) <= lookback or lookback <= 0:
            return 0.0
        prev = float(values[-1 - lookback])
        cur = float(values[-1])
        if prev == 0:
            return 0.0
        return (cur - prev) / prev * 100.0

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        # Стратегия применима только к BTC (тезис Gold -> BTC).
        if self._symbol_key(symbol) != "BTC":
            return None
        if not self.exchange:
            return None

        gold_symbol = self._resolve_gold_symbol()
        if not gold_symbol:
            return None

        btc_ohlcv = self.get_ohlcv(symbol, 140)
        if len(btc_ohlcv) < 80:
            return None

        try:
            gold_ohlcv = self.exchange.fetch_ohlcv(gold_symbol, self.config.timeframe, limit=140)
        except Exception:
            return None
        if not gold_ohlcv or len(gold_ohlcv) < 80:
            return None

        btc_closes = [float(c[4]) for c in btc_ohlcv]
        gold_closes = [float(c[4]) for c in gold_ohlcv]
        btc_price = btc_closes[-1]
        gold_price = gold_closes[-1]
        if btc_price <= 0 or gold_price <= 0:
            return None

        # Trend / regime filters
        btc_ema20 = self.calc_ema(btc_closes, 20)
        btc_ema50 = self.calc_ema(btc_closes, 50)
        gold_ema20 = self.calc_ema(gold_closes, 20)
        gold_ema50 = self.calc_ema(gold_closes, 50)
        if not btc_ema20 or not btc_ema50 or not gold_ema20 or not gold_ema50:
            return None

        btc_rsi = self.calc_rsi(btc_closes, 14)
        btc_atr = self.calc_atr(btc_ohlcv, 14)
        if btc_atr <= 0:
            return None

        gold_ret_3 = self._pct_change(gold_closes, 3)
        gold_ret_12 = self._pct_change(gold_closes, 12)
        btc_ret_3 = self._pct_change(btc_closes, 3)

        gold_down = gold_ema20[-1] < gold_ema50[-1] and gold_ret_3 <= -0.35 and gold_ret_12 <= -0.8
        gold_up = gold_ema20[-1] > gold_ema50[-1] and gold_ret_3 >= 0.35 and gold_ret_12 >= 0.8

        btc_bull_confirm = btc_price > btc_ema20[-1] and btc_ema20[-1] >= btc_ema50[-1] * 0.995 and btc_rsi < 72 and btc_ret_3 >= 0.15
        btc_bear_confirm = btc_price < btc_ema20[-1] and btc_ema20[-1] <= btc_ema50[-1] * 1.005 and btc_rsi > 28 and btc_ret_3 <= -0.15

        signal = Signal.NONE
        strength = 0
        reason = ""

        if gold_down and btc_bull_confirm:
            signal = Signal.BUY
            strength = 70
            if gold_ret_12 <= -1.5:
                strength += 10
            if btc_price > btc_ema50[-1]:
                strength += 8
            strength = min(strength, 95)
            reason = (
                f"Gold weak (3={gold_ret_3:.2f}%, 12={gold_ret_12:.2f}%) + BTC bullish confirmation "
                f"(RSI={btc_rsi:.0f}, ret3={btc_ret_3:.2f}%)"
            )
        elif gold_up and btc_bear_confirm:
            signal = Signal.SELL
            strength = 70
            if gold_ret_12 >= 1.5:
                strength += 10
            if btc_price < btc_ema50[-1]:
                strength += 8
            strength = min(strength, 95)
            reason = (
                f"Gold strong (3={gold_ret_3:.2f}%, 12={gold_ret_12:.2f}%) + BTC bearish confirmation "
                f"(RSI={btc_rsi:.0f}, ret3={btc_ret_3:.2f}%)"
            )
        else:
            return None

        # ATR based SL + fixed RR 1:2
        sl_dist = max(btc_atr * 1.25, btc_price * 0.006)  # >=0.6%
        tp_dist = sl_dist * 2.0
        if signal == Signal.BUY:
            sl_price = btc_price - sl_dist
            tp_price = btc_price + tp_dist
        else:
            sl_price = btc_price + sl_dist
            tp_price = btc_price - tp_dist

        return TradeSignal(
            signal=signal,
            strength=int(strength),
            entry_price=float(btc_price),
            sl_price=float(sl_price),
            tp_price=float(tp_price),
            reason=reason,
        )

    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple[bool, str]:
        # Позиции закрываются через SL/TP терминала/биржи. Здесь только мягкий фильтр на слом тезиса.
        if self._symbol_key(symbol) != "BTC":
            return False, ""
        try:
            btc_ohlcv = self.get_ohlcv(symbol, 80)
            gold_symbol = self._resolve_gold_symbol()
            if not gold_symbol or len(btc_ohlcv) < 50:
                return False, ""
            gold_ohlcv = self.exchange.fetch_ohlcv(gold_symbol, self.config.timeframe, limit=80)
            if not gold_ohlcv or len(gold_ohlcv) < 50:
                return False, ""

            btc_closes = [float(c[4]) for c in btc_ohlcv]
            gold_closes = [float(c[4]) for c in gold_ohlcv]
            btc_ema20 = self.calc_ema(btc_closes, 20)
            btc_ema50 = self.calc_ema(btc_closes, 50)
            gold_ema20 = self.calc_ema(gold_closes, 20)
            gold_ema50 = self.calc_ema(gold_closes, 50)
            if not btc_ema20 or not btc_ema50 or not gold_ema20 or not gold_ema50:
                return False, ""

            if position_side == "long" and (gold_ema20[-1] > gold_ema50[-1] and btc_ema20[-1] < btc_ema50[-1]):
                return True, "Тезис Gold→BTC сломан: gold up + BTC weak"
            if position_side == "short" and (gold_ema20[-1] < gold_ema50[-1] and btc_ema20[-1] > btc_ema50[-1]):
                return True, "Тезис Gold→BTC сломан: gold down + BTC strong"
        except Exception:
            return False, ""
        return False, ""

