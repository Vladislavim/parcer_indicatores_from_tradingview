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


def atr_series(highs: List[float], lows: List[float], closes: List[float], length: int) -> List[float]:
    trs: List[float] = []
    for i in range(len(closes)):
        if i == 0:
            tr = highs[i] - lows[i]
        else:
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        trs.append(tr)
    # Pine ATR = RMA, но EMA близко; здесь ATR нужен только косвенно
    return ema_series(trs, length)


def pivot_high(highs: List[float], i: int, L: int) -> Optional[float]:
    j = i - L
    if j - L < 0 or j + L >= len(highs):
        return None
    c = highs[j]
    left = highs[j - L: j]
    right = highs[j + 1: j + L + 1]
    if all(c > x for x in left) and all(c > x for x in right):
        return c
    return None


def pivot_low(lows: List[float], i: int, L: int) -> Optional[float]:
    j = i - L
    if j - L < 0 or j + L >= len(lows):
        return None
    c = lows[j]
    left = lows[j - L: j]
    right = lows[j + 1: j + L + 1]
    if all(c < x for x in left) and all(c < x for x in right):
        return c
    return None


def _bars_since(last_ts: Optional[int], cur_ts: int, tf_ms: int) -> int:
    if last_ts is None:
        return 10**9
    if tf_ms <= 0:
        return 10**9
    return int((cur_ts - last_ts) // tf_ms)


class EmaMarketStructureBOSWaves(IndicatorBase):
    name = "EMA Market Structure [BOSWaves] (BOS)"

    @staticmethod
    def default_params() -> Dict[str, Any]:
        return {
            "emaLength": 50,
            "swingLength": 5,
            "swingCooloff": 10,
            "bosCooloff": 15,
            "slBufferPct": 0.1,
        }

    def compute(self, candles, state: Dict[str, Any], params: Dict[str, Any]) -> List[Signal]:
        if len(candles) < 200:
            return []

        ema_len = int(params.get("emaLength", 50))
        L = int(params.get("swingLength", 5))
        swing_cool = int(params.get("swingCooloff", 10))
        bos_cool = int(params.get("bosCooloff", 15))
        sl_buf = float(params.get("slBufferPct", 0.1))

        highs = [c.h for c in candles]
        lows = [c.l for c in candles]
        closes = [c.c for c in candles]
        ts = [c.ts for c in candles]

        n = len(candles) - 1

        ema = ema_series(closes, ema_len)

        # init vars из state (используем ts вместо индексов для sliding window)
        lastSwingHighTs: Optional[int] = state.get("lastSwingHighTs")
        lastSwingLowTs: Optional[int] = state.get("lastSwingLowTs")
        lastSwingHigh: Optional[float] = state.get("lastSwingHigh")
        lastSwingLow: Optional[float] = state.get("lastSwingLow")
        prevSwingHigh: Optional[float] = state.get("prevSwingHigh")
        prevSwingLow: Optional[float] = state.get("prevSwingLow")
        lastBullishBOSTs: Optional[int] = state.get("lastBullishBOSTs")
        lastBearishBOSTs: Optional[int] = state.get("lastBearishBOSTs")

        tf_ms = int(state.get("tf_ms", 60_000))

        # флаги и данные для сигнала только на последнем баре
        bullish_last = False
        bearish_last = False
        bull_sl: Optional[float] = None
        bear_sl: Optional[float] = None
        bull_break_level: Optional[float] = None
        bear_break_level: Optional[float] = None

        # проигрываем историю внутри окна
        for i in range(1, len(candles)):
            cur_ts = ts[i]
            emaTrend_i = 1 if ema[i] > ema[i - 1] else -1 if ema[i] < ema[i - 1] else 0

            ph = pivot_high(highs, i, L)
            pl = pivot_low(lows, i, L)

            canPlotHigh = _bars_since(lastSwingHighTs, cur_ts, tf_ms) >= swing_cool
            canPlotLow = _bars_since(lastSwingLowTs, cur_ts, tf_ms) >= swing_cool

            if ph is not None and canPlotHigh:
                prevSwingHigh = lastSwingHigh
                lastSwingHigh = ph
                lastSwingHighTs = cur_ts

            if pl is not None and canPlotLow:
                prevSwingLow = lastSwingLow
                lastSwingLow = pl
                lastSwingLowTs = cur_ts

            canBull = _bars_since(lastBullishBOSTs, cur_ts, tf_ms) >= bos_cool
            canBear = _bars_since(lastBearishBOSTs, cur_ts, tf_ms) >= bos_cool

            bullishBOS = (
                canBull
                and emaTrend_i == 1
                and prevSwingHigh is not None
                and closes[i] > prevSwingHigh
                and closes[i - 1] <= prevSwingHigh
            )
            bearishBOS = (
                canBear
                and emaTrend_i == -1
                and prevSwingLow is not None
                and closes[i] < prevSwingLow
                and closes[i - 1] >= prevSwingLow
            )

            if bullishBOS:
                lastBullishBOSTs = cur_ts
                if i == n:
                    bullish_last = True
                    bull_sl = lows[i] * (1 - sl_buf / 100.0)
                    bull_break_level = prevSwingHigh

            if bearishBOS:
                lastBearishBOSTs = cur_ts
                if i == n:
                    bearish_last = True
                    bear_sl = highs[i] * (1 + sl_buf / 100.0)
                    bear_break_level = prevSwingLow

        # текущий EMA-тренд (по последнему бару)
        emaTrend = 1 if ema[n] > ema[n - 1] else -1 if ema[n] < ema[n - 1] else 0

        # сохраняем состояние обратно
        state["lastSwingHighTs"] = lastSwingHighTs
        state["lastSwingLowTs"] = lastSwingLowTs
        state["lastSwingHigh"] = lastSwingHigh
        state["lastSwingLow"] = lastSwingLow
        state["prevSwingHigh"] = prevSwingHigh
        state["prevSwingLow"] = prevSwingLow
        state["lastBullishBOSTs"] = lastBullishBOSTs
        state["lastBearishBOSTs"] = lastBearishBOSTs
        state["emaTrend"] = emaTrend  # для статуса в get_signal

        out: List[Signal] = []

        if bullish_last and bull_break_level is not None and bull_sl is not None:
            out.append(Signal(
                type="BUY",
                name="BOS",
                message=f"Bullish BOS\nBreak level: {bull_break_level}\nClose: {closes[n]}\nSL: {bull_sl}",
                ts_ms=ts[n],
            ))

        if bearish_last and bear_break_level is not None and bear_sl is not None:
            out.append(Signal(
                type="SELL",
                name="BOS",
                message=f"Bearish BOS\nBreak level: {bear_break_level}\nClose: {closes[n]}\nSL: {bear_sl}",
                ts_ms=ts[n],
            ))

        return out


# обёртка для сигнала

_INDICATOR = EmaMarketStructureBOSWaves()


def _status_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    t = int(state.get("emaTrend", 0) or 0)
    if t > 0:
        return "bull"
    if t < 0:
        return "bear"
    return "neutral"


def _detail_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    t = int(state.get("emaTrend", 0) or 0)
    if t > 0:
        return "EMA тренд вверх"
    if t < 0:
        return "EMA тренд вниз"
    return "EMA тренд боковик"


def get_signal(symbol: str, timeframe: str, source: str):
    return run_indicator_get_signal(
        _INDICATOR,
        "ema_ms",
        symbol,
        timeframe,
        source,
        status_from_state=_status_from_state,
        detail_from_state=_detail_from_state,
    )
