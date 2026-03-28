from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from indicators.algoalpha_smart_money_breakout import pivot_high as smart_pivot_high
from indicators.algoalpha_smart_money_breakout import pivot_low as smart_pivot_low
from indicators.boswaves_ema_market_structure import ema_series as bos_ema_series
from indicators.boswaves_ema_market_structure import pivot_high as bos_pivot_high
from indicators.boswaves_ema_market_structure import pivot_low as bos_pivot_low
from indicators.confirmation_stack import (
    analyze_alpha_trend,
    analyze_confirmation_stack_ohlcv,
    analyze_qqe_signals,
    analyze_smart_qqe,
    analyze_turtle_trade_channels,
    analyze_twin_range_filter,
    analyze_ualgo_trend,
    analyze_zero_lag,
)

from .base import BaseStrategy, Signal, StrategyConfig, TradeSignal


HTF_ORDER_BLOCK_CONFIG = StrategyConfig(
    name="HTF Order Block",
    description="Основная стратегия по ТЗ: вход от старшего order block, SL за блоком, TP на новый HH/LL.",
    timeframe="4h",
    sl_pct=0.7,
    tp_pct=2.4,
    risk_reward="1:3",
    avg_monthly_return="8-18%",
    win_rate="44-58%",
    trades_per_month="4-10",
    risk_level="Medium",
)

LIQUIDITY_ORDER_BLOCK_CONFIG = StrategyConfig(
    name="Liquidity Sweep + OB",
    description="Order block + снятие liquidity + возврат в supply/demand before entry.",
    timeframe="4h",
    sl_pct=0.8,
    tp_pct=2.6,
    risk_reward="1:3.2",
    avg_monthly_return="9-20%",
    win_rate="42-56%",
    trades_per_month="3-8",
    risk_level="Medium",
)

SMART_MONEY_SOLO_CONFIG = StrategyConfig(
    name="Smart Money Breakout Solo",
    description="Отдельная стратегия по Smart Money Breakout [AlgoAlpha] без тестовых надстроек.",
    timeframe="1h",
    sl_pct=0.9,
    tp_pct=2.7,
    risk_reward="1:3",
    avg_monthly_return="8-16%",
    win_rate="43-55%",
    trades_per_month="8-16",
    risk_level="Medium",
)

EMA_SOLO_CONFIG = StrategyConfig(
    name="EMA Market Structure Solo",
    description="Отдельная стратегия по EMA Market Structure [BOSWaves] с BOS и EMA trend filter.",
    timeframe="1h",
    sl_pct=0.8,
    tp_pct=2.4,
    risk_reward="1:3",
    avg_monthly_return="7-15%",
    win_rate="45-57%",
    trades_per_month="7-14",
    risk_level="Medium",
)

ALPHA_TREND_SOLO_CONFIG = StrategyConfig(
    name="AlphaTrend Solo",
    description="Соло-стратегия по AlphaTrend из ссылки, без обязательных внешних фильтров.",
    timeframe="1h",
    sl_pct=0.9,
    tp_pct=2.7,
    risk_reward="1:3",
    avg_monthly_return="7-14%",
    win_rate="44-56%",
    trades_per_month="9-18",
    risk_level="Medium",
)

ZERO_LAG_SOLO_CONFIG = StrategyConfig(
    name="Zero Lag Solo",
    description="Соло-стратегия по Zero Lag Signals For Loop [QuantAlgo].",
    timeframe="1h",
    sl_pct=1.0,
    tp_pct=3.0,
    risk_reward="1:3",
    avg_monthly_return="8-17%",
    win_rate="41-53%",
    trades_per_month="6-12",
    risk_level="Medium",
)

SMART_EMA_COMBO_CONFIG = StrategyConfig(
    name="Smart Money + EMA Combo",
    description="Комбо: Smart Money Breakout [AlgoAlpha] + EMA Market Structure [BOSWaves].",
    timeframe="1h",
    sl_pct=0.7,
    tp_pct=2.3,
    risk_reward="1:3.0",
    avg_monthly_return="10-21%",
    win_rate="48-60%",
    trades_per_month="5-11",
    risk_level="Medium",
)

