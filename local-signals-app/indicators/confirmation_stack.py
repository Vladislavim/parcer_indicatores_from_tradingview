from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from indicators.base import IndicatorBase, Signal
from indicators.runtime import run_indicator_get_signal


def _series_from_candles(candles) -> Tuple[List[int], List[float], List[float], List[float], List[float], List[float]]:
    ts: List[int] = []
    opens: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    volumes: List[float] = []
    for c in candles:
        if hasattr(c, "c"):
            ts.append(int(c.ts))
            opens.append(float(c.o))
            highs.append(float(c.h))
            lows.append(float(c.l))
            closes.append(float(c.c))
            volumes.append(float(c.v))
        else:
            ts.append(int(c[0]))
            opens.append(float(c[1]))
            highs.append(float(c[2]))
            lows.append(float(c[3]))
            closes.append(float(c[4]))
            volumes.append(float(c[5] if len(c) > 5 else 0.0))
    return ts, opens, highs, lows, closes, volumes


def _ema_series(values: List[float], length: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (max(1, length) + 1.0)
    out: List[float] = []
    ema = float(values[0])
    for v in values:
        ema = ema + alpha * (float(v) - ema)
        out.append(ema)
    return out


def _sma_series(values: List[float], length: int) -> List[float]:
    out: List[float] = []
    window: List[float] = []
    total = 0.0
    n = max(1, int(length))
    for v in values:
        fv = float(v)
        window.append(fv)
        total += fv
        if len(window) > n:
            total -= window.pop(0)
        out.append(total / len(window))
    return out


def _wma_series(values: List[float], length: int) -> List[float]:
    out: List[float] = []
    n = max(1, int(length))
    weights = list(range(1, n + 1))
    weight_sum = sum(weights)
    for i in range(len(values)):
        start = max(0, i - n + 1)
        window = [float(x) for x in values[start : i + 1]]
        w = weights[-len(window) :]
        out.append(sum(a * b for a, b in zip(window, w)) / sum(w if len(window) < n else weights))
    return out


def _rma_series(values: List[float], length: int) -> List[float]:
    if not values:
        return []
    n = max(1, int(length))
    out: List[float] = []
    acc = float(values[0])
    out.append(acc)
    for v in values[1:]:
        acc = ((acc * (n - 1)) + float(v)) / n
        out.append(acc)
    return out


def _rolling_max(values: List[float], length: int) -> List[float]:
    out: List[float] = []
    n = max(1, int(length))
    for i in range(len(values)):
        out.append(max(values[max(0, i - n + 1) : i + 1]))
    return out


def _rolling_min(values: List[float], length: int) -> List[float]:
    out: List[float] = []
    n = max(1, int(length))
    for i in range(len(values)):
        out.append(min(values[max(0, i - n + 1) : i + 1]))
    return out


def _rsi_series(values: List[float], length: int = 14) -> List[float]:
    if not values:
        return []
    n = max(1, int(length))
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(values)):
        delta = float(values[i]) - float(values[i - 1])
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = _rma_series(gains, n)
    avg_loss = _rma_series(losses, n)
    out: List[float] = []
    for g, l in zip(avg_gain, avg_loss):
        if l <= 1e-12:
            out.append(100.0 if g > 0 else 50.0)
        else:
            rs = g / l
            out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def _atr_series(highs: List[float], lows: List[float], closes: List[float], length: int = 14, use_sma: bool = False) -> List[float]:
    tr: List[float] = []
    for i in range(len(closes)):
        if i == 0:
            tr.append(float(highs[i]) - float(lows[i]))
        else:
            tr.append(
                max(
                    float(highs[i]) - float(lows[i]),
                    abs(float(highs[i]) - float(closes[i - 1])),
                    abs(float(lows[i]) - float(closes[i - 1])),
                )
            )
    return _sma_series(tr, length) if use_sma else _rma_series(tr, length)


