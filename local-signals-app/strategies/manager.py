"""
РњРµРЅРµРґР¶РµСЂ СЃС‚СЂР°С‚РµРіРёР№ - СѓРїСЂР°РІР»СЏРµС‚ РЅРµСЃРєРѕР»СЊРєРёРјРё СЃС‚СЂР°С‚РµРіРёСЏРјРё РїР°СЂР°Р»Р»РµР»СЊРЅРѕ
"""
from typing import Dict, List, Optional
import time
from PySide6.QtCore import QThread, Signal as QtSignal
from .base import BaseStrategy, TradeSignal, Signal
from .trend_following import TrendFollowingStrategy
from .breakout import BreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .scalping import ScalpingStrategy
from .swing import SwingStrategy
from .adaptive_regime import AdaptiveRegimeStrategy
from .gold_btc_inverse import GoldBtcInverseStrategy


# Р’СЃРµ РґРѕСЃС‚СѓРїРЅС‹Рµ СЃС‚СЂР°С‚РµРіРёРё
STRATEGIES = {
    "adaptive_regime": AdaptiveRegimeStrategy,
    "gold_btc_inverse": GoldBtcInverseStrategy,
    "trend_following": TrendFollowingStrategy,
    "breakout": BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "scalping": ScalpingStrategy,
    "swing": SwingStrategy,
}


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
        })
    return result