TREND_ENGINE_COMBO_CONFIG = StrategyConfig(
    name="Trend Engine Combo",
    description="Комбо: AlphaTrend + Zero Lag + QQE/Smart QQE/Twin/UAlgo confirmations.",
    timeframe="1h",
    sl_pct=0.8,
    tp_pct=2.6,
    risk_reward="1:3.1",
    avg_monthly_return="11-22%",
    win_rate="47-59%",
    trades_per_month="4-10",
    risk_level="Medium",
)

PROFIT_STACK_COMBO_CONFIG = StrategyConfig(
    name="Profit Stack Combo",
    description="Жесткая связка на максимум потенциала: Smart Money + EMA + AlphaTrend + Zero Lag + combo-only filters.",
    timeframe="1h",
    sl_pct=0.7,
    tp_pct=3.0,
    risk_reward="1:3.5",
    avg_monthly_return="12-26%",
    win_rate="46-58%",
    trades_per_month="3-8",
    risk_level="High",
)


def _match_side(status: str, side: str) -> bool:
    return (side == "buy" and status == "bull") or (side == "sell" and status == "bear")


def _side_from_status(status: str) -> Optional[str]:
    if status == "bull":
        return "buy"
    if status == "bear":
        return "sell"
    return None


def _count_side(modules: Dict[str, Dict[str, Any]], keys: List[str], side: str) -> int:
    want = "bull" if side == "buy" else "bear"
    return sum(1 for key in keys if modules.get(key, {}).get("status") == want)


def _smart_money_event(ohlcv: list, swing_size: int = 25, bos_conf_type: str = "Candle Close") -> Optional[Dict[str, Any]]:
    if len(ohlcv) < max(120, swing_size * 5):
        return None

    highs = [float(x[2]) for x in ohlcv]
    lows = [float(x[3]) for x in ohlcv]
    closes = [float(x[4]) for x in ohlcv]

    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    prev_high_index: Optional[int] = None
    prev_low_index: Optional[int] = None
    high_active = False
    low_active = False
    prev_breakout_dir = 0
    latest: Optional[Dict[str, Any]] = None

    for i in range(len(ohlcv)):
        piv_hi = smart_pivot_high(highs, i, swing_size)
        piv_lo = smart_pivot_low(lows, i, swing_size)

        if piv_hi is not None:
            prev_high = float(piv_hi)
            prev_high_index = i - swing_size
            high_active = True
        if piv_lo is not None:
            prev_low = float(piv_lo)
            prev_low_index = i - swing_size
            low_active = True

        high_src = closes[i] if bos_conf_type == "Candle Close" else highs[i]
        low_src = closes[i] if bos_conf_type == "Candle Close" else lows[i]

        if prev_high is not None and prev_high_index is not None and high_active and high_src > prev_high:
            length = max(1, i - prev_high_index)
            start = max(0, i - length)
            dist = (max(highs[start : i + 1]) - min(lows[start : i + 1])) / 3.0
            latest = {
                "side": "buy",
                "bar_index": i,
                "level": prev_high,
                "label": "CHoCH" if prev_breakout_dir == -1 else "BOS",
                "dist": max(dist, closes[i] * 0.004),
            }
            prev_breakout_dir = 1
            high_active = False

        if prev_low is not None and prev_low_index is not None and low_active and low_src < prev_low:
            length = max(1, i - prev_low_index)
            start = max(0, i - length)
            dist = (max(highs[start : i + 1]) - min(lows[start : i + 1])) / 3.0
            latest = {
                "side": "sell",
                "bar_index": i,
                "level": prev_low,
                "label": "CHoCH" if prev_breakout_dir == 1 else "BOS",
                "dist": max(dist, closes[i] * 0.004),
            }
            prev_breakout_dir = -1
            low_active = False

    return latest