def _mfi_series(highs: List[float], lows: List[float], closes: List[float], volumes: List[float], length: int = 14) -> List[float]:
    typical = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    pos = [0.0]
    neg = [0.0]
    for i in range(1, len(typical)):
        flow = typical[i] * max(0.0, volumes[i])
        if typical[i] > typical[i - 1]:
            pos.append(flow)
            neg.append(0.0)
        elif typical[i] < typical[i - 1]:
            pos.append(0.0)
            neg.append(flow)
        else:
            pos.append(0.0)
            neg.append(0.0)
    pos_sum = _sma_series(pos, length)
    neg_sum = _sma_series(neg, length)
    out: List[float] = []
    for p, n in zip(pos_sum, neg_sum):
        if n <= 1e-12:
            out.append(100.0 if p > 0 else 50.0)
        else:
            ratio = p / n
            out.append(100.0 - (100.0 / (1.0 + ratio)))
    return out


def _signal_dict(status: str, detail: str, *, bull: bool = False, bear: bool = False) -> Dict[str, Any]:
    return {
        "status": status,
        "detail": detail,
        "bull_signal": bull,
        "bear_signal": bear,
    }


def analyze_alpha_trend(candles) -> Dict[str, Any]:
    _, _, highs, lows, closes, volumes = _series_from_candles(candles)
    if len(closes) < 30:
        return _signal_dict("neutral", "AlphaTrend: not enough candles")

    ap = 14
    coeff = 1.0
    atr = _sma_series(_atr_series(highs, lows, closes, ap), 1)
    rsi = _rsi_series(closes, ap)
    use_volume = any(v > 0 for v in volumes)
    mfi = _mfi_series(highs, lows, closes, volumes, ap) if use_volume else [50.0] * len(closes)

    alpha = [0.0 for _ in closes]
    for i in range(len(closes)):
        up_t = lows[i] - atr[i] * coeff
        down_t = highs[i] + atr[i] * coeff
        prev = alpha[i - 1] if i > 0 else 0.0
        gate = mfi[i] >= 50.0 if use_volume else rsi[i] >= 50.0
        if gate:
            alpha[i] = max(prev, up_t)
        else:
            alpha[i] = min(prev, down_t)

    bull = False
    bear = False
    if len(alpha) >= 5:
        bull = alpha[-2] <= alpha[-4] and alpha[-1] > alpha[-3]
        bear = alpha[-2] >= alpha[-4] and alpha[-1] < alpha[-3]

    if alpha[-1] > alpha[-3]:
        status = "bull"
    elif alpha[-1] < alpha[-3]:
        status = "bear"
    else:
        status = "neutral"
    detail = f"AlphaTrend {'up' if status == 'bull' else 'down' if status == 'bear' else 'flat'}"
    return _signal_dict(status, detail, bull=bull, bear=bear)


def _qqe_core(closes: List[float], rsi_period: int = 14, sf: int = 5, qqe_factor: float = 4.238) -> Dict[str, Any]:
    if len(closes) < 80:
        return _signal_dict("neutral", "QQE: not enough candles")

    rsi = _rsi_series(closes, rsi_period)
    rsi_ma = _ema_series(rsi, sf)
    wilders = rsi_period * 2 - 1
    atr_rsi = [0.0]
    for i in range(1, len(rsi_ma)):
        atr_rsi.append(abs(rsi_ma[i] - rsi_ma[i - 1]))
    ma_atr_rsi = _ema_series(atr_rsi, wilders)
    dar = [x * qqe_factor for x in _ema_series(ma_atr_rsi, wilders)]

    longband: List[float] = []
    shortband: List[float] = []
    trend: List[int] = []
    fast_tl: List[float] = []
    qqe_long_count = 0
    qqe_short_count = 0
    qqe_long = False
    qqe_short = False

    for i in range(len(rsi_ma)):
        new_short = rsi_ma[i] + dar[i]
        new_long = rsi_ma[i] - dar[i]

        if i == 0:
            lb = new_long
            sb = new_short
            tr = 1
        else:
            prev_lb = longband[-1]
            prev_sb = shortband[-1]
            lb = max(prev_lb, new_long) if rsi_ma[i - 1] > prev_lb and rsi_ma[i] > prev_lb else new_long
            sb = min(prev_sb, new_short) if rsi_ma[i - 1] < prev_sb and rsi_ma[i] < prev_sb else new_short
            if rsi_ma[i - 1] <= prev_sb and rsi_ma[i] > prev_sb:
                tr = 1
            elif prev_lb >= rsi_ma[i - 1] and lb < rsi_ma[i]:
                tr = -1
            else:
                tr = trend[-1]
        longband.append(lb)
        shortband.append(sb)
        trend.append(tr)
        tl = lb if tr == 1 else sb
        fast_tl.append(tl)

        if tl < rsi_ma[i]:
            qqe_long_count += 1
            qqe_short_count = 0
        elif tl > rsi_ma[i]:
            qqe_short_count += 1
            qqe_long_count = 0
        else:
            qqe_long_count = 0
            qqe_short_count = 0

        if i == len(rsi_ma) - 1:
            qqe_long = qqe_long_count == 1
            qqe_short = qqe_short_count == 1

    if rsi_ma[-1] > fast_tl[-1]:
        status = "bull"
    elif rsi_ma[-1] < fast_tl[-1]:
        status = "bear"
    else:
        status = "neutral"
    detail = f"QQE {'bull' if status == 'bull' else 'bear' if status == 'bear' else 'flat'}"
    return _signal_dict(status, detail, bull=qqe_long, bear=qqe_short)


