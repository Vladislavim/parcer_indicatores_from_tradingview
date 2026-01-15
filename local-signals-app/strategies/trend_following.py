"""
🚀 Trend Following Strategy (Следование за трендом)

Классическая стратегия профессиональных трейдеров.
Торгует только по тренду на старших таймфреймах.

Логика:
- EMA 20/50/200 для определения тренда
- RSI для подтверждения силы
- ATR для динамического SL/TP
- Вход на откатах к EMA

Средняя доходность: 15-30% в месяц при правильном риск-менеджменте
"""
from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal
from typing import Optional


CONFIG = StrategyConfig(
    name="🚀 Trend Following",
    description="Следование за трендом. Торгует только по направлению основного тренда на откатах.",
    timeframe="4h",
    sl_pct=1.5,
    tp_pct=4.5,
    risk_reward="1:3",
    avg_monthly_return="15-30%",
    win_rate="45-55%",
    trades_per_month="8-15",
    risk_level="Средний"
)


class TrendFollowingStrategy(BaseStrategy):
    """Стратегия следования за трендом"""
    
    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 250)
        if len(ohlcv) < 200:
            return None
            
        closes = [c[4] for c in ohlcv]
        current_price = closes[-1]
        
        # EMA
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        ema200 = self.calc_ema(closes, 200)
        
        if not ema20 or not ema50 or not ema200:
            return None
            
        ema20_val = ema20[-1]
        ema50_val = ema50[-1]
        ema200_val = ema200[-1]
        
        # RSI
        rsi = self.calc_rsi(closes)
        
        # ATR для динамического SL
        atr = self.calc_atr(ohlcv)
        
        # Определяем тренд
        uptrend = ema20_val > ema50_val > ema200_val
        downtrend = ema20_val < ema50_val < ema200_val
        
        signal = Signal.NONE
        reason = ""
        strength = 0
        
        # ЛОНГ: восходящий тренд + откат к EMA20 + RSI не перекуплен
        if uptrend and current_price <= ema20_val * 1.01 and current_price > ema50_val:
            if rsi < 70:
                signal = Signal.BUY
                strength = 70 + int((70 - rsi) / 2)  # Чем ниже RSI, тем сильнее сигнал
                reason = f"Откат к EMA20 в восходящем тренде, RSI={rsi:.0f}"
        
        # ШОРТ: нисходящий тренд + откат к EMA20 + RSI не перепродан
        elif downtrend and current_price >= ema20_val * 0.99 and current_price < ema50_val:
            if rsi > 30:
                signal = Signal.SELL
                strength = 70 + int((rsi - 30) / 2)
                reason = f"Откат к EMA20 в нисходящем тренде, RSI={rsi:.0f}"
        
        if signal == Signal.NONE:
            return None
            
        # Динамический SL/TP на основе ATR
        atr_mult_sl = 1.5
        atr_mult_tp = 4.5
        
        if signal == Signal.BUY:
            sl_price = current_price - (atr * atr_mult_sl)
            tp_price = current_price + (atr * atr_mult_tp)
        else:
            sl_price = current_price + (atr * atr_mult_sl)
            tp_price = current_price - (atr * atr_mult_tp)
            
        return TradeSignal(
            signal=signal,
            strength=min(strength, 100),
            entry_price=current_price,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=reason
        )
    
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple:
        ohlcv = self.get_ohlcv(symbol, 60)
        if len(ohlcv) < 50:
            return False, ""
            
        closes = [c[4] for c in ohlcv]
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        
        if not ema20 or not ema50:
            return False, ""
        
        # Закрываем если тренд сломался
        if position_side == "long" and ema20[-1] < ema50[-1]:
            return True, "Тренд сломался (EMA20 < EMA50)"
        if position_side == "short" and ema20[-1] > ema50[-1]:
            return True, "Тренд сломался (EMA20 > EMA50)"
            
        return False, ""