def _ema_structure_event(
    ohlcv: list,
    ema_length: int = 50,
    swing_length: int = 5,
    swing_cooloff: int = 10,
    bos_cooloff: int = 15,
    sl_buffer: float = 0.1,
) -> Optional[Dict[str, Any]]:
    if len(ohlcv) < 160:
        return None

    highs = [float(x[2]) for x in ohlcv]
    lows = [float(x[3]) for x in ohlcv]
    closes = [float(x[4]) for x in ohlcv]
    ema = bos_ema_series(closes, ema_length)

    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    prev_swing_high: Optional[float] = None
    prev_swing_low: Optional[float] = None
    last_swing_high_plot: Optional[int] = None
    last_swing_low_plot: Optional[int] = None
    last_bullish_bos: Optional[int] = None
    last_bearish_bos: Optional[int] = None
    latest: Optional[Dict[str, Any]] = None

    for i in range(1, len(ohlcv)):
        ema_trend = 1 if ema[i] > ema[i - 1] else -1 if ema[i] < ema[i - 1] else 0
        piv_hi = bos_pivot_high(highs, i, swing_length)
        piv_lo = bos_pivot_low(lows, i, swing_length)

        can_plot_high = last_swing_high_plot is None or (i - last_swing_high_plot) >= swing_cooloff
        can_plot_low = last_swing_low_plot is None or (i - last_swing_low_plot) >= swing_cooloff

        if piv_hi is not None and can_plot_high:
            prev_swing_high = last_swing_high
            last_swing_high = float(piv_hi)
            last_swing_high_plot = i
        if piv_lo is not None and can_plot_low:
            prev_swing_low = last_swing_low
            last_swing_low = float(piv_lo)
            last_swing_low_plot = i

        can_bull = last_bullish_bos is None or (i - last_bullish_bos) >= bos_cooloff
        can_bear = last_bearish_bos is None or (i - last_bearish_bos) >= bos_cooloff

        bullish_bos = (
            can_bull
            and ema_trend == 1
            and prev_swing_high is not None
            and closes[i] > prev_swing_high
            and closes[i - 1] <= prev_swing_high
        )
        bearish_bos = (
            can_bear
            and ema_trend == -1
            and prev_swing_low is not None
            and closes[i] < prev_swing_low
            and closes[i - 1] >= prev_swing_low
        )

        if bullish_bos:
            last_bullish_bos = i
            latest = {
                "side": "buy",
                "bar_index": i,
                "level": float(prev_swing_high),
                "sl": float(lows[i] * (1.0 - sl_buffer / 100.0)),
                "ema_trend": ema_trend,
            }
        if bearish_bos:
            last_bearish_bos = i
            latest = {
                "side": "sell",
                "bar_index": i,
                "level": float(prev_swing_low),
                "sl": float(highs[i] * (1.0 + sl_buffer / 100.0)),
                "ema_trend": ema_trend,
            }

    return latest


class _TradingViewStrategyBase(BaseStrategy):
    strategy_group = "Комбо-стратегии"
    group_hint = ""
    sort_order = 100

    def _fetch(self, symbol: str, timeframe: str, limit: int) -> list:
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception:
            return []

    def _price(self, ohlcv: list) -> float:
        return float(ohlcv[-1][4])

    def _atr_value(self, ohlcv: list, period: int = 14) -> float:
        price = self._price(ohlcv)
        return max(self.calc_atr(ohlcv, period), price * 0.0035, 1e-9)

    def _rr_target(self, entry: float, sl: float, side: str, rr: float) -> float:
        risk = max(abs(entry - sl), entry * 0.0035)
        return entry + risk * rr if side == "buy" else entry - risk * rr

    def _recent_swing_stop(self, ohlcv: list, side: str, lookback: int, atr: float) -> float:
        highs = [float(x[2]) for x in ohlcv]
        lows = [float(x[3]) for x in ohlcv]
        if side == "buy":
            return min(lows[-lookback:]) - atr * 0.18
        return max(highs[-lookback:]) + atr * 0.18

    def _recent_target_extreme(self, ohlcv: list, side: str, lookback: int, atr: float) -> float:
        highs = [float(x[2]) for x in ohlcv]
        lows = [float(x[3]) for x in ohlcv]
        if side == "buy":
            return max(highs[-lookback:]) + atr * 0.12
        return min(lows[-lookback:]) - atr * 0.12

    def _is_fresh(self, bar_index: int, total_bars: int, max_age: int) -> bool:
        return (total_bars - 1 - int(bar_index)) <= max_age

    def _not_overextended(self, price: float, level: float, dist: float, side: str) -> bool:
        if side == "buy":
            return price <= level + dist * 0.75
        return price >= level - dist * 0.75

    def _build_trade(
        self,
        *,
        side: str,
        entry: float,
        sl: float,
        tp: float,
        reason: str,
        strength: int,
    ) -> TradeSignal:
        signal = Signal.BUY if side == "buy" else Signal.SELL
        return TradeSignal(
            signal=signal,
            strength=max(1, min(int(strength), 100)),
            entry_price=float(entry),
            sl_price=float(sl),
            tp_price=float(tp),
            reason=reason,
        )

    def should_close(self, symbol: str, position_side: str, entry_price: float) -> Tuple[bool, str]:
        return False, ""


