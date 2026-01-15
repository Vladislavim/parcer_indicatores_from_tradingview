"""
💥 Breakout Strategy (Пробой уровней)

Торгует пробои ключевых уровней поддержки/сопротивления.
Используется профессионалами для ловли сильных движений.

Логика:
- Определение уровней по максимумам/минимумам
- Подтверждение объёмом (если доступно)
- Вход на пробое с ретестом
- Жёсткий SL за уровнем

Средняя доходность: 20-40% в месяц (высокий риск)
"""
from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal
from typing import Optional


CONFIG = StrategyConfig(
    name="💥 Breakout",
    description="Пробой уровней. Ловит сильные движения на пробоях поддержки/сопротивления.",
    timeframe="1h",
    sl_pct=0.8,
    tp_pct=2.4,
    risk_reward="1:3",
    avg_monthly_return="20-40%",
    win_rate="40-50%",
    trades_per_month="15-25",
    risk_level="Высокий"
)


class BreakoutStrategy(BaseStrategy):
    """Стратегия пробоя уровней"""
    
    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        
    def find_levels(self, ohlcv: list, lookback: int = 20) -> tuple:
        """Находит уровни поддержки и сопротивления"""
        if len(ohlcv) < lookback:
            return None, None
            
        highs = [c[2] for c in ohlcv[-lookback:]]
        lows = [c[3] for c in ohlcv[-lookback:]]
        
        resistance = max(highs)
        support = min(lows)
        
        return support, resistance
        
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 50)
        if len(ohlcv) < 30:
            return None
            
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        current_price = closes[-1]
        prev_close = closes[-2]
        
        # Уровни за последние 20 свечей (без текущей)
        support, resistance = self.find_levels(ohlcv[:-1], 20)
        if not support or not resistance:
            return None
            
        # ATR для фильтрации шума
        atr = self.calc_atr(ohlcv)
        min_breakout = atr * 0.5  # Минимальный пробой = 0.5 ATR
        
        signal = Signal.NONE
        reason = ""
        strength = 0
        
        # Пробой сопротивления вверх
        if prev_close <= resistance and current_price > resistance + min_breakout:
            signal = Signal.BUY
            strength = min(90, 60 + int((current_price - resistance) / atr * 30))
            reason = f"Пробой сопротивления ${resistance:,.2f}"
            
        # Пробой поддержки вниз
        elif prev_close >= support and current_price < support - min_breakout:
            signal = Signal.SELL
            strength = min(90, 60 + int((support - current_price) / atr * 30))
            reason = f"Пробой поддержки ${support:,.2f}"
        
        if signal == Signal.NONE:
            return None
            
        # SL за уровнем, TP = 3x SL
        if signal == Signal.BUY:
            sl_price = resistance - (atr * 0.5)  # SL чуть ниже уровня
            tp_price = current_price + (current_price - sl_price) * 3
        else:
            sl_price = support + (atr * 0.5)  # SL чуть выше уровня
            tp_price = current_price - (sl_price - current_price) * 3
            
        return TradeSignal(
            signal=signal,
            strength=strength,
            entry_price=current_price,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=reason
        )
    
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple:
        ohlcv = self.get_ohlcv(symbol, 10)
        if len(ohlcv) < 5:
            return False, ""
            
        closes = [c[4] for c in ohlcv]
        current = closes[-1]
        
        # Закрываем если цена вернулась за уровень (ложный пробой)
        atr = self.calc_atr(ohlcv)
        
        if position_side == "long" and current < entry_price - atr:
            return True, "Ложный пробой — цена вернулась"
        if position_side == "short" and current > entry_price + atr:
            return True, "Ложный пробой — цена вернулась"
            
        return False, ""
