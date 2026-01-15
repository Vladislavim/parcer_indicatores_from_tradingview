"""
Базовый класс для торговых стратегий
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    NONE = "none"


@dataclass
class StrategyConfig:
    """Конфигурация стратегии"""
    name: str
    description: str
    timeframe: str  # "1h", "4h", "1d"
    sl_pct: float   # Stop Loss %
    tp_pct: float   # Take Profit %
    risk_reward: str  # "1:2", "1:3" etc
    avg_monthly_return: str  # "15-25%", "10-20%" etc
    win_rate: str   # "55-65%", "60-70%" etc
    trades_per_month: str  # "10-15", "5-10" etc
    risk_level: str  # "Низкий", "Средний", "Высокий"


@dataclass 
class TradeSignal:
    """Торговый сигнал"""
    signal: Signal
    strength: int  # 0-100
    entry_price: float
    sl_price: float
    tp_price: float
    reason: str


class BaseStrategy(ABC):
    """Базовый класс стратегии"""
    
    def __init__(self, exchange, config: StrategyConfig):
        self.exchange = exchange
        self.config = config
        
    @abstractmethod
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        """Получить торговый сигнал"""
        pass
    
    @abstractmethod
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> Tuple[bool, str]:
        """Проверить нужно ли закрыть позицию"""
        pass
    
    def get_ohlcv(self, symbol: str, limit: int = 100) -> list:
        """Получить свечи"""
        try:
            return self.exchange.fetch_ohlcv(symbol, self.config.timeframe, limit=limit)
        except:
            return []
    
    def calc_ema(self, closes: list, period: int) -> list:
        """Рассчитать EMA"""
        if len(closes) < period:
            return []
        ema = []
        multiplier = 2 / (period + 1)
        sma = sum(closes[:period]) / period
        ema.append(sma)
        for price in closes[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
    
    def calc_rsi(self, closes: list, period: int = 14) -> float:
        """Рассчитать RSI"""
        if len(closes) < period + 1:
            return 50
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calc_atr(self, ohlcv: list, period: int = 14) -> float:
        """Рассчитать ATR"""
        if len(ohlcv) < period + 1:
            return 0
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period
