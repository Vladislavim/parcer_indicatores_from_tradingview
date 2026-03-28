from __future__ import annotations

from typing import Optional, Tuple

from core.bybit_news import BybitAnnouncementFeed
from core.signal_fusion import build_weighted_signal

from .base import StrategyConfig, TradeSignal
from .order_block_strategies import _TradingViewStrategyBase


PROTECTED_BLEND_CONFIG = StrategyConfig(
    name="Protected Indicator Blend",
    description="Risk-first blend of the existing indicator stack with stricter confirmation and calmer sizing.",
    timeframe="1h",
    sl_pct=0.8,
    tp_pct=1.8,
    risk_reward="1:2.2",
    avg_monthly_return="6-14%",
    win_rate="49-61%",
    trades_per_month="4-12",
    risk_level="Low",
)

DELISTING_SHORT_CONFIG = StrategyConfig(
    name="Bybit Delisting Short",
    description="Official Bybit delisting announcements + bearish indicator confirmation + forced safety window.",
    timeframe="1h",
    sl_pct=1.0,
    tp_pct=2.4,
    risk_reward="1:2.4",
    avg_monthly_return="event-driven",
    win_rate="n/a",
    trades_per_month="0-3",
    risk_level="Medium",
)


class _EventStrategyBase(_TradingViewStrategyBase):
    strategy_group = "Комбо-стратегии"

    def __init__(self, exchange, config: StrategyConfig):
        super().__init__(exchange, config)
        self.news_feed = BybitAnnouncementFeed(ttl_sec=300, pages=2)

    def _htf_trend(self, symbol: str) -> str:
        htf = self._fetch(symbol, "4h", 240)
        if len(htf) < 180:
            return "neutral"
        closes = [float(x[4]) for x in htf]
        ema50 = self.calc_ema(closes, 50)
        ema200 = self.calc_ema(closes, 200)
        if not ema50 or not ema200:
            return "neutral"
        if closes[-1] > ema50[-1] and ema50[-1] > ema200[-1]:
            return "bull"
        if closes[-1] < ema50[-1] and ema50[-1] < ema200[-1]:
            return "bear"
        return "neutral"

    def should_close(self, symbol: str, position_side: str, entry_price: float) -> Tuple[bool, str]:
        return False, ""


class ProtectedIndicatorBlendStrategy(_EventStrategyBase):
    sort_order = 5

    def __init__(self, exchange):
        super().__init__(exchange, PROTECTED_BLEND_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self._fetch(symbol, self.config.timeframe, 260)
        if len(ohlcv) < 180:
            return None

        coin = symbol.split("/")[0]
        htf_trend = self._htf_trend(symbol)
        news_bias = self.news_feed.get_symbol_bias(coin)
        signal, strength, details, _ = build_weighted_signal(
            self.exchange,
            symbol,
            self.config.timeframe,
            htf_trend=htf_trend,
            news_bias=news_bias,
        )
        if signal not in {"buy", "sell"} or strength < 3:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, signal, 16, atr)
        rr = 2.4 if signal == "sell" and news_bias and news_bias.active else 2.2
        tp = self._rr_target(entry, sl, signal, rr)
        target_extreme = self._recent_target_extreme(ohlcv, signal, 28, atr)
        tp = max(tp, target_extreme) if signal == "buy" else min(tp, target_extreme)

        reason = f"Protected blend | {details}"
        return self._build_trade(side=signal, entry=entry, sl=sl, tp=tp, reason=reason, strength=84)


class BybitDelistingShortStrategy(_EventStrategyBase):
    sort_order = 6

    def __init__(self, exchange):
        super().__init__(exchange, DELISTING_SHORT_CONFIG)

    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        coin = symbol.split("/")[0]
        news_bias = self.news_feed.get_symbol_bias(coin)
        if not news_bias or not news_bias.active or news_bias.hard_block:
            return None
        if news_bias.hours_to_delist < 8 or news_bias.hours_since_publish > 72:
            return None

        htf_trend = self._htf_trend(symbol)
        if htf_trend != "bear":
            return None

        ohlcv = self._fetch(symbol, self.config.timeframe, 260)
        if len(ohlcv) < 180:
            return None

        signal, strength, details, _ = build_weighted_signal(
            self.exchange,
            symbol,
            self.config.timeframe,
            htf_trend=htf_trend,
            news_bias=news_bias,
        )
        if signal != "sell" or strength < 3:
            return None

        entry = self._price(ohlcv)
        atr = self._atr_value(ohlcv)
        sl = self._recent_swing_stop(ohlcv, "sell", 12, atr)
        tp = min(
            self._rr_target(entry, sl, "sell", 2.4),
            self._recent_target_extreme(ohlcv, "sell", 30, atr),
        )
        reason = f"Bybit delisting short | {news_bias.reason} | {details}"
        return self._build_trade(side="sell", entry=entry, sl=sl, tp=tp, reason=reason, strength=88)