def analyze_qqe_signals(candles) -> Dict[str, Any]:
    _, _, _, _, closes, _ = _series_from_candles(candles)
    return _qqe_core(closes, 14, 5, 4.238)


def analyze_smart_qqe(candles) -> Dict[str, Any]:
    _, _, _, _, closes, _ = _series_from_candles(candles)
    res = _qqe_core(closes, 14, 5, 4.238)
    res["detail"] = res["detail"].replace("QQE", "Smart QQE")
    return res


def analyze_twin_range_filter(candles) -> Dict[str, Any]:
    _, _, _, _, closes, _ = _series_from_candles(candles)
    if len(closes) < 80:
        return _signal_dict("neutral", "Twin Range: not enough candles")

    def smoothrng(values: List[float], period: int, mult: float) -> List[float]:
        avrng = _ema_series([0.0] + [abs(values[i] - values[i - 1]) for i in range(1, len(values))], period)
        return [x * mult for x in _ema_series(avrng, period * 2 - 1)]

    fast = smoothrng(closes, 27, 1.6)
    slow = smoothrng(closes, 55, 2.0)
    smrng = [(a + b) / 2.0 for a, b in zip(fast, slow)]

    filt: List[float] = []
    upward: List[int] = []
    downward: List[int] = []
    long_sig = False
    short_sig = False
    cond_ini = 0

    for i, close in enumerate(closes):
        prev_f = filt[-1] if filt else close
        r = smrng[i]
        if close > prev_f:
            f = prev_f if close - r < prev_f else close - r
        else:
            f = prev_f if close + r > prev_f else close + r
        filt.append(f)

        up_count = (upward[-1] + 1) if upward and f > filt[-2] else 0 if upward and f < filt[-2] else (upward[-1] if upward else 0)
        dn_count = (downward[-1] + 1) if downward and f < filt[-2] else 0 if downward and f > filt[-2] else (downward[-1] if downward else 0)
        upward.append(up_count)
        downward.append(dn_count)

        long_cond = close > f and up_count > 0
        short_cond = close < f and dn_count > 0
        prev_cond = cond_ini
        cond_ini = 1 if long_cond else -1 if short_cond else cond_ini
        if i == len(closes) - 1:
            long_sig = long_cond and prev_cond == -1
            short_sig = short_cond and prev_cond == 1

    if closes[-1] > filt[-1]:
        status = "bull"
    elif closes[-1] < filt[-1]:
        status = "bear"
    else:
        status = "neutral"
    detail = f"Twin Range {'bull' if status == 'bull' else 'bear' if status == 'bear' else 'flat'}"
    return _signal_dict(status, detail, bull=long_sig, bear=short_sig)