class _OrderBlockBaseStrategy(_TradingViewStrategyBase):
    strategy_group = "Стратегии по ТЗ"
    htf_timeframe = "4h"
    entry_timeframe = "1h"
    require_liquidity = False

    def _trend_side(self, htf_ohlcv: list) -> str:
        closes = [x[4] for x in htf_ohlcv]
        ema50 = self.calc_ema(closes, 50)
        ema200 = self.calc_ema(closes, 200)
        if not ema50 or not ema200:
            return "none"
        if ema50[-1] > ema200[-1] and closes[-1] > ema50[-1]:
            return "buy"
        if ema50[-1] < ema200[-1] and closes[-1] < ema50[-1]:
            return "sell"
        return "none"

    def _structure_side(self, htf_ohlcv: list, swing: int = 5) -> str:
        if len(htf_ohlcv) < swing * 4:
            return "none"
        highs = [x[2] for x in htf_ohlcv]
        lows = [x[3] for x in htf_ohlcv]
        closes = [x[4] for x in htf_ohlcv]
        last_high = None
        last_low = None
        direction = "none"
        for i in range(swing, len(htf_ohlcv) - swing):
            h = highs[i]
            l = lows[i]
            if all(h > x for x in highs[i - swing : i]) and all(h > x for x in highs[i + 1 : i + swing + 1]):
                last_high = h
            if all(l < x for x in lows[i - swing : i]) and all(l < x for x in lows[i + 1 : i + swing + 1]):
                last_low = l
            if last_high is not None and closes[i] > last_high:
                direction = "buy"
            if last_low is not None and closes[i] < last_low:
                direction = "sell"
        return direction

    def _find_order_block(self, htf_ohlcv: list, side: str) -> Optional[Dict[str, float]]:
        if len(htf_ohlcv) < 60:
            return None
        highs = [float(x[2]) for x in htf_ohlcv]
        lows = [float(x[3]) for x in htf_ohlcv]
        closes = [float(x[4]) for x in htf_ohlcv]
        atr = max(self.calc_atr(htf_ohlcv, 14), closes[-1] * 0.004)

        for i in range(len(htf_ohlcv) - 6, 8, -1):
            o = float(htf_ohlcv[i][1])
            h = float(htf_ohlcv[i][2])
            l = float(htf_ohlcv[i][3])
            c = float(htf_ohlcv[i][4])
            future = htf_ohlcv[i + 1 : i + 4]
            if len(future) < 3:
                continue

            prev_high = max(highs[max(0, i - 8) : i])
            prev_low = min(lows[max(0, i - 8) : i])
            future_high = max(float(x[2]) for x in future)
            future_low = min(float(x[3]) for x in future)
            future_close = float(future[-1][4])

            if side == "buy" and c < o:
                impulse_ok = future_high > prev_high and future_close > h and (future_high - l) > atr * 1.15
                if not impulse_ok:
                    continue
                return {
                    "index": float(i),
                    "zone_low": l,
                    "zone_high": max(o, c),
                    "impulse_high": future_high,
                }

            if side == "sell" and c > o:
                impulse_ok = future_low < prev_low and future_close < l and (h - future_low) > atr * 1.15
                if not impulse_ok:
                    continue
                return {
                    "index": float(i),
                    "zone_low": min(o, c),
                    "zone_high": h,
                    "impulse_low": future_low,
                }
        return None

    def _price_in_zone(self, price: float, ob: Dict[str, float], atr: float) -> bool:
        buffer = atr * 0.08
        return (ob["zone_low"] - buffer) <= price <= (ob["zone_high"] + buffer)

    def _has_liquidity_sweep(self, entry_ohlcv: list, side: str, ob: Dict[str, float]) -> bool:
        if len(entry_ohlcv) < 30:
            return False
        highs = [float(x[2]) for x in entry_ohlcv]
        lows = [float(x[3]) for x in entry_ohlcv]
        closes = [float(x[4]) for x in entry_ohlcv]
        if side == "buy":
            prev_pool = min(lows[-25:-5])
            recent_sweep = min(lows[-4:-1])
            reclaimed = closes[-1] >= ob["zone_low"]
            return recent_sweep < prev_pool and reclaimed
        prev_pool = max(highs[-25:-5])
        recent_sweep = max(highs[-4:-1])
        reclaimed = closes[-1] <= ob["zone_high"]
        return recent_sweep > prev_pool and reclaimed

    def _target_from_structure(
        self,
        htf_ohlcv: list,
        ob: Dict[str, float],
        side: str,
        entry: float,
        sl: float,
        atr: float,
    ) -> float:
        idx = int(ob["index"])
        highs = [float(x[2]) for x in htf_ohlcv]
        lows = [float(x[3]) for x in htf_ohlcv]
        swing = 3

        if side == "buy":
            for i in range(len(htf_ohlcv) - swing - 1, max(idx + swing, swing), -1):
                h = highs[i]
                if all(h > x for x in highs[i - swing : i]) and all(h >= x for x in highs[i + 1 : i + swing + 1]):
                    return max(h + atr * 0.12, self._rr_target(entry, sl, side, 3.0))
            structural_target = (max(highs[idx + 1 :]) if idx + 1 < len(highs) else entry) + atr * 0.12
            return max(structural_target, self._rr_target(entry, sl, side, 3.0))

        for i in range(len(htf_ohlcv) - swing - 1, max(idx + swing, swing), -1):
            l = lows[i]
            if all(l < x for x in lows[i - swing : i]) and all(l <= x for x in lows[i + 1 : i + swing + 1]):
                return min(l - atr * 0.12, self._rr_target(entry, sl, side, 3.0))
        structural_target = (min(lows[idx + 1 :]) if idx + 1 < len(lows) else entry) - atr * 0.12
        return min(structural_target, self._rr_target(entry, sl, side, 3.0))

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        htf = self._fetch(symbol, self.htf_timeframe, 220)
        entry_ohlcv = self._fetch(symbol, self.entry_timeframe, 220)
        if len(htf) < 120 or len(entry_ohlcv) < 120:
            return None

        trend_side = self._trend_side(htf)
        structure_side = self._structure_side(htf)
        if trend_side == "none" or trend_side != structure_side:
            return None

        side = trend_side
        ob = self._find_order_block(htf, side)
        if not ob:
            return None

        entry = self._price(entry_ohlcv)
        atr = self._atr_value(entry_ohlcv)
        if not self._price_in_zone(entry, ob, atr):
            return None

        confirmations = analyze_confirmation_stack_ohlcv(entry_ohlcv)
        if not _match_side(confirmations["status"], side):
            return None

        if self.require_liquidity and not self._has_liquidity_sweep(entry_ohlcv, side, ob):
            return None

        if side == "buy":
            sl = ob["zone_low"] - atr * 0.15
        else:
            sl = ob["zone_high"] + atr * 0.15
        tp = self._target_from_structure(htf, ob, side, entry, sl, atr)

        reason = (
            f"HTF order block {self.htf_timeframe} {ob['zone_low']:.4f}-{ob['zone_high']:.4f} "
            f"| SL за OB | TP за крайний {'HH' if side == 'buy' else 'LL'} | {confirmations['detail']}"
        )
        if self.require_liquidity:
            reason += " | liquidity sweep reclaimed"

        strength = 78 if self.require_liquidity else 74
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=reason, strength=strength)


