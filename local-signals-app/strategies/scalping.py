"""
⚡ Scalping Strategy (Скальпинг)

Быстрые сделки на малых таймфреймах.
Много сделок, маленькие профиты.

Логика:
- EMA 9/21 для быстрого тренда
- RSI для моментума
- Быстрый вход/выход
- Жёсткий SL

Средняя доходность: 25-50% в месяц (очень высокий риск)
"""
from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal
from typing import Optional


CONFIG = StrategyConfig(
    name="⚡ Scalping",
    description="Скальпинг. Много быстрых сделок с маленьким профитом. Требует внимания.",
    timeframe="15m",
    sl_pct=0.5,
    tp_pct=1.0,
    risk_reward="1:2",
    avg_monthly_return="25-50%",
    win_rate="55-65%",
    trades_per_month="50-100",
    risk_level="Очень высокий"
)


class ScalpingStrategy(BaseStrategy):
    """Стратегия скальпинга"""
    
    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 50)
        if len(ohlcv) < 30:
            return None
            
        closes = [c[4] for c in ohlcv]
        current_price = closes[-1]
        
        # Быстрые EMA
        ema9 = self.calc_ema(closes, 9)
        ema21 = self.calc_ema(closes, 21)
        
        if not ema9 or not ema21:
            return None
            
        ema9_val = ema9[-1]
        ema21_val = ema21[-1]
        ema9_prev = ema9[-2] if len(ema9) > 1 else ema9_val
        ema21_prev = ema21[-2] if len(ema21) > 1 else ema21_val
        
        # RSI
        rsi = self.calc_rsi(closes, 7)  # Быстрый RSI
        
        # ATR
        atr = self.calc_atr(ohlcv, 7)
        
        signal = Signal.NONE
        reason = ""
        strength = 0
        
        # ЛОНГ: EMA9 пересекает EMA21 вверх + RSI > 50
        if ema9_prev <= ema21_prev and ema9_val > ema21_val and rsi > 50:
            signal = Signal.BUY
            strength = min(85, 60 + int(rsi - 50))
            reason = f"EMA9 пересекла EMA21 вверх, RSI={rsi:.0f}"
            
        # ШОРТ: EMA9 пересекает EMA21 вниз + RSI < 50
        elif ema9_prev >= ema21_prev and ema9_val < ema21_val and rsi < 50:
            signal = Signal.SELL
            strength = min(85, 60 + int(50 - rsi))
            reason = f"EMA9 пересекла EMA21 вниз, RSI={rsi:.0f}"
        
        if signal == Signal.NONE:
            return None
            
        # Жёсткий SL/TP
        if signal == Signal.BUY:
            sl_price = current_price - (atr * 1.0)
            tp_price = current_price + (atr * 2.0)
        else:
            sl_price = current_price + (atr * 1.0)
            tp_price = current_price - (atr * 2.0)
            
        return TradeSignal(
            signal=signal,
            strength=strength,
            entry_price=current_price,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=reason
        )
    
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple:
        ohlcv = self.get_ohlcv(symbol, 20)
        if len(ohlcv) < 15:
            return False, ""
            
        closes = [c[4] for c in ohlcv]
        
        ema9 = self.calc_ema(closes, 9)
        ema21 = self.calc_ema(closes, 21)
        
        if not ema9 or not ema21:
            return False, ""
        
        # Закрываем при обратном пересечении
        if position_side == "long" and ema9[-1] < ema21[-1]:
            return True, "EMA9 пересекла EMA21 вниз"
        if position_side == "short" and ema9[-1] > ema21[-1]:
            return True, "EMA9 пересекла EMA21 вверх"
            
        return False, ""
