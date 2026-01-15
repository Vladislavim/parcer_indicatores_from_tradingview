"""
Менеджер стратегий - управляет несколькими стратегиями параллельно
"""
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal as QtSignal
from .base import BaseStrategy, TradeSignal, Signal
from .trend_following import TrendFollowingStrategy
from .breakout import BreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .scalping import ScalpingStrategy
from .swing import SwingStrategy


# Все доступные стратегии
STRATEGIES = {
    "trend_following": TrendFollowingStrategy,
    "breakout": BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "scalping": ScalpingStrategy,
    "swing": SwingStrategy,
}


def get_all_strategies() -> List[dict]:
    """Получить информацию о всех стратегиях"""
    result = []
    for key, cls in STRATEGIES.items():
        # Создаём временный экземпляр для получения конфига
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
    """Воркер для одной стратегии"""
    log_signal = QtSignal(str, str)  # message, strategy_id
    trade_signal = QtSignal(str, str, str, float, float, float, float, str)  # strategy_id, symbol, side, size, sl, tp, leverage, reason
    close_signal = QtSignal(str, str, str)  # strategy_id, symbol, reason
    
    def __init__(self, exchange, strategy_id: str, coins: List[str], risk_pct: float, leverage: int):
        super().__init__()
        self.exchange = exchange
        self.strategy_id = strategy_id
        self.coins = coins
        self.risk_pct = risk_pct
        self.leverage = leverage
        self._stop = False
        
        # Создаём стратегию
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
            self.log_signal.emit(f"⚠️ Ошибка: {e}", self.strategy_id)
            
    def _check_signals(self):
        """Проверяет сигналы по стратегии"""
        # Получаем баланс
        try:
            balance = self.exchange.fetch_balance()
            available = float(balance.get('USDT', {}).get('free') or 0)
        except:
            return
            
        if available < 10:
            return
            
        # Получаем открытые позиции
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]
        except:
            open_positions = []
        
        # НЕ закрываем позиции автоматически — это делает SL/TP на бирже
        # Стратегия только ОТКРЫВАЕТ позиции, закрытие — через биржевые ордера
        
        # Проверяем сигналы для новых позиций
        for coin in self.coins:
            if self._stop:
                return
                
            symbol = f"{coin}/USDT:USDT"
            
            # Пропускаем если уже есть позиция
            has_position = any(
                p.get('symbol') == symbol and float(p.get('contracts') or 0) > 0
                for p in open_positions
            )
            if has_position:
                continue
                
            # Получаем сигнал
            trade = self.strategy.get_signal(symbol)
            if not trade or trade.signal == Signal.NONE:
                continue
                
            # Рассчитываем размер позиции
            position_usdt = available * (self.risk_pct / 100)
            size = position_usdt / trade.entry_price
            
            # Округляем
            if coin == "BTC":
                size = round(size, 3)
            elif coin in ["ETH", "SOL"]:
                size = round(size, 2)
            else:
                size = round(size, 1)
                
            if size < 0.001:
                continue
            
            # Отправляем сигнал на открытие
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


class MultiStrategyManager:
    """Менеджер для запуска нескольких стратегий параллельно"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.workers: Dict[str, StrategyWorker] = {}
        self.active_strategies: Dict[str, dict] = {}  # strategy_id -> config
        
    def start_strategy(self, strategy_id: str, coins: List[str], risk_pct: float, leverage: int,
                       log_callback, trade_callback, close_callback) -> bool:
        """Запустить стратегию"""
        if strategy_id in self.workers:
            return False  # Уже запущена
            
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
        """Остановить стратегию"""
        if strategy_id not in self.workers:
            return False
            
        worker = self.workers[strategy_id]
        worker.stop()
        worker.wait(2000)
        
        del self.workers[strategy_id]
        del self.active_strategies[strategy_id]
        return True
        
    def stop_all(self):
        """Остановить все стратегии"""
        for strategy_id in list(self.workers.keys()):
            self.stop_strategy(strategy_id)
            
    def run_check(self, strategy_id: str):
        """Запустить проверку для стратегии"""
        if strategy_id not in self.active_strategies:
            return
            
        config = self.active_strategies[strategy_id]
        
        # Создаём новый воркер для проверки
        if strategy_id in self.workers:
            old_worker = self.workers[strategy_id]
            if old_worker.isRunning():
                return  # Ещё работает
                
        # Перезапускаем
        worker = self.workers.get(strategy_id)
        if worker and not worker.isRunning():
            worker.start()
            
    def is_running(self, strategy_id: str) -> bool:
        """Проверить запущена ли стратегия"""
        return strategy_id in self.workers