class SmartMoneyBreakoutSoloStrategy(_TradingViewStrategyBase):
    strategy_group = "Одиночные стратегии"
    sort_order = 30

    def __init__(self, exchange):
        super().__init__(exchange, SMART_MONEY_SOLO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 320)
        if len(ohlcv) < 160:
            return None

        event = _smart_money_event(ohlcv)
        if not event or not self._is_fresh(event["bar_index"], len(ohlcv), 2):
            return None

        entry = self._price(ohlcv)
        if not self._not_overextended(entry, event["level"], event["dist"], event["side"]):
            return None

        atr = self._atr_value(ohlcv)
        recent_stop = self._recent_swing_stop(ohlcv, event["side"], 10, atr)
        recent_target = self._recent_target_extreme(ohlcv, event["side"], 24, atr)
        if event["side"] == "buy":
            sl = min(event["level"] - atr * 0.6, recent_stop)
            tp = max(recent_target, event["level"] + event["dist"], self._rr_target(entry, sl, "buy", 3.0))
        else:
            sl = max(event["level"] + atr * 0.6, recent_stop)
            tp = min(recent_target, event["level"] - event["dist"], self._rr_target(entry, sl, "sell", 3.0))

        reason = f"Smart Money Breakout {event['label']} | level {event['level']:.4f}"
        return self._build_trade(side=event["side"], entry=entry, sl=sl, tp=tp, reason=reason, strength=72)


