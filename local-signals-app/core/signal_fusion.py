from __future__ import annotations

from typing import Any, Optional

from indicators.confirmation_stack import (
    _atr_series,
    _ema_series,
    _rsi_series,
    analyze_confirmation_stack_ohlcv,
)
from strategies.order_block_strategies import _ema_structure_event, _smart_money_event


def _status_from_side(side: Optional[str]) -> str:
    if side == "buy":
        return "bull"
    if side == "sell":
        return "bear"
    return "neutral"


def _weight_side(score_map: dict[str, int], side: str, weight: int) -> None:
    if side == "bull":
        score_map["bull"] += weight
    elif side == "bear":
        score_map["bear"] += weight


def build_weighted_signal(
    exchange: Any,
    symbol: str,
    timeframe: str,
    *,
    htf_trend: str = "neutral",
    news_bias: Optional[Any] = None,
) -> tuple[str, int, str, dict[str, Any]]:
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=260)
    except Exception as exc:
        return "none", 0, f"ohlcv error: {exc}", {}

    if not ohlcv or len(ohlcv) < 180:
        return "none", 0, "not enough candles", {}

    highs = [float(x[2]) for x in ohlcv]
    lows = [float(x[3]) for x in ohlcv]
    closes = [float(x[4]) for x in ohlcv]
    price = float(closes[-1])

    stack = analyze_confirmation_stack_ohlcv(ohlcv)
    smart_event = _smart_money_event(ohlcv)
    ema_event = _ema_structure_event(ohlcv)

    smart_status = "neutral"
    if smart_event and (len(ohlcv) - 1 - int(smart_event["bar_index"])) <= 3:
        smart_status = _status_from_side(str(smart_event.get("side") or ""))

    ema_status = "neutral"
    if ema_event and (len(ohlcv) - 1 - int(ema_event["bar_index"])) <= 4:
        ema_status = _status_from_side(str(ema_event.get("side") or ""))

    modules = stack.get("modules", {})
    alpha = modules.get("alpha_trend", {})
    zero = modules.get("zero_lag", {})
    qqe = modules.get("qqe", {})
    smart_qqe = modules.get("smart_qqe", {})
    twin = modules.get("twin_range", {})
    turtle = modules.get("turtle", {})
    ualgo = modules.get("ualgo", {})

    weights = {
        "stack": 4,
        "ema": 3,
        "smart": 3,
        "alpha": 2,
        "zero": 2,
        "qqe": 1,
        "smart_qqe": 1,
        "twin": 1,
        "turtle": 1,
        "ualgo": 1,
    }
    scores = {"bull": 0, "bear": 0}
    _weight_side(scores, str(stack.get("status") or "neutral"), weights["stack"])
    _weight_side(scores, ema_status, weights["ema"])
    _weight_side(scores, smart_status, weights["smart"])
    _weight_side(scores, str(alpha.get("status") or "neutral"), weights["alpha"])
    _weight_side(scores, str(zero.get("status") or "neutral"), weights["zero"])
    _weight_side(scores, str(qqe.get("status") or "neutral"), weights["qqe"])
    _weight_side(scores, str(smart_qqe.get("status") or "neutral"), weights["smart_qqe"])
    _weight_side(scores, str(twin.get("status") or "neutral"), weights["twin"])
    _weight_side(scores, str(turtle.get("status") or "neutral"), weights["turtle"])
    _weight_side(scores, str(ualgo.get("status") or "neutral"), weights["ualgo"])

    if htf_trend == "bull":
        scores["bull"] += 2
    elif htf_trend == "bear":
        scores["bear"] += 2

    bias_note = ""
    if news_bias and getattr(news_bias, "active", False):
        scores["bear"] += max(1, int(getattr(news_bias, "score", 1)))
        bias_note = f" | news={getattr(news_bias, 'reason', '')}"
    elif news_bias and getattr(news_bias, "hard_block", False):
        bias_note = f" | news-block={getattr(news_bias, 'reason', '')}"

    atr = _atr_series(highs, lows, closes, 14, use_sma=False)
    ema20 = _ema_series(closes, 20)
    rsi = _rsi_series(closes, 14)
    atr_last = float(atr[-1]) if atr else 0.0
    ema20_last = float(ema20[-1]) if ema20 else price
    rsi_last = float(rsi[-1]) if rsi else 50.0

    long_extension = (price - ema20_last) > (atr_last * 1.6) if atr_last > 0 else False
    short_extension = (ema20_last - price) > (atr_last * 1.6) if atr_last > 0 else False

    long_trigger = bool(alpha.get("bull_signal")) or bool(zero.get("bull_signal")) or ema_status == "bull" or smart_status == "bull"
    short_trigger = bool(alpha.get("bear_signal")) or bool(zero.get("bear_signal")) or ema_status == "bear" or smart_status == "bear"

    bull_score = int(scores["bull"])
    bear_score = int(scores["bear"])
    gap = abs(bull_score - bear_score)
    signal = "none"
    strength = 0

    if (
        bull_score >= 12
        and bull_score >= bear_score + 4
        and str(stack.get("status") or "neutral") == "bull"
        and htf_trend != "bear"
        and long_trigger
        and not long_extension
        and rsi_last < 72.0
        and not (news_bias and getattr(news_bias, "active", False))
    ):
        signal = "buy"
        strength = 3 if bull_score >= 15 and gap >= 5 else 2
    elif (
        bear_score >= 12
        and bear_score >= bull_score + 4
        and str(stack.get("status") or "neutral") == "bear"
        and htf_trend != "bull"
        and short_trigger
        and not short_extension
        and rsi_last > 28.0
    ):
        signal = "sell"
        strength = 3 if bear_score >= 15 and gap >= 5 else 2

    if strength < 3:
        signal = "none"
        strength = 0

    detail = (
        f"stack {stack.get('status')} B{bull_score}/S{bear_score}"
        f" | EMA={ema_status} SM={smart_status} HTF={htf_trend}"
        f" | RSI={rsi_last:.1f} ATR={atr_last:.4f}{bias_note}"
    )

    meta = {
        "scores": scores,
        "htf_trend": htf_trend,
        "stack": stack,
        "ema_status": ema_status,
        "smart_status": smart_status,
        "rsi": rsi_last,
        "atr": atr_last,
        "long_extension": long_extension,
        "short_extension": short_extension,
        "news_bias": news_bias,
    }
    return signal, strength, detail, meta