class StrategyWorker(QThread):
    """Р’РѕСЂРєРµСЂ РґР»СЏ РѕРґРЅРѕР№ СЃС‚СЂР°С‚РµРіРёРё"""
    log_signal = QtSignal(str, str)  # message, strategy_id
    trade_signal = QtSignal(str, str, str, float, float, float, float, str)  # strategy_id, symbol, side, size, sl, tp, leverage, reason
    close_signal = QtSignal(str, str, str)  # strategy_id, symbol, reason
    
    def __init__(self, exchange, strategy_id: str, coins: List[str], risk_pct: float, leverage: int):
        super().__init__()
        self.exchange = exchange
        self.strategy_id = strategy_id
        self.coins = coins
        self.risk_pct = max(0.5, min(float(risk_pct), 5.0))
        self.leverage = max(5, min(int(leverage), 10))
        self._stop = False
        
        # РЎРѕР·РґР°С‘Рј СЃС‚СЂР°С‚РµРіРёСЋ
        strategy_cls = STRATEGIES.get(strategy_id)
        if strategy_cls:
            self.strategy = strategy_cls(exchange)
        else:
            self.strategy = None
            
    def stop(self):
        self._stop = True
        
    def run(self):
        if not self.strategy or not self.exchange:
            return
            
        try:
            self._check_signals()
        except Exception as e:
            self.log_signal.emit(f"вљ пёЏ РћС€РёР±РєР°: {e}", self.strategy_id)
            
    def _check_signals(self):
        """РџСЂРѕРІРµСЂСЏРµС‚ СЃРёРіРЅР°Р»С‹ РїРѕ СЃС‚СЂР°С‚РµРіРёРё"""
        # РџРѕР»СѓС‡Р°РµРј Р±Р°Р»Р°РЅСЃ
        try:
            balance = self.exchange.fetch_balance()
            available = float(balance.get('USDT', {}).get('free') or 0)
        except:
            return
            
        if available < 10:
            return
            
        # РџРѕР»СѓС‡Р°РµРј РѕС‚РєСЂС‹С‚С‹Рµ РїРѕР·РёС†РёРё
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]
        except:
            open_positions = []
        open_position_coins = set()
        for p in open_positions:
            symbol_raw = str(p.get('symbol') or '')
            if not symbol_raw:
                continue
            if '/' in symbol_raw:
                coin_key = symbol_raw.split('/')[0]
            else:
                coin_key = symbol_raw.split(':')[0].replace("USDT", "")
            if coin_key:
                open_position_coins.add(coin_key)
        
        # РќР• Р·Р°РєСЂС‹РІР°РµРј РїРѕР·РёС†РёРё Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё вЂ” СЌС‚Рѕ РґРµР»Р°РµС‚ SL/TP РЅР° Р±РёСЂР¶Рµ
        # РЎС‚СЂР°С‚РµРіРёСЏ С‚РѕР»СЊРєРѕ РћРўРљР Р«Р’РђР•Рў РїРѕР·РёС†РёРё, Р·Р°РєСЂС‹С‚РёРµ вЂ” С‡РµСЂРµР· Р±РёСЂР¶РµРІС‹Рµ РѕСЂРґРµСЂР°
        
        # РџСЂРѕРІРµСЂСЏРµРј СЃРёРіРЅР°Р»С‹ РґР»СЏ РЅРѕРІС‹С… РїРѕР·РёС†РёР№
        ordered_coins = list(self.coins)
        if ordered_coins:
            offset = (abs(hash(self.strategy_id)) + int(time.time() // 60)) % len(ordered_coins)
            ordered_coins = ordered_coins[offset:] + ordered_coins[:offset]
        skipped_busy = 0
        opened_in_cycle = False
        for coin in ordered_coins:
            if self._stop:
                return
                
            symbol = f"{coin}/USDT:USDT"
                
            # РџРѕР»СѓС‡Р°РµРј СЃРёРіРЅР°Р»
            trade = self.strategy.get_signal(symbol)
            if not trade or trade.signal == Signal.NONE:
                continue

            if coin in open_position_coins:
                skipped_busy += 1
                continue

            # РџСЂРѕРїСѓСЃРєР°РµРј РІС…РѕРґ РІ РјРѕРјРµРЅС‚ СЂР°СЃС€РёСЂРµРЅРЅРѕРіРѕ СЃРїСЂРµРґР°
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                bid = float(ticker.get('bid') or 0)
                ask = float(ticker.get('ask') or 0)
                last = float(ticker.get('last') or trade.entry_price or 0)
                if bid > 0 and ask > 0 and last > 0:
                    spread_pct = ((ask - bid) / last) * 100.0
                    if spread_pct > 0.12:
                        self.log_signal.emit(
                            f"вљ пёЏ {coin}: РїСЂРѕРїСѓСЃРє РІС…РѕРґР°, РІС‹СЃРѕРєРёР№ СЃРїСЂРµРґ {spread_pct:.2f}%",
                            self.strategy_id
                        )
                        continue
            except Exception:
                pass
                
            # Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј СЂР°Р·РјРµСЂ РїРѕР·РёС†РёРё
            position_usdt = available * (self.risk_pct / 100)
            position_usdt = min(position_usdt, available * 0.30)
            size = (position_usdt * self.leverage) / trade.entry_price
            
            # РћРєСЂСѓРіР»СЏРµРј
            if coin == "BTC":
                size = round(size, 3)
            elif coin in ["ETH", "SOL"]:
                size = round(size, 2)
            else:
                size = round(size, 1)
                
            notional_usdt = size * trade.entry_price
            if size < 0.001 or notional_usdt < 5:
                continue
            
            # РћС‚РїСЂР°РІР»СЏРµРј СЃРёРіРЅР°Р» РЅР° РѕС‚РєСЂС‹С‚РёРµ
            side = "buy" if trade.signal == Signal.BUY else "sell"
            self.trade_signal.emit(
                self.strategy_id,
                symbol,
                side,
                size,
                trade.sl_price,
                trade.tp_price,
                self.leverage,
                trade.reason
            )
            open_position_coins.add(coin)
            opened_in_cycle = True
            break

        if not opened_in_cycle and skipped_busy > 0:
            self.log_signal.emit(
                f"⚠️ Монеты заняты: {skipped_busy}. Проверил другие символы, входов нет",
                self.strategy_id
            )


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
