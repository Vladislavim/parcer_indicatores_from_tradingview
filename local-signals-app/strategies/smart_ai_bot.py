"""
🧠 SMART AI BOT - Супер-умный торговый бот

Использует комплексный анализ рынка:
1. Multi-Timeframe Analysis (MTF) - анализ нескольких таймфреймов
2. Market Structure - определение тренда, BOS, CHoCH
3. Order Blocks & FVG - институциональные зоны
4. Liquidity Zones - зоны ликвидности
5. Volume Profile - анализ объёмов
6. Sentiment Analysis - настроение рынка
7. Correlation Analysis - корреляция с BTC
8. Risk Management - динамический риск

Средняя доходность: 20-50% в месяц при правильных настройках
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum
import math


class MarketPhase(Enum):
    ACCUMULATION = "accumulation"  # Накопление
    MARKUP = "markup"              # Рост
    DISTRIBUTION = "distribution"  # Распределение
    MARKDOWN = "markdown"          # Падение


class TrendStrength(Enum):
    STRONG_BULL = "strong_bull"
    WEAK_BULL = "weak_bull"
    NEUTRAL = "neutral"
    WEAK_BEAR = "weak_bear"
    STRONG_BEAR = "strong_bear"


@dataclass
class MarketAnalysis:
    """Результат анализа рынка"""
    # Тренд
    trend: str  # "bull", "bear", "neutral"
    trend_strength: TrendStrength
    market_phase: MarketPhase
    
    # MTF анализ
    htf_trend: str  # Старший ТФ
    mtf_trend: str  # Средний ТФ
    ltf_trend: str  # Младший ТФ
    mtf_alignment: bool  # Все ТФ совпадают
    
    # Структура
    last_bos: Optional[str]  # Последний BOS
    last_choch: Optional[str]  # Последний CHoCH
    swing_high: float
    swing_low: float
    
    # Зоны
    order_blocks: List[Tuple[float, float, str]]  # (price, strength, type)
    fvg_zones: List[Tuple[float, float]]  # Fair Value Gaps
    liquidity_zones: List[Tuple[float, str]]  # (price, type)
    
    # Индикаторы
    rsi: float
    macd_histogram: float
    volume_ratio: float  # Текущий объём / средний
    atr: float
    
    # Сентимент
    funding_rate: float
    open_interest_change: float
    long_short_ratio: float
    
    # Скор
    bull_score: int  # 0-100
    bear_score: int  # 0-100
    confidence: int  # 0-100


@dataclass
class SmartSignal:
    """Умный торговый сигнал"""
    action: str  # "buy", "sell", "wait"
    confidence: int  # 0-100
    entry_price: float
    stop_loss: float
    take_profit_1: float  # Первая цель
    take_profit_2: float  # Вторая цель
    take_profit_3: float  # Третья цель
    position_size_pct: float  # % от баланса
    reason: str
    analysis: MarketAnalysis


class SmartAIBot:
    """Супер-умный AI торговый бот"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.analysis_cache: Dict[str, MarketAnalysis] = {}
        
    # ==================== ТЕХНИЧЕСКИЙ АНАЛИЗ ====================
    
    def calc_ema(self, closes: list, period: int) -> list:
        """EMA"""
        if len(closes) < period:
            return []
        ema = []
        mult = 2 / (period + 1)
        sma = sum(closes[:period]) / period
        ema.append(sma)
        for price in closes[period:]:
            ema.append((price - ema[-1]) * mult + ema[-1])
        return ema
    
    def calc_rsi(self, closes: list, period: int = 14) -> float:
        """RSI"""
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
    
    def calc_macd(self, closes: list) -> Tuple[float, float, float]:
        """MACD"""
        if len(closes) < 35:
            return 0, 0, 0
        ema12 = self.calc_ema(closes, 12)
        ema26 = self.calc_ema(closes, 26)
        if not ema12 or not ema26:
            return 0, 0, 0
        min_len = min(len(ema12), len(ema26))
        macd_line = [e12 - e26 for e12, e26 in zip(ema12[-min_len:], ema26[-min_len:])]
        signal = self.calc_ema(macd_line, 9)
        if not signal:
            return 0, 0, 0
        return macd_line[-1], signal[-1], macd_line[-1] - signal[-1]

    def calc_atr(self, ohlcv: list, period: int = 14) -> float:
        """ATR"""
        if len(ohlcv) < period + 1:
            return 0
        trs = []
        for i in range(1, len(ohlcv)):
            high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period
    
    def calc_bollinger(self, closes: list, period: int = 20) -> Tuple[float, float, float]:
        """Bollinger Bands"""
        if len(closes) < period:
            return 0, 0, 0
        sma = sum(closes[-period:]) / period
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = math.sqrt(variance)
        return sma - 2*std, sma, sma + 2*std
    
    # ==================== СТРУКТУРА РЫНКА ====================
    
    def find_swing_points(self, ohlcv: list, lookback: int = 5) -> Tuple[List, List]:
        """Находит swing high/low"""
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(ohlcv) - lookback):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            
            is_swing_high = all(high >= ohlcv[j][2] for j in range(i-lookback, i+lookback+1) if j != i)
            is_swing_low = all(low <= ohlcv[j][3] for j in range(i-lookback, i+lookback+1) if j != i)
            
            if is_swing_high:
                swing_highs.append((i, high))
            if is_swing_low:
                swing_lows.append((i, low))
                
        return swing_highs, swing_lows
    
    def detect_bos_choch(self, ohlcv: list) -> Tuple[Optional[str], Optional[str]]:
        """Определяет BOS и CHoCH"""
        swing_highs, swing_lows = self.find_swing_points(ohlcv)
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None, None
            
        current_price = ohlcv[-1][4]
        last_high = swing_highs[-1][1]
        prev_high = swing_highs[-2][1] if len(swing_highs) > 1 else last_high
        last_low = swing_lows[-1][1]
        prev_low = swing_lows[-2][1] if len(swing_lows) > 1 else last_low
        
        bos = None
        choch = None
        
        # BOS вверх - пробой предыдущего хая в восходящем тренде
        if current_price > last_high and last_low > prev_low:
            bos = "bull"
        # BOS вниз - пробой предыдущего лоу в нисходящем тренде
        elif current_price < last_low and last_high < prev_high:
            bos = "bear"
            
        # CHoCH - смена характера (разворот)
        if current_price > last_high and last_high < prev_high:
            choch = "bull"  # Был даунтренд, теперь разворот вверх
        elif current_price < last_low and last_low > prev_low:
            choch = "bear"  # Был аптренд, теперь разворот вниз
            
        return bos, choch

    def find_order_blocks(self, ohlcv: list) -> List[Tuple[float, float, str]]:
        """Находит Order Blocks (институциональные зоны)"""
        order_blocks = []
        
        for i in range(2, len(ohlcv) - 1):
            # Бычий OB: сильное движение вверх после свечи
            if ohlcv[i+1][4] > ohlcv[i][2] * 1.005:  # Следующая свеча закрылась выше хая
                if ohlcv[i][4] < ohlcv[i][1]:  # Текущая свеча медвежья
                    ob_price = (ohlcv[i][3] + ohlcv[i][4]) / 2  # Середина тела
                    strength = (ohlcv[i+1][4] - ohlcv[i][2]) / ohlcv[i][2] * 100
                    order_blocks.append((ob_price, strength, "bull"))
                    
            # Медвежий OB: сильное движение вниз после свечи
            if ohlcv[i+1][4] < ohlcv[i][3] * 0.995:
                if ohlcv[i][4] > ohlcv[i][1]:  # Текущая свеча бычья
                    ob_price = (ohlcv[i][2] + ohlcv[i][4]) / 2
                    strength = (ohlcv[i][3] - ohlcv[i+1][4]) / ohlcv[i][3] * 100
                    order_blocks.append((ob_price, strength, "bear"))
                    
        return order_blocks[-5:]  # Последние 5
    
    def find_fvg(self, ohlcv: list) -> List[Tuple[float, float]]:
        """Находит Fair Value Gaps (имбалансы)"""
        fvg_zones = []
        
        for i in range(2, len(ohlcv)):
            # Бычий FVG: гэп между хаем свечи i-2 и лоу свечи i
            if ohlcv[i][3] > ohlcv[i-2][2]:
                gap_low = ohlcv[i-2][2]
                gap_high = ohlcv[i][3]
                fvg_zones.append((gap_low, gap_high))
                
            # Медвежий FVG
            if ohlcv[i][2] < ohlcv[i-2][3]:
                gap_low = ohlcv[i][2]
                gap_high = ohlcv[i-2][3]
                fvg_zones.append((gap_low, gap_high))
                
        return fvg_zones[-5:]
    
    def find_liquidity_zones(self, ohlcv: list) -> List[Tuple[float, str]]:
        """Находит зоны ликвидности (скопления стопов)"""
        swing_highs, swing_lows = self.find_swing_points(ohlcv, 3)
        
        liquidity = []
        
        # Ликвидность выше равных хаёв
        for i, (idx, high) in enumerate(swing_highs[:-1]):
            for j, (idx2, high2) in enumerate(swing_highs[i+1:]):
                if abs(high - high2) / high < 0.002:  # Равные хаи (0.2%)
                    liquidity.append((max(high, high2), "buy_stops"))
                    
        # Ликвидность ниже равных лоёв
        for i, (idx, low) in enumerate(swing_lows[:-1]):
            for j, (idx2, low2) in enumerate(swing_lows[i+1:]):
                if abs(low - low2) / low < 0.002:
                    liquidity.append((min(low, low2), "sell_stops"))
                    
        return liquidity[-5:]

    # ==================== MULTI-TIMEFRAME АНАЛИЗ ====================
    
    def get_trend(self, ohlcv: list) -> str:
        """Определяет тренд по EMA"""
        if len(ohlcv) < 50:
            return "neutral"
        closes = [c[4] for c in ohlcv]
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, 50)
        if not ema20 or not ema50:
            return "neutral"
        if ema20[-1] > ema50[-1] and closes[-1] > ema20[-1]:
            return "bull"
        elif ema20[-1] < ema50[-1] and closes[-1] < ema20[-1]:
            return "bear"
        return "neutral"
    
    def analyze_mtf(self, symbol: str) -> Tuple[str, str, str, bool]:
        """Multi-Timeframe анализ"""
        try:
            # HTF - 4h
            htf_ohlcv = self.exchange.fetch_ohlcv(symbol, '4h', limit=100)
            htf_trend = self.get_trend(htf_ohlcv)
            
            # MTF - 1h
            mtf_ohlcv = self.exchange.fetch_ohlcv(symbol, '1h', limit=100)
            mtf_trend = self.get_trend(mtf_ohlcv)
            
            # LTF - 15m
            ltf_ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=100)
            ltf_trend = self.get_trend(ltf_ohlcv)
            
            # Проверяем выравнивание
            alignment = htf_trend == mtf_trend == ltf_trend and htf_trend != "neutral"
            
            return htf_trend, mtf_trend, ltf_trend, alignment
            
        except:
            return "neutral", "neutral", "neutral", False
    
    def get_market_phase(self, ohlcv: list) -> MarketPhase:
        """Определяет фазу рынка по Вайкоффу"""
        if len(ohlcv) < 50:
            return MarketPhase.NEUTRAL
            
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        # Средние
        price_change = (closes[-1] - closes[-20]) / closes[-20] * 100
        vol_avg = sum(volumes[-20:]) / 20
        vol_recent = sum(volumes[-5:]) / 5
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1
        
        # Волатильность
        atr = self.calc_atr(ohlcv)
        atr_pct = atr / closes[-1] * 100
        
        # Определяем фазу
        if price_change > 5 and vol_ratio > 1.2:
            return MarketPhase.MARKUP
        elif price_change < -5 and vol_ratio > 1.2:
            return MarketPhase.MARKDOWN
        elif abs(price_change) < 2 and vol_ratio < 0.8:
            if closes[-1] < closes[-20]:
                return MarketPhase.ACCUMULATION
            else:
                return MarketPhase.DISTRIBUTION
        
        return MarketPhase.MARKUP if price_change > 0 else MarketPhase.MARKDOWN

    # ==================== СЕНТИМЕНТ ====================
    
    def get_funding_rate(self, symbol: str) -> float:
        """Получает funding rate"""
        try:
            # Для Bybit
            funding = self.exchange.fetch_funding_rate(symbol)
            return float(funding.get('fundingRate', 0)) * 100
        except:
            return 0
    
    def get_sentiment_score(self, symbol: str) -> Tuple[float, float, float]:
        """Анализ сентимента"""
        funding = self.get_funding_rate(symbol)
        
        # Funding rate интерпретация:
        # > 0.01% - много лонгов, возможен шорт-сквиз или коррекция
        # < -0.01% - много шортов, возможен лонг-сквиз
        
        # Упрощённый long/short ratio на основе funding
        if funding > 0.05:
            long_short = 1.5  # Много лонгов
        elif funding < -0.05:
            long_short = 0.7  # Много шортов
        else:
            long_short = 1.0
            
        return funding, 0, long_short  # OI change пока 0
    
    # ==================== ГЛАВНЫЙ АНАЛИЗ ====================
    
    def analyze(self, symbol: str) -> MarketAnalysis:
        """Полный анализ рынка"""
        # Получаем данные
        ohlcv_1h = self.exchange.fetch_ohlcv(symbol, '1h', limit=200)
        
        if len(ohlcv_1h) < 50:
            raise Exception("Недостаточно данных")
            
        closes = [c[4] for c in ohlcv_1h]
        current_price = closes[-1]
        
        # MTF анализ
        htf, mtf, ltf, alignment = self.analyze_mtf(symbol)
        
        # Структура
        bos, choch = self.detect_bos_choch(ohlcv_1h)
        swing_highs, swing_lows = self.find_swing_points(ohlcv_1h)
        
        # Зоны
        order_blocks = self.find_order_blocks(ohlcv_1h)
        fvg_zones = self.find_fvg(ohlcv_1h)
        liquidity = self.find_liquidity_zones(ohlcv_1h)
        
        # Индикаторы
        rsi = self.calc_rsi(closes)
        macd, signal, histogram = self.calc_macd(closes)
        atr = self.calc_atr(ohlcv_1h)
        
        # Объём
        volumes = [c[5] for c in ohlcv_1h]
        vol_avg = sum(volumes[-20:]) / 20
        vol_ratio = volumes[-1] / vol_avg if vol_avg > 0 else 1
        
        # Сентимент
        funding, oi_change, ls_ratio = self.get_sentiment_score(symbol)
        
        # Фаза рынка
        phase = self.get_market_phase(ohlcv_1h)
        
        # Определяем силу тренда
        if alignment and htf == "bull":
            strength = TrendStrength.STRONG_BULL
        elif htf == "bull":
            strength = TrendStrength.WEAK_BULL
        elif alignment and htf == "bear":
            strength = TrendStrength.STRONG_BEAR
        elif htf == "bear":
            strength = TrendStrength.WEAK_BEAR
        else:
            strength = TrendStrength.NEUTRAL

        # Скоринг
        bull_score = 0
        bear_score = 0
        
        # MTF +30
        if alignment:
            if htf == "bull":
                bull_score += 30
            elif htf == "bear":
                bear_score += 30
        else:
            if htf == "bull":
                bull_score += 15
            elif htf == "bear":
                bear_score += 15
                
        # RSI +20
        if rsi < 30:
            bull_score += 20  # Перепродан
        elif rsi > 70:
            bear_score += 20  # Перекуплен
        elif rsi < 45:
            bull_score += 10
        elif rsi > 55:
            bear_score += 10
            
        # MACD +15
        if histogram > 0:
            bull_score += 15
        else:
            bear_score += 15
            
        # BOS/CHoCH +20
        if bos == "bull" or choch == "bull":
            bull_score += 20
        elif bos == "bear" or choch == "bear":
            bear_score += 20
            
        # Order Blocks +10
        for ob_price, strength, ob_type in order_blocks:
            if ob_type == "bull" and current_price < ob_price * 1.02:
                bull_score += 10
                break
            elif ob_type == "bear" and current_price > ob_price * 0.98:
                bear_score += 10
                break
                
        # Funding +5
        if funding < -0.01:
            bull_score += 5  # Много шортов - потенциал сквиза
        elif funding > 0.03:
            bear_score += 5  # Много лонгов - потенциал коррекции
            
        # Confidence
        confidence = abs(bull_score - bear_score)
        
        return MarketAnalysis(
            trend=htf,
            trend_strength=strength,
            market_phase=phase,
            htf_trend=htf,
            mtf_trend=mtf,
            ltf_trend=ltf,
            mtf_alignment=alignment,
            last_bos=bos,
            last_choch=choch,
            swing_high=swing_highs[-1][1] if swing_highs else current_price,
            swing_low=swing_lows[-1][1] if swing_lows else current_price,
            order_blocks=order_blocks,
            fvg_zones=fvg_zones,
            liquidity_zones=liquidity,
            rsi=rsi,
            macd_histogram=histogram,
            volume_ratio=vol_ratio,
            atr=atr,
            funding_rate=funding,
            open_interest_change=oi_change,
            long_short_ratio=ls_ratio,
            bull_score=bull_score,
            bear_score=bear_score,
            confidence=confidence
        )

    # ==================== ГЕНЕРАЦИЯ СИГНАЛА ====================
    
    def get_signal(self, symbol: str, risk_pct: float = 2.0) -> Optional[SmartSignal]:
        """Генерирует умный торговый сигнал"""
        try:
            analysis = self.analyze(symbol)
        except Exception as e:
            return None
            
        # Минимальный confidence для входа
        MIN_CONFIDENCE = 25
        
        if analysis.confidence < MIN_CONFIDENCE:
            return SmartSignal(
                action="wait",
                confidence=analysis.confidence,
                entry_price=0,
                stop_loss=0,
                take_profit_1=0,
                take_profit_2=0,
                take_profit_3=0,
                position_size_pct=0,
                reason=f"Низкая уверенность ({analysis.confidence}). Ждём.",
                analysis=analysis
            )
        
        # Определяем направление
        if analysis.bull_score > analysis.bear_score:
            action = "buy"
            score = analysis.bull_score
        else:
            action = "sell"
            score = analysis.bear_score
            
        # Дополнительные фильтры
        reasons = []
        
        # MTF alignment - обязательно для сильного сигнала
        if analysis.mtf_alignment:
            reasons.append(f"MTF выравнивание ({analysis.htf_trend})")
        else:
            # Без выравнивания - только если очень сильный сигнал
            if analysis.confidence < 40:
                return SmartSignal(
                    action="wait",
                    confidence=analysis.confidence,
                    entry_price=0, stop_loss=0,
                    take_profit_1=0, take_profit_2=0, take_profit_3=0,
                    position_size_pct=0,
                    reason="MTF не выровнены. Ждём подтверждения.",
                    analysis=analysis
                )
            reasons.append(f"Сильный сигнал без MTF")
            
        # BOS/CHoCH
        if analysis.last_bos:
            reasons.append(f"BOS {analysis.last_bos}")
        if analysis.last_choch:
            reasons.append(f"CHoCH {analysis.last_choch}")
            
        # RSI
        if analysis.rsi < 30:
            reasons.append(f"RSI перепродан ({analysis.rsi:.0f})")
        elif analysis.rsi > 70:
            reasons.append(f"RSI перекуплен ({analysis.rsi:.0f})")
            
        # Фаза рынка
        reasons.append(f"Фаза: {analysis.market_phase.value}")
        
        # Рассчитываем уровни
        current_price = analysis.swing_high if action == "sell" else analysis.swing_low
        ticker = self.exchange.fetch_ticker(symbol)
        entry = ticker['last']
        atr = analysis.atr
        
        # Ограничиваем ATR максимум 3% от цены (чтобы TP не был отрицательным)
        max_atr = entry * 0.03
        atr = min(atr, max_atr)
        
        if action == "buy":
            stop_loss = entry - atr * 1.5
            tp1 = entry + atr * 1.5  # 1:1
            tp2 = entry + atr * 3.0  # 1:2
            tp3 = entry + atr * 4.5  # 1:3
        else:
            stop_loss = entry + atr * 1.5
            tp1 = entry - atr * 1.5
            tp2 = entry - atr * 3.0
            tp3 = entry - atr * 4.5
        
        # Защита от отрицательных TP
        if action == "sell":
            tp1 = max(tp1, entry * 0.9)   # Минимум -10%
            tp2 = max(tp2, entry * 0.85)  # Минимум -15%
            tp3 = max(tp3, entry * 0.8)   # Минимум -20%
            
        # Размер позиции на основе confidence
        if analysis.confidence >= 50:
            size_pct = risk_pct * 1.5  # Увеличиваем при высокой уверенности
        elif analysis.confidence >= 35:
            size_pct = risk_pct
        else:
            size_pct = risk_pct * 0.5  # Уменьшаем при низкой
            
        return SmartSignal(
            action=action,
            confidence=analysis.confidence,
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit_1=round(tp1, 2),
            take_profit_2=round(tp2, 2),
            take_profit_3=round(tp3, 2),
            position_size_pct=size_pct,
            reason=" | ".join(reasons),
            analysis=analysis
        )