class EmaMarketStructureSoloStrategy(_TradingViewStrategyBase):
    strategy_group = "Одиночные стратегии"
    sort_order = 40

    def __init__(self, exchange):
        super().__init__(exchange, EMA_SOLO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 320)
        if len(ohlcv) < 180:
            return None

        event = _ema_structure_event(ohlcv)
        if not event or not self._is_fresh(event["bar_index"], len(ohlcv), 3):
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        recent_stop = self._recent_swing_stop(ohlcv, event["side"], 9, atr)
        recent_target = self._recent_target_extreme(ohlcv, event["side"], 24, atr)
        if event["side"] == "buy":
            sl = min(float(event["sl"]), recent_stop)
            tp = max(recent_target, self._rr_target(entry, sl, "buy", 3.0))
        else:
            sl = max(float(event["sl"]), recent_stop)
            tp = min(recent_target, self._rr_target(entry, sl, "sell", 3.0))

        reason = f"EMA Market Structure BOS | level {event['level']:.4f}"
        return self._build_trade(side=event["side"], entry=entry, sl=sl, tp=tp, reason=reason, strength=71)


class AlphaTrendSoloStrategy(_TradingViewStrategyBase):
    strategy_group = "Одиночные стратегии"
    sort_order = 50

    def __init__(self, exchange):
        super().__init__(exchange, ALPHA_TREND_SOLO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 260)
        if len(ohlcv) < 140:
            return None

        analysis = analyze_alpha_trend(ohlcv)
        side = "buy" if analysis["bull_signal"] else "sell" if analysis["bear_signal"] else None
        if side is None:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, side, 12, atr)
        tp = self._recent_target_extreme(ohlcv, side, 24, atr)
        tp = max(tp, self._rr_target(entry, sl, side, 3.0)) if side == "buy" else min(tp, self._rr_target(entry, sl, side, 3.0))
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=analysis["detail"], strength=68)


class ZeroLagSoloStrategy(_TradingViewStrategyBase):
    strategy_group = "Одиночные стратегии"
    sort_order = 60

    def __init__(self, exchange):
        super().__init__(exchange, ZERO_LAG_SOLO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 260)
        if len(ohlcv) < 180:
            return None

        analysis = analyze_zero_lag(ohlcv)
        side = "buy" if analysis["bull_signal"] else "sell" if analysis["bear_signal"] else None
        if side is None:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, side, 14, atr)
        tp = self._recent_target_extreme(ohlcv, side, 28, atr)
        tp = max(tp, self._rr_target(entry, sl, side, 3.0)) if side == "buy" else min(tp, self._rr_target(entry, sl, side, 3.0))
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=analysis["detail"], strength=70)


class SmartMoneyEmaComboStrategy(_TradingViewStrategyBase):
    strategy_group = "Комбо-стратегии"
    sort_order = 70

    def __init__(self, exchange):
        super().__init__(exchange, SMART_EMA_COMBO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 320)
        if len(ohlcv) < 180:
            return None

        smart = _smart_money_event(ohlcv)
        ema = _ema_structure_event(ohlcv)
        if not smart or not ema:
            return None
        if smart["side"] != ema["side"]:
            return None
        if not self._is_fresh(smart["bar_index"], len(ohlcv), 2):
            return None
        if not self._is_fresh(ema["bar_index"], len(ohlcv), 3):
            return None

        side = smart["side"]
        entry = self._price(ohlcv)
        if not self._not_overextended(entry, smart["level"], smart["dist"], side):
            return None

        stack = analyze_confirmation_stack_ohlcv(ohlcv)
        if not _match_side(stack["status"], side):
            return None

        atr = self._atr_value(ohlcv)
        swing_stop = self._recent_swing_stop(ohlcv, side, 12, atr)
        if side == "buy":
            sl = min(float(ema["sl"]), smart["level"] - atr * 0.55, swing_stop)
            tp = max(self._rr_target(entry, sl, side, 3.0), smart["level"] + smart["dist"] * 1.2)
        else:
            sl = max(float(ema["sl"]), smart["level"] + atr * 0.55, swing_stop)
            tp = min(self._rr_target(entry, sl, side, 3.0), smart["level"] - smart["dist"] * 1.2)

        reason = f"Smart Money + EMA | {stack['detail']}"
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=reason, strength=79)


