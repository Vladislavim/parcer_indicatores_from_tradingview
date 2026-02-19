"""
🎯 Adaptive Regime Strategy

Адаптивная стратегия под 3 режима рынка:
- Trend Up: лонг по откату
- Trend Down: шорт по откату
- Range: возврат к среднему (mean reversion)

Идея: не использовать одну и ту же логику во всех фазах рынка.
"""
from typing import Optional, Tuple
import math

from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal


CONFIG = StrategyConfig(
    name="🎯 Adaptive Regime",
    description="Автовыбор режима рынка: тренд вверх/вниз и боковик. Лонг/шорт/флэт-логика в одной стратегии.",
    timeframe="1h",
    sl_pct=1.2,
    tp_pct=2.8,
    risk_reward="1:2.3",
    avg_monthly_return="8-25%",
    win_rate="45-62%",
    trades_per_month="12-30",
    risk_level="Средний",
)


class AdaptiveRegimeStrategy(BaseStrategy):
    """Режимная стратегия: тренд + контртренд в боковике."""

    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)

    def _bollinger(self, closes: list, period: int = 20, std_mult: float = 2.0) -> Tuple[float, float, float]:
        if len(closes) < period:
            return 0.0, 0.0, 0.0
        sma = sum(closes[-period:]) / period
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = math.sqrt(variance)
        return sma - std_mult * std, sma, sma + std_mult * std

    def _regime(self, closes: list, ohlcv: list) -> str:
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        ema200 = self.calc_ema(closes, 200)
        if not ema20 or not ema50 or not ema200:
            return "unknown"

        px = closes[-1]
        e20 = ema20[-1]
        e50 = ema50[-1]
        e200 = ema200[-1]
        e50_prev = ema50[-6] if len(ema50) >= 6 else ema50[0]
        slope50 = ((e50 - e50_prev) / px) * 100 if px > 0 else 0

        bb_low, bb_mid, bb_up = self._bollinger(closes, 20, 2.0)
        bb_width = ((bb_up - bb_low) / bb_mid) * 100 if bb_mid > 0 else 0
        atr = self.calc_atr(ohlcv, 14)
        atr_pct = (atr / px) * 100 if px > 0 else 0

        if e20 > e50 > e200 and slope50 > 0.10:
            return "trend_up"
        if e20 < e50 < e200 and slope50 < -0.10:
            return "trend_down"
        if bb_width < 5.0 and atr_pct < 2.2:
            return "range"
        return "mixed"

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 260)
        if len(ohlcv) < 210:
            return None

        closes = [x[4] for x in ohlcv]
        highs = [x[2] for x in ohlcv]
        lows = [x[3] for x in ohlcv]
        px = closes[-1]
        rsi = self.calc_rsi(closes)
        atr = self.calc_atr(ohlcv, 14)

        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        if not ema20 or not ema50 or atr <= 0:
            return None

        e20 = ema20[-1]
        e50 = ema50[-1]
        bb_low, bb_mid, bb_up = self._bollinger(closes, 20, 2.0)
        regime = self._regime(closes, ohlcv)

        signal = Signal.NONE
        strength = 0
        reason = ""
        sl = 0.0
        tp = 0.0

        # Trend Up: buy pullback to EMA20 in bullish structure
        if regime == "trend_up":
            if px <= e20 * 1.01 and px > e50 and 38 <= rsi <= 67:
                signal = Signal.BUY
                strength = 72 + int(max(0, 67 - rsi) * 0.7)
                sl = px - atr * 1.3
                tp = px + atr * 3.0
                reason = f"[trend_up] Откат к EMA20, RSI={rsi:.0f}"

        # Trend Down: sell pullback to EMA20 in bearish structure
        elif regime == "trend_down":
            if px >= e20 * 0.99 and px < e50 and 33 <= rsi <= 62:
                signal = Signal.SELL
                strength = 72 + int(max(0, rsi - 33) * 0.7)
                sl = px + atr * 1.3
                tp = px - atr * 3.0
                reason = f"[trend_down] Откат к EMA20, RSI={rsi:.0f}"

        # Range: fade band edges
        elif regime == "range":
            if px <= bb_low * 1.004 and rsi <= 36:
                signal = Signal.BUY
                strength = 68 + int((36 - rsi) * 1.2)
                sl = min(px - atr * 1.2, bb_low - atr * 0.8)
                tp = bb_mid
                reason = f"[range] Лонг от нижней границы BB, RSI={rsi:.0f}"
            elif px >= bb_up * 0.996 and rsi >= 64:
                signal = Signal.SELL
                strength = 68 + int((rsi - 64) * 1.2)
                sl = max(px + atr * 1.2, bb_up + atr * 0.8)
                tp = bb_mid
                reason = f"[range] Шорт от верхней границы BB, RSI={rsi:.0f}"

        # Mixed: breakout continuation
        else:
            h20 = max(highs[-21:-1])
            l20 = min(lows[-21:-1])
            breakout_up = px > (h20 + atr * 0.25)
            breakout_dn = px < (l20 - atr * 0.25)
            if breakout_up and rsi > 52:
                signal = Signal.BUY
                strength = 65 + int(min(25, (rsi - 52) * 1.5))
                sl = px - atr * 1.1
                tp = px + atr * 2.5
                reason = f"[mixed] Breakout вверх, RSI={rsi:.0f}"
            elif breakout_dn and rsi < 48:
                signal = Signal.SELL
                strength = 65 + int(min(25, (48 - rsi) * 1.5))
                sl = px + atr * 1.1
                tp = px - atr * 2.5
                reason = f"[mixed] Breakout вниз, RSI={rsi:.0f}"

        if signal == Signal.NONE:
            return None

        return TradeSignal(
            signal=signal,
            strength=max(0, min(100, strength)),
            entry_price=px,
            sl_price=sl,
            tp_price=tp,
            reason=reason,
        )

    def should_close(self, symbol: str, position_side: str, entry_price: float) -> Tuple[bool, str]:
        ohlcv = self.get_ohlcv(symbol, 120)
        if len(ohlcv) < 60:
            return False, ""

        closes = [x[4] for x in ohlcv]
        px = closes[-1]
        rsi = self.calc_rsi(closes)
        regime = self._regime(closes, ohlcv)
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        if not ema20 or not ema50:
            return False, ""

        # Close on clear regime/structure invalidation
        if position_side == "long":
            if regime == "trend_down":
                return True, "Смена режима в bearish"
            if ema20[-1] < ema50[-1] and rsi < 45:
                return True, "Слом лонг-структуры"
            if regime == "range" and px >= entry_price * 1.01 and rsi > 66:
                return True, "Range take-profit condition"
        else:
            if regime == "trend_up":
                return True, "Смена режима в bullish"
            if ema20[-1] > ema50[-1] and rsi > 55:
                return True, "Слом шорт-структуры"
            if regime == "range" and px <= entry_price * 0.99 and rsi < 34:
                return True, "Range take-profit condition"

        return False, ""

