"""
🌊 Swing Trading Strategy (Свинг-трейдинг)

Среднесрочные сделки на несколько дней.
Баланс между частотой и качеством сделок.

Логика:
- MACD для определения моментума
- EMA 50/200 для тренда
- Вход на развороте MACD по тренду
- Держим позицию несколько дней

Средняя доходность: 15-25% в месяц
"""
from .base import BaseStrategy, StrategyConfig, TradeSignal, Signal
from typing import Optional


CONFIG = StrategyConfig(
    name="🌊 Swing Trading",
    description="Свинг-трейдинг. Среднесрочные сделки на несколько дней с хорошим R:R.",
    timeframe="1d",
    sl_pct=3.0,
    tp_pct=9.0,
    risk_reward="1:3",
    avg_monthly_return="15-25%",
    win_rate="50-60%",
    trades_per_month="4-8",
    risk_level="Средний"
)


class SwingStrategy(BaseStrategy):
    """Стратегия свинг-трейдинга"""
    
    def __init__(self, exchange):
        super().__init__(exchange, CONFIG)
        
    def calc_macd(self, closes: list) -> tuple:
        """Рассчитать MACD"""
        if len(closes) < 35:
            return None, None, None
            
        ema12 = self.calc_ema(closes, 12)
        ema26 = self.calc_ema(closes, 26)
        
        if not ema12 or not ema26:
            return None, None, None
            
        # Выравниваем длины
        min_len = min(len(ema12), len(ema26))
        ema12 = ema12[-min_len:]
        ema26 = ema26[-min_len:]
        
        macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
        signal_line = self.calc_ema(macd_line, 9)
        
        if not signal_line:
            return None, None, None
            
        histogram = macd_line[-1] - signal_line[-1]
        
        return macd_line[-1], signal_line[-1], histogram
        
    def get_signal(self, symbol: str) -> Optional[TradeSignal]:
        ohlcv = self.get_ohlcv(symbol, 250)
        if len(ohlcv) < 200:
            return None
            
        closes = [c[4] for c in ohlcv]
        current_price = closes[-1]
        
        # EMA для тренда
        ema50 = self.calc_ema(closes, 50)
        ema200 = self.calc_ema(closes, 200)
        
        if not ema50 or not ema200:
            return None
            
        # MACD
        macd, signal, histogram = self.calc_macd(closes)
        if macd is None:
            return None
            
        # Предыдущий MACD
        prev_closes = closes[:-1]
        prev_macd, prev_signal, _ = self.calc_macd(prev_closes)
        if prev_macd is None:
            return None
        
        # ATR
        atr = self.calc_atr(ohlcv)
        
        trade_signal = Signal.NONE
        reason = ""
        strength = 0
        
        uptrend = ema50[-1] > ema200[-1]
        downtrend = ema50[-1] < ema200[-1]
        
        # ЛОНГ: восходящий тренд + MACD пересекает сигнальную вверх
        if uptrend and prev_macd <= prev_signal and macd > signal:
            trade_signal = Signal.BUY
            strength = min(85, 60 + int(abs(histogram) * 1000))
            reason = f"MACD пересёк сигнальную вверх в восходящем тренде"
            
        # ШОРТ: нисходящий тренд + MACD пересекает сигнальную вниз
        elif downtrend and prev_macd >= prev_signal and macd < signal:
            trade_signal = Signal.SELL
            strength = min(85, 60 + int(abs(histogram) * 1000))
            reason = f"MACD пересёк сигнальную вниз в нисходящем тренде"
        
        if trade_signal == Signal.NONE:
            return None
            
        # SL/TP на основе ATR
        if trade_signal == Signal.BUY:
            sl_price = current_price - (atr * 2)
            tp_price = current_price + (atr * 6)
        else:
            sl_price = current_price + (atr * 2)
            tp_price = current_price - (atr * 6)
            
        return TradeSignal(
            signal=trade_signal,
            strength=strength,
            entry_price=current_price,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=reason
        )
    
    def should_close(self, symbol: str, position_side: str, entry_price: float) -> tuple:
        ohlcv = self.get_ohlcv(symbol, 50)
        if len(ohlcv) < 35:
            return False, ""
            
        closes = [c[4] for c in ohlcv]
        
        macd, signal, histogram = self.calc_macd(closes)
        if macd is None:
            return False, ""
        
        # Закрываем при обратном пересечении MACD
        if position_side == "long" and macd < signal:
            return True, "MACD пересёк сигнальную вниз"
        if position_side == "short" and macd > signal:
            return True, "MACD пересёк сигнальную вверх"
            
        return False, ""
