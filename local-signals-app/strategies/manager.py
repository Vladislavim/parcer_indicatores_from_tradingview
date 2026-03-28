"""
РњРµРЅРµРґР¶РµСЂ СЃС‚СЂР°С‚РµРіРёР№ - СѓРїСЂР°РІР»СЏРµС‚ РЅРµСЃРєРѕР»СЊРєРёРјРё СЃС‚СЂР°С‚РµРіРёСЏРјРё РїР°СЂР°Р»Р»РµР»СЊРЅРѕ
"""
from typing import Dict, List, Optional
import time
from PySide6.QtCore import QThread, Signal as QtSignal
from core.bybit_news import BybitAnnouncementFeed
from core.trading import build_risk_plan, market_gate_from_ticker
from .base import BaseStrategy, TradeSignal, Signal
from .event_driven_strategies import (
    BybitDelistingShortStrategy,
    ProtectedIndicatorBlendStrategy,
)
from .order_block_strategies import (
    AlphaTrendSoloStrategy,
    EmaMarketStructureSoloStrategy,
    HtfOrderBlockStrategy,
    LiquidityReturnOrderBlockStrategy,
    ProfitStackComboStrategy,
    SmartMoneyBreakoutSoloStrategy,
    SmartMoneyEmaComboStrategy,
    TrendEngineComboStrategy,
    ZeroLagSoloStrategy,
)


# Р’СЃРµ РґРѕСЃС‚СѓРїРЅС‹Рµ СЃС‚СЂР°С‚РµРіРёРё
STRATEGIES = {
    "protected_indicator_blend": ProtectedIndicatorBlendStrategy,
    "bybit_delisting_short": BybitDelistingShortStrategy,
    "htf_order_block": HtfOrderBlockStrategy,
    "liquidity_order_block": LiquidityReturnOrderBlockStrategy,
    "smart_money_breakout_solo": SmartMoneyBreakoutSoloStrategy,
    "ema_market_structure_solo": EmaMarketStructureSoloStrategy,
    "alpha_trend_solo": AlphaTrendSoloStrategy,
    "zero_lag_solo": ZeroLagSoloStrategy,
    "smart_money_ema_combo": SmartMoneyEmaComboStrategy,
    "trend_engine_combo": TrendEngineComboStrategy,
    "profit_stack_combo": ProfitStackComboStrategy,
}


def _fetch_balance_safe(exchange):
    """Bybit-safe balance fetch with linear/futures-first params."""
    last_err = None
    attempts = [
        {"type": "swap"},
        {"category": "linear"},
        {"type": "future"},
        {"accountType": "UNIFIED"},
        {},
    ]
    for params in attempts:
        try:
            return exchange.fetch_balance(params)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return exchange.fetch_balance()


def get_all_strategies() -> List[dict]:
    """РџРѕР»СѓС‡РёС‚СЊ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ РІСЃРµС… СЃС‚СЂР°С‚РµРіРёСЏС…"""
    result = []
    for key, cls in STRATEGIES.items():
        # РЎРѕР·РґР°С‘Рј РІСЂРµРјРµРЅРЅС‹Р№ СЌРєР·РµРјРїР»СЏСЂ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РєРѕРЅС„РёРіР°
        instance = cls(None)
        config = instance.config
        result.append({
            "id": key,
            "name": config.name,
            "description": config.description,
            "timeframe": config.timeframe,
            "sl_pct": config.sl_pct,
            "tp_pct": config.tp_pct,
            "risk_reward": config.risk_reward,
            "avg_monthly_return": config.avg_monthly_return,
            "win_rate": config.win_rate,
            "trades_per_month": config.trades_per_month,
            "risk_level": config.risk_level,
            "group": getattr(instance, "strategy_group", "Комбо-стратегии"),
            "group_hint": getattr(instance, "group_hint", ""),
            "sort_order": int(getattr(instance, "sort_order", 100)),
        })
    return sorted(result, key=lambda item: (str(item.get("group") or ""), int(item.get("sort_order") or 100)))


