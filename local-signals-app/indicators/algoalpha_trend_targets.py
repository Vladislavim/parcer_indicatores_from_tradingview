from __future__ import annotations
from typing import Dict, Any, List, Optional
from indicators.base import IndicatorBase, Signal
from indicators.runtime import run_indicator_get_signal


def ema_series(values: List[float], length: int) -> List[float]:
    alpha = 2 / (length + 1)
    out: List[float] = []
    e: Optional[float] = None
    for v in values:
        e = v if e is None else (e + alpha * (v - e))
        out.append(e)
    return out


def wma_series(values: List[float], length: int) -> List[float]:
    out: List[float] = []
    w = list(range(1, length + 1))
    ws = sum(w)
    for i in range(len(values)):
        if i + 1 < length:
            out.append(values[i])
            continue
        window = values[i - length + 1: i + 1]
        out.append(sum(window[j] * w[j] for j in range(length)) / ws)
    return out


def atr_series(highs: List[float], lows: List[float], closes: List[float], length: int) -> List[float]:
    tr: List[float] = []
    for i in range(len(closes)):
        if i == 0:
            tr.append(highs[i] - lows[i])
        else:
            tr.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            ))
    # Pine atr() = RMA. EMA близко; для SL/TP обычно ок.
    return ema_series(tr, length)


def pine_supertrend_bands(highs, lows, closes, factor, atrPeriod):
    # src = hl2
    hl2 = [(h + l) / 2 for h, l in zip(highs, lows)]
    atr = atr_series(highs, lows, closes, atrPeriod)
    upper = [hl2[i] + factor * atr[i] for i in range(len(closes))]
    lower = [hl2[i] - factor * atr[i] for i in range(len(closes))]

    out_lower = lower[:]
    out_upper = upper[:]

    for i in range(1, len(closes)):
        prevLower = out_lower[i - 1]
        prevUpper = out_upper[i - 1]

        # lowerBand := lowerBand > prevLowerBand or close[1] < prevLowerBand ? lowerBand : prevLowerBand
        if not (out_lower[i] > prevLower or closes[i - 1] < prevLower):
            out_lower[i] = prevLower

        # upperBand := upperBand < prevUpperBand or close[1] > prevUpperBand ? upperBand : prevUpperBand
        if not (out_upper[i] < prevUpper or closes[i - 1] > prevUpper):
            out_upper[i] = prevUpper

    return out_lower, out_upper


def crossover(a: List[float], b: List[float], i: int) -> bool:
    return a[i] > b[i] and a[i - 1] <= b[i - 1]


def crossunder(a: List[float], b: List[float], i: int) -> bool:
    return a[i] < b[i] and a[i - 1] >= b[i - 1]


class TrendTargetsAlgoAlpha(IndicatorBase):
    name = "Trend Targets [AlgoAlpha] (Trend change)"

    @staticmethod
    def default_params() -> Dict[str, Any]:
        return {
            "st_factor": 12.0,
            "st_atr_period": 90,
            "wma_length": 40,
            "ema_length": 14,
            "atr_period": 14,
            "sl_multiplier": 5.0,
            "tp1_multiplier": 0.5,
            "tp2_multiplier": 1.0,
            "tp3_multiplier": 1.5,
        }

    def compute(self, candles, state: Dict[str, Any], params: Dict[str, Any]) -> List[Signal]:
        if len(candles) < 300:
            return []

        st_factor = float(params.get("st_factor", 12.0))
        st_atr_period = int(params.get("st_atr_period", 90))
        wma_length = int(params.get("wma_length", 40))
        ema_length = int(params.get("ema_length", 14))

        atr_period = int(params.get("atr_period", 14))
        sl_mult = float(params.get("sl_multiplier", 5.0))
        tp1m = float(params.get("tp1_multiplier", 0.5))
        tp2m = float(params.get("tp2_multiplier", 1.0))
        tp3m = float(params.get("tp3_multiplier", 1.5))

        highs = [c.h for c in candles]
        lows = [c.l for c in candles]
        closes = [c.c for c in candles]
        ts = [c.ts for c in candles]

        n = len(candles) - 1

        lwr, upr = pine_supertrend_bands(highs, lows, closes, st_factor, st_atr_period)
        mid = [(lwr[i] + upr[i]) / 2 for i in range(len(closes))]
        tL = ema_series(wma_series(mid, wma_length), ema_length)

        # строим смещённую серию для кроссов
        tL_shift = [tL[0]] + tL[:-1]

        # тренд восстанавливаем по всей истории окна
        trend = int(state.get("trend", 0) or 0)
        prev_trend_before_last = trend

        for i in range(1, len(closes)):
            if i == n:
                # сохраняем тренд перед последним баром
                prev_trend_before_last = trend

            if crossover(tL, tL_shift, i):
                trend = 1
            elif crossunder(tL, tL_shift, i):
                trend = -1

        cur_trend = trend
        state["trend"] = cur_trend  # для статуса в get_signal

        longSignal = (cur_trend == 1 and prev_trend_before_last <= 0)
        shortSignal = (cur_trend == -1 and prev_trend_before_last >= 0)

        vol = atr_series(highs, lows, closes, atr_period)

        out: List[Signal] = []

        if longSignal:
            SL = lows[n] - vol[n] * sl_mult
            dist = abs(closes[n] - SL)
            TP1 = closes[n] + dist * tp1m
            TP2 = closes[n] + dist * tp2m
            TP3 = closes[n] + dist * tp3m

            out.append(Signal(
                type="BUY",
                name="Trend",
                message=(
                    f"Long signal\nEntry: {closes[n]}\nSL: {SL}\nTP1: {TP1}\nTP2: {TP2}\nTP3: {TP3}"
                ),
                ts_ms=ts[n],
            ))

        if shortSignal:
            SL = highs[n] + vol[n] * sl_mult
            dist = abs(closes[n] - SL)
            TP1 = closes[n] - dist * tp1m
            TP2 = closes[n] - dist * tp2m
            TP3 = closes[n] - dist * tp3m

            out.append(Signal(
                type="SELL",
                name="Trend",
                message=(
                    f"Short signal\nEntry: {closes[n]}\nSL: {SL}\nTP1: {TP1}\nTP2: {TP2}\nTP3: {TP3}"
                ),
                ts_ms=ts[n],
            ))

        return out


# обёртка для сигнала

_INDICATOR = TrendTargetsAlgoAlpha()


def _status_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    t = int(state.get("trend", 0) or 0)
    if t > 0:
        return "bull"
    if t < 0:
        return "bear"
    return "neutral"


def _detail_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    t = int(state.get("trend", 0) or 0)
    if t > 0:
        return "Тренд: вверх"
    if t < 0:
        return "Тренд: вниз"
    return "Тренд: боковик"


def get_signal(symbol: str, timeframe: str, source: str):
    return run_indicator_get_signal(
        _INDICATOR,
        "trend_targets",
        symbol,
        timeframe,
        source,
        status_from_state=_status_from_state,
        detail_from_state=_detail_from_state,
    )
