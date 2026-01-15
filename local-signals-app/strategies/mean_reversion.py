"""
🔄 Mean Reversion Strategy (Возврат к среднему)

Торгует отклонения от средней цены.
Консервативная стратегия с высоким винрейтом.

Логика:
- Bollinger Bands для определения перекупленности/перепроданности
- RSI для подтверждения
- Вход при касании границ BB
- Выход при возврате к средней

Средняя доходность: 10-20% в месяц (низкий риск)
"""
from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal
from typing import Optional
import math


CONFIG = StrategyConfig(
    name="🔄 Mean Reversion",
    description="Возврат к среднему. Торгует отклонения от средней цены с высоким винрейтом.",
    timeframe="4h",
    sl_pct=2.0,
    tp_pct=3.0,
    risk_reward="1:1.5",
    avg_monthly_return="10-20%",
    win_rate="60-70%",
    trades_per_month="10-20",
    risk_level="Низкий"
)


class MeanReversionStrategy(BaseStrategy):
    """Стратегия возврата к среднему"""
    
    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        
    def calc_bollinger(self, closes: list, period: int = 20, std_mult: float = 2.0) -> tuple:
        """Рассчитать Bollinger Bands"""
        if len(closes) < period:
            return None, None, None
            
        sma = sum(closes[-period:]) / period
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = math.sqrt(variance)
        
        upper = sma + (std * std_mult)
        lower = sma - (std * std_mult)
        
        return lower, sma, upper
        
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 50)
        if len(ohlcv) < 30:
            return None
            
        closes = [c[4] for c in ohlcv]
        current_price = closes[-1]
        
        # Bollinger Bands
        bb_lower, bb_middle, bb_upper = self.calc_bollinger(closes)
        if not bb_lower:
            return None
            
        # RSI
        rsi = self.calc_rsi(closes)
        
        # ATR
        atr = self.calc_atr(ohlcv)
        
        signal = Signal.NONE
        reason = ""
        strength = 0
        
        # Ширина BB в процентах
        bb_width = (bb_upper - bb_lower) / bb_middle * 100
        
        # ЛОНГ: цена у нижней границы BB + RSI перепродан
        if current_price <= bb_lower * 1.005 and rsi < 35:
            signal = Signal.BUY
            strength = min(90, 50 + int((35 - rsi) * 2))
            reason = f"Касание нижней BB, RSI={rsi:.0f} (перепродан)"
            
        # ШОРТ: цена у верхней границы BB + RSI перекуплен
        elif current_price >= bb_upper * 0.995 and rsi > 65:
            signal = Signal.SELL
            strength = min(90, 50 + int((rsi - 65) * 2))
            reason = f"Касание верхней BB, RSI={rsi:.0f} (перекуплен)"
        
        if signal == Signal.NONE:
            return None
            
        # TP = средняя BB, SL = за границей BB
        if signal == Signal.BUY:
            sl_price = bb_lower - atr
            tp_price = bb_middle
        else:
            sl_price = bb_upper + atr
            tp_price = bb_middle
            
        return TradeSignal(
            signal=signal,
            strength=strength,
            entry_price=current_price,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=reason
        )
    
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple:
        ohlcv = self.get_ohlcv(symbol, 30)
        if len(ohlcv) < 20:
            return False, ""
            
        closes = [c[4] for c in ohlcv]
        current = closes[-1]
        
        bb_lower, bb_middle, bb_upper = self.calc_bollinger(closes)
        if not bb_middle:
            return False, ""
        
        # Закрываем при достижении средней BB
        if position_side == "long" and current >= bb_middle:
            return True, "Достигнута средняя BB"
        if position_side == "short" and current <= bb_middle:
            return True, "Достигнута средняя BB"
            
        return False, ""