class StrategyWorker(QThread):
    """Worker that checks one strategy and emits a single protected entry."""
    log_signal = QtSignal(str, str)  # message, strategy_id
    trade_signal = QtSignal(str, str, str, float, float, float, float, str)  # strategy_id, symbol, side, size, sl, tp, leverage, reason
    close_signal = QtSignal(str, str, str)  # strategy_id, symbol, reason

    def __init__(
        self,
        exchange,
        strategy_id: str,
        coins: List[str],
        risk_pct: float,
        leverage: int,
        tracked_positions: Optional[Dict[str, dict]] = None,
    ):
        super().__init__()
        self.exchange = exchange
        self.strategy_id = strategy_id
        self.coins = coins
        self.risk_pct = max(0.25, min(float(risk_pct), 1.5))
        self.leverage = max(3, min(int(leverage), 7))
        self.tracked_positions = dict(tracked_positions or {})
        self._stop = False
        self.news_feed = BybitAnnouncementFeed(ttl_sec=300, pages=2)

        strategy_cls = STRATEGIES.get(strategy_id)
        self.strategy = strategy_cls(exchange) if strategy_cls else None

    def _emit_log(self, message: str):
        self.log_signal.emit(message, self.strategy_id)

    def _format_risk_block(self, coin: str, risk_plan) -> str:
        if risk_plan.reason == "portfolio risk limit reached":
            return (
                f"⚠️ {coin}: вход заблокирован, лимит портфельного риска "
                f"(${risk_plan.open_risk_usd:.2f}/${risk_plan.portfolio_risk_limit_usd:.2f})"
            )
        if risk_plan.reason.startswith("same-side alt cap reached"):
            return (
                f"⚠️ {coin}: вход заблокирован, уже открыто слишком много альтов "
                f"в ту же сторону ({risk_plan.same_side_alt_positions})"
            )
        return f"⚠️ {coin}: вход заблокирован, {risk_plan.reason}"

    def stop(self):
        self._stop = True

    def run(self):
        if not self.strategy or not self.exchange:
            return

        try:
            self._check_signals()
        except Exception as e:
            self._emit_log(f"⚠️ Ошибка стратегии: {e}")

    def _check_signals(self):
        try:
            balance = _fetch_balance_safe(self.exchange)
            usdt = balance.get("USDT", {})
            available = float(usdt.get("free") or 0)
            total_equity = float(usdt.get("total") or usdt.get("equity") or available)
        except Exception:
            return

        if available < 10:
            return

        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get("contracts") or 0) > 0]
        except Exception:
            open_positions = []

        ordered_coins = list(self.coins)
        if self.strategy_id == "bybit_delisting_short":
            try:
                event_coins = []
                for event in self.news_feed.get_delisting_events():
                    if event.hours_since_publish > 72:
                        continue
                    if event.hours_to_delist < 8 or event.hours_to_delist > 168:
                        continue
                    if event.symbol not in event_coins:
                        event_coins.append(event.symbol)
                ordered_coins = event_coins + ordered_coins
            except Exception:
                pass
        ordered_coins = list(dict.fromkeys([coin for coin in ordered_coins if coin]))
        if ordered_coins:
            offset = (abs(hash(self.strategy_id)) + int(time.time() // 60)) % len(ordered_coins)
            ordered_coins = ordered_coins[offset:] + ordered_coins[:offset]

        for coin in ordered_coins:
            if self._stop:
                return

            symbol = f"{coin}/USDT:USDT"
            trade = self.strategy.get_signal(symbol)
            if not trade or trade.signal == Signal.NONE:
                continue

            side = "buy" if trade.signal == Signal.BUY else "sell"
            news_bias = self.news_feed.get_symbol_bias(coin)
            if news_bias and news_bias.hard_block:
                self._emit_log(f"⚠️ {coin}: вход пропущен, news-block ({news_bias.reason})")
                continue
            if news_bias and news_bias.active and side == "buy":
                self._emit_log(f"⚠️ {coin}: лонг отменён, есть официальный notice о delisting от Bybit")
                continue

            try:
                ticker = self.exchange.fetch_ticker(symbol)
                gate = market_gate_from_ticker(
                    ticker,
                    max_spread_pct=0.10,
                    min_quote_volume=5_000_000,
                )
                if not gate.ok:
                    self._emit_log(f"⚠️ {coin}: вход пропущен, {gate.reason}")
                    continue
            except Exception:
                continue

            entry_price = float(ticker.get("last") or trade.entry_price or 0)
            risk_plan = build_risk_plan(
                exchange=self.exchange,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                stop_price=float(trade.sl_price or 0),
                leverage=self.leverage,
                risk_pct=self.risk_pct,
                available_balance=available,
                total_equity=total_equity,
                positions=open_positions,
                tracked_positions=self.tracked_positions,
                max_margin_pct=0.10,
                max_notional_pct=0.18,
                max_portfolio_risk_pct=0.0,
                max_same_side_alt_positions=0,
            )
            if not risk_plan.ok:
                self._emit_log(self._format_risk_block(coin, risk_plan))
                continue

            self.trade_signal.emit(
                self.strategy_id,
                symbol,
                side,
                float(risk_plan.size),
                trade.sl_price,
                trade.tp_price,
                self.leverage,
                f"{trade.reason} | risk={risk_plan.risk_amount_usd:.2f}$",
            )
            break


class MultiStrategyManager:
    """РњРµРЅРµРґР¶РµСЂ РґР»СЏ Р·Р°РїСѓСЃРєР° РЅРµСЃРєРѕР»СЊРєРёС… СЃС‚СЂР°С‚РµРіРёР№ РїР°СЂР°Р»Р»РµР»СЊРЅРѕ"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.workers: Dict[str, StrategyWorker] = {}
        self.active_strategies: Dict[str, dict] = {}  # strategy_id -> config
        
    def start_strategy(self, strategy_id: str, coins: List[str], risk_pct: float, leverage: int,
                       log_callback, trade_callback, close_callback) -> bool:
        """Р—Р°РїСѓСЃС‚РёС‚СЊ СЃС‚СЂР°С‚РµРіРёСЋ"""
        if strategy_id in self.workers:
            return False  # РЈР¶Рµ Р·Р°РїСѓС‰РµРЅР°
            
        worker = StrategyWorker(self.exchange, strategy_id, coins, risk_pct, leverage)
        worker.log_signal.connect(log_callback)
        worker.trade_signal.connect(trade_callback)
        worker.close_signal.connect(close_callback)
        
        self.workers[strategy_id] = worker
        self.active_strategies[strategy_id] = {
            "coins": coins,
            "risk_pct": risk_pct,
            "leverage": leverage
        }
        
        worker.start()
        return True
        
    def stop_strategy(self, strategy_id: str) -> bool:
        """РћСЃС‚Р°РЅРѕРІРёС‚СЊ СЃС‚СЂР°С‚РµРіРёСЋ"""
        if strategy_id not in self.workers:
            return False
            
        worker = self.workers[strategy_id]
        worker.stop()
        worker.wait(2000)
        
        del self.workers[strategy_id]
        del self.active_strategies[strategy_id]
        return True
        
    def stop_all(self):
        """РћСЃС‚Р°РЅРѕРІРёС‚СЊ РІСЃРµ СЃС‚СЂР°С‚РµРіРёРё"""
        for strategy_id in list(self.workers.keys()):
            self.stop_strategy(strategy_id)
            
    def run_check(self, strategy_id: str):
        """Р—Р°РїСѓСЃС‚РёС‚СЊ РїСЂРѕРІРµСЂРєСѓ РґР»СЏ СЃС‚СЂР°С‚РµРіРёРё"""
        if strategy_id not in self.active_strategies:
            return
            
        config = self.active_strategies[strategy_id]
        
        # РЎРѕР·РґР°С‘Рј РЅРѕРІС‹Р№ РІРѕСЂРєРµСЂ РґР»СЏ РїСЂРѕРІРµСЂРєРё
        if strategy_id in self.workers:
            old_worker = self.workers[strategy_id]
            if old_worker.isRunning():
                return  # Р•С‰С‘ СЂР°Р±РѕС‚Р°РµС‚
                
        # РџРµСЂРµР·Р°РїСѓСЃРєР°РµРј
        worker = self.workers.get(strategy_id)
        if worker and not worker.isRunning():
            worker.start()
            
    def is_running(self, strategy_id: str) -> bool:
        """РџСЂРѕРІРµСЂРёС‚СЊ Р·Р°РїСѓС‰РµРЅР° Р»Рё СЃС‚СЂР°С‚РµРіРёСЏ"""
        return strategy_id in self.workers