def analyze_turtle_trade_channels(candles) -> Dict[str, Any]:
    _, _, highs, lows, closes, _ = _series_from_candles(candles)
    if len(closes) < 30:
        return _signal_dict("neutral", "Turtle Channels: not enough candles")

    length = 20
    upper = _rolling_max(highs, length)
    lower = _rolling_min(lows, length)
    buy_sig = len(highs) > 1 and highs[-1] >= upper[-2]
    sell_sig = len(lows) > 1 and lows[-1] <= lower[-2]

    if closes[-1] >= (upper[-1] + lower[-1]) / 2.0:
        status = "bull"
    elif closes[-1] <= (upper[-1] + lower[-1]) / 2.0:
        status = "bear"
    else:
        status = "neutral"
    detail = f"Turtle {'breakout up' if buy_sig else 'breakout down' if sell_sig else status}"
    return _signal_dict(status, detail, bull=buy_sig, bear=sell_sig)


def analyze_ualgo_trend(candles) -> Dict[str, Any]:
    _, opens, highs, lows, closes, _ = _series_from_candles(candles)
    if len(closes) < 40:
        return _signal_dict("neutral", "UAlgo: not enough candles")

    src = [(h + l) / 2.0 for h, l in zip(highs, lows)]
    atr = _atr_series(highs, lows, closes, 10, use_sma=False)
    mult = 2.0
    up: List[float] = []
    dn: List[float] = []
    trend: List[int] = []
    buy_sig = False
    sell_sig = False

    for i in range(len(closes)):
        up_i = src[i] - (mult * atr[i])
        dn_i = src[i] + (mult * atr[i])
        if i > 0:
            up_prev = up[-1]
            dn_prev = dn[-1]
            if closes[i - 1] > up_prev:
                up_i = max(up_i, up_prev)
            if closes[i - 1] < dn_prev:
                dn_i = min(dn_i, dn_prev)
            t = trend[-1]
            if t == -1 and closes[i] > dn_prev:
                t = 1
            elif t == 1 and closes[i] < up_prev:
                t = -1
        else:
            t = 1
        up.append(up_i)
        dn.append(dn_i)
        trend.append(t)
        if i == len(closes) - 1 and len(trend) >= 2:
            buy_sig = trend[-1] == 1 and trend[-2] == -1
            sell_sig = trend[-1] == -1 and trend[-2] == 1

    status = "bull" if trend[-1] == 1 else "bear"
    detail = f"UAlgo {'bull' if status == 'bull' else 'bear'}"
    return _signal_dict(status, detail, bull=buy_sig, bear=sell_sig)