class TrendEngineComboStrategy(_TradingViewStrategyBase):
    strategy_group = "Комбо-стратегии"
    sort_order = 80

    def __init__(self, exchange):
        super().__init__(exchange, TREND_ENGINE_COMBO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 260)
        if len(ohlcv) < 180:
            return None

        alpha = analyze_alpha_trend(ohlcv)
        zero = analyze_zero_lag(ohlcv)
        qqe = analyze_qqe_signals(ohlcv)
        smart_qqe = analyze_smart_qqe(ohlcv)
        twin = analyze_twin_range_filter(ohlcv)
        turtle = analyze_turtle_trade_channels(ohlcv)
        ualgo = analyze_ualgo_trend(ohlcv)

        side = None
        if alpha["bull_signal"] and zero["status"] == "bull":
            side = "buy"
        elif alpha["bear_signal"] and zero["status"] == "bear":
            side = "sell"
        elif zero["bull_signal"] and alpha["status"] == "bull":
            side = "buy"
        elif zero["bear_signal"] and alpha["status"] == "bear":
            side = "sell"
        if side is None:
            return None

        extras = {
            "qqe": qqe,
            "smart_qqe": smart_qqe,
            "twin_range": twin,
            "turtle": turtle,
            "ualgo": ualgo,
        }
        if _count_side(extras, list(extras.keys()), side) < 2:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, side, 12, atr)
        tp = self._rr_target(entry, sl, side, 3.1)
        reason = f"AlphaTrend + Zero Lag | extras { _count_side(extras, list(extras.keys()), side) }/5"
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=reason, strength=81)


class ProfitStackComboStrategy(_TradingViewStrategyBase):
    strategy_group = "Комбо-стратегии"
    sort_order = 90

    def __init__(self, exchange):
        super().__init__(exchange, PROFIT_STACK_COMBO_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 320)
        htf = self._fetch(symbol, "4h", 220)
        if len(ohlcv) < 220 or len(htf) < 160:
            return None

        smart = _smart_money_event(ohlcv)
        ema = _ema_structure_event(ohlcv)
        stack = analyze_confirmation_stack_ohlcv(ohlcv)
        if stack["status"] == "neutral":
            return None

        side = _side_from_status(stack["status"])
        if side is None:
            return None

        trigger_ok = False
        if smart and smart["side"] == side and self._is_fresh(smart["bar_index"], len(ohlcv), 2):
            trigger_ok = True
        if ema and ema["side"] == side and self._is_fresh(ema["bar_index"], len(ohlcv), 3):
            trigger_ok = True
        if not trigger_ok:
            return None

        htf_trend = _ema_structure_event(htf, ema_length=50, swing_length=5, swing_cooloff=6, bos_cooloff=8)
        if not htf_trend or htf_trend["side"] != side:
            return None

        modules = stack["modules"]
        if modules["alpha_trend"]["status"] != stack["status"]:
            return None
        if modules["zero_lag"]["status"] != stack["status"]:
            return None

        combo_keys = ["qqe", "smart_qqe", "twin_range", "turtle", "ualgo"]
        if _count_side(modules, combo_keys, side) < 3:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, side, 14, atr)
        tp = self._rr_target(entry, sl, side, 3.5)
        reason = f"Profit stack {side} | {stack['detail']} | combo { _count_side(modules, combo_keys, side) }/5"
        return self._build_trade(side=side, entry=entry, sl=sl, tp=tp, reason=reason, strength=86)


class HtfOrderBlockStrategy(_OrderBlockBaseStrategy):
    sort_order = 10

    def __init__(self, exchange):
        super().__init__(exchange, HTF_ORDER_BLOCK_CONFIG)


class LiquidityReturnOrderBlockStrategy(_OrderBlockBaseStrategy):
    sort_order = 20
    entry_timeframe = "15m"
    require_liquidity = True

    def __init__(self, exchange):
        super().__init__(exchange, LIQUIDITY_ORDER_BLOCK_CONFIG)
