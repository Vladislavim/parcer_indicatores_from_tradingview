from __future__ import annotations
from typing import Dict, Any, List, Optional
from indicators.base import IndicatorBase, Signal
from indicators.runtime import run_indicator_get_signal


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


class SmartMoneyBreakoutAlgoAlpha(IndicatorBase):
    name = "Smart Money Breakout [AlgoAlpha] (BOS/CHoCH)"

    @staticmethod
    def default_params() -> Dict[str, Any]:
        return {
            "swingSize": 25,
            "bosConfType": "Candle Close",  # или "Wicks"
            "showCHoCH": True,
        }

    def compute(self, candles, state: Dict[str, Any], params: Dict[str, Any]) -> List[Signal]:
        if len(candles) < 300:
            return []

        swingSize = int(params.get("swingSize", 25))
        bosConfType = str(params.get("bosConfType", "Candle Close"))
        showCHoCH = bool(params.get("showCHoCH", True))

        highs = [c.h for c in candles]
        lows = [c.l for c in candles]
        closes = [c.c for c in candles]
        ts = [c.ts for c in candles]

        n = len(candles) - 1

        # восстановление состояния (как var в Pine)
        prevHigh: Optional[float] = state.get("prevHigh")
        prevLow: Optional[float] = state.get("prevLow")
        prevHighIndex: Optional[int] = state.get("prevHighIndex")
        prevLowIndex: Optional[int] = state.get("prevLowIndex")
        highActive: bool = bool(state.get("highActive", False))
        lowActive: bool = bool(state.get("lowActive", False))
        prevBreakoutDir: int = int(state.get("prevBreakoutDir", 0) or 0)  # 1 bullish, -1 bearish

        # флаги для последнего бара
        bull_broken_last = False
        bear_broken_last = False
        bull_label_last: Optional[str] = None
        bear_label_last: Optional[str] = None

        # проигрываем историю по всему окну
        for i in range(len(candles)):
            pivHi = pivot_high(highs, i, swingSize)
            pivLo = pivot_low(lows, i, swingSize)

            if pivHi is not None:
                prevHigh = pivHi
                prevHighIndex = i - swingSize
                highActive = True

            if pivLo is not None:
                prevLow = pivLo
                prevLowIndex = i - swingSize
                lowActive = True

            highSrc = closes[i] if bosConfType == "Candle Close" else highs[i]
            lowSrc = closes[i] if bosConfType == "Candle Close" else lows[i]

            highBroken = (
                prevHigh is not None
                and highActive
                and highSrc > prevHigh
            )
            lowBroken = (
                prevLow is not None
                and lowActive
                and lowSrc < prevLow
            )

            if highBroken:
                highActive = False
                label = "BOS"
                if showCHoCH and prevBreakoutDir == -1:
                    label = "CHoCH"
                prevBreakoutDir = 1

                if i == n:
                    bull_broken_last = True
                    bull_label_last = label

            if lowBroken:
                lowActive = False
                label = "BOS"
                if showCHoCH and prevBreakoutDir == 1:
                    label = "CHoCH"
                prevBreakoutDir = -1

                if i == n:
                    bear_broken_last = True
                    bear_label_last = label

        # сохраняем состояние обратно
        state["prevHigh"] = prevHigh
        state["prevLow"] = prevLow
        state["prevHighIndex"] = prevHighIndex
        state["prevLowIndex"] = prevLowIndex
        state["highActive"] = highActive
        state["lowActive"] = lowActive
        state["prevBreakoutDir"] = prevBreakoutDir

        out: List[Signal] = []

        if bull_broken_last and bull_label_last is not None and prevHigh is not None:
            out.append(Signal(
                type="BUY",
                name=bull_label_last,
                message=f"Bullish Breakout ({bull_label_last})\nLevel: {prevHigh}\nClose: {closes[n]}",
                ts_ms=ts[n],
            ))

        if bear_broken_last and bear_label_last is not None and prevLow is not None:
            out.append(Signal(
                type="SELL",
                name=bear_label_last,
                message=f"Bearish Breakout ({bear_label_last})\nLevel: {prevLow}\nClose: {closes[n]}",
                ts_ms=ts[n],
            ))

        return out


# обёртка для сигнала

_INDICATOR = SmartMoneyBreakoutAlgoAlpha()


def _status_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    d = int(state.get("prevBreakoutDir", 0) or 0)
    if d > 0:
        return "bull"
    if d < 0:
        return "bear"
    return "neutral"


def _detail_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    d = int(state.get("prevBreakoutDir", 0) or 0)
    if d > 0:
        return "Последний пробой: вверх"
    if d < 0:
        return "Последний пробой: вниз"
    return "Нет пробоя"


def get_signal(symbol: str, timeframe: str, source: str):
    return run_indicator_get_signal(
        _INDICATOR,
        "smart_money",
        symbol,
        timeframe,
        source,
        status_from_state=_status_from_state,
        detail_from_state=_detail_from_state,
    )