def analyze_zero_lag(candles) -> Dict[str, Any]:
    _, _, highs, lows, closes, _ = _series_from_candles(candles)
    if len(closes) < 140:
        return _signal_dict("neutral", "Zero Lag: not enough candles")

    length = 50
    volatility_mult = 1.5
    loop_start = 1
    loop_end = 70
    threshold_up = 5
    threshold_down = -5

    lag = max(1, (length - 1) // 2)
    basis_input: List[float] = []
    for i, close in enumerate(closes):
        shifted = closes[i - lag] if i >= lag else close
        basis_input.append(close + (close - shifted))
    zl_basis = _ema_series(basis_input, length)
    atr = _atr_series(highs, lows, closes, length, use_sma=False)
    vol_base = _rolling_max(atr, length * 3)
    volatility = [x * volatility_mult for x in vol_base]

    trend: List[int] = []
    long_sig = False
    short_sig = False
    for i in range(len(closes)):
        score = 0.0
        for j in range(loop_start, loop_end + 1):
            if i - j < 0:
                continue
            score += 1.0 if zl_basis[i] > zl_basis[i - j] else -1.0
        is_long = score > threshold_up and closes[i] > zl_basis[i] + volatility[i]
        is_short = score < threshold_down and closes[i] < zl_basis[i] - volatility[i]
        if not trend:
            t = 0
        else:
            t = trend[-1]
        if is_long:
            t = 1
        elif is_short:
            t = -1
        trend.append(t)
        if i == len(closes) - 1 and len(trend) >= 2:
            long_sig = trend[-1] == 1 and trend[-2] != 1
            short_sig = trend[-1] == -1 and trend[-2] != -1

    status = "bull" if trend[-1] == 1 else "bear" if trend[-1] == -1 else "neutral"
    detail = f"Zero Lag {'bull' if status == 'bull' else 'bear' if status == 'bear' else 'flat'}"
    return _signal_dict(status, detail, bull=long_sig, bear=short_sig)


def analyze_confirmation_stack(candles) -> Dict[str, Any]:
    modules = {
        "alpha_trend": analyze_alpha_trend(candles),
        "zero_lag": analyze_zero_lag(candles),
        "qqe": analyze_qqe_signals(candles),
        "smart_qqe": analyze_smart_qqe(candles),
        "twin_range": analyze_twin_range_filter(candles),
        "turtle": analyze_turtle_trade_channels(candles),
        "ualgo": analyze_ualgo_trend(candles),
    }
    weights = {
        "alpha_trend": 2,
        "zero_lag": 2,
        "qqe": 1,
        "smart_qqe": 1,
        "twin_range": 1,
        "turtle": 1,
        "ualgo": 1,
    }

    bull_score = sum(weights[k] for k, v in modules.items() if v["status"] == "bull")
    bear_score = sum(weights[k] for k, v in modules.items() if v["status"] == "bear")
    bull_names = [k for k, v in modules.items() if v["status"] == "bull"]
    bear_names = [k for k, v in modules.items() if v["status"] == "bear"]

    if bull_score >= 4 and bull_score > bear_score + 1:
        status = "bull"
        detail = "Confirmations bull: " + ", ".join(bull_names[:4])
    elif bear_score >= 4 and bear_score > bull_score + 1:
        status = "bear"
        detail = "Confirmations bear: " + ", ".join(bear_names[:4])
    else:
        status = "neutral"
        detail = f"Confirmations mixed B{bull_score}/S{bear_score}"

    bull_signal = any(modules[k]["bull_signal"] for k in ("alpha_trend", "zero_lag")) or (
        sum(1 for v in modules.values() if v["bull_signal"]) >= 2
    )
    bear_signal = any(modules[k]["bear_signal"] for k in ("alpha_trend", "zero_lag")) or (
        sum(1 for v in modules.values() if v["bear_signal"]) >= 2
    )
    return {
        "status": status,
        "detail": detail,
        "bull_signal": bull_signal and status == "bull",
        "bear_signal": bear_signal and status == "bear",
        "modules": modules,
        "bull_score": bull_score,
        "bear_score": bear_score,
    }


def analyze_confirmation_stack_ohlcv(ohlcv) -> Dict[str, Any]:
    return analyze_confirmation_stack(ohlcv)


class ConfirmationStackIndicator(IndicatorBase):
    name = "Confirmation Stack (AlphaTrend/QQE/ZeroLag)"

    @staticmethod
    def default_params() -> Dict[str, Any]:
        return {}

    def compute(self, candles, state: Dict[str, Any], params: Dict[str, Any]) -> List[Signal]:
        if len(candles) < 140:
            return []

        analysis = analyze_confirmation_stack(candles)
        state["stack_status"] = analysis["status"]
        state["stack_detail"] = analysis["detail"]
        state["stack_modules"] = analysis["modules"]

        prev_status = str(state.get("last_emitted_status") or "neutral")
        out: List[Signal] = []
        if analysis["status"] == "bull" and prev_status != "bull" and analysis["bull_signal"]:
            out.append(
                Signal(
                    type="BUY",
                    name="Confirmations",
                    message=analysis["detail"],
                    ts_ms=int(candles[-1].ts if hasattr(candles[-1], "ts") else candles[-1][0]),
                )
            )
        elif analysis["status"] == "bear" and prev_status != "bear" and analysis["bear_signal"]:
            out.append(
                Signal(
                    type="SELL",
                    name="Confirmations",
                    message=analysis["detail"],
                    ts_ms=int(candles[-1].ts if hasattr(candles[-1], "ts") else candles[-1][0]),
                )
            )
        state["last_emitted_status"] = analysis["status"]
        return out


_INDICATOR = ConfirmationStackIndicator()


def _status_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    return str(state.get("stack_status") or "neutral")


def _detail_from_state(state: Dict[str, Any], _candles) -> Optional[str]:
    return str(state.get("stack_detail") or "Confirmations mixed")


def get_signal(symbol: str, timeframe: str, source: str):
    return run_indicator_get_signal(
        _INDICATOR,
        "confirmations",
        symbol,
        timeframe,
        source,
        status_from_state=_status_from_state,
        detail_from_state=_detail_from_state,
    )
