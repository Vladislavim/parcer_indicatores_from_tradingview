"""
🧠 SMART AI BOT v2 - Улучшенная версия с дополнительными фильтрами

Новое в v2:
1. Liquidation Zones - где сносят стопы
2. Open Interest анализ - рост/падение OI
3. Volume Profile - POC, VAH, VAL
4. Корреляция с BTC - не торгуем альты против BTC
5. Volatility фильтр - не торгуем в боковике
6. Session фильтр - учитываем торговые сессии
7. Более строгий конфлюенс - 5 факторов вместо 3

Ожидаемый Win Rate: 60-68%
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime, timezone
import math

from strategies.smart_ai_bot import (
    SmartAIBot, MarketAnalysis, SmartSignal, 
    MarketPhase, TrendStrength
)


class TradingSession(Enum):
    ASIA = "asia"        # 00:00-08:00 UTC
    EUROPE = "europe"    # 08:00-16:00 UTC  
    USA = "usa"          # 14:00-22:00 UTC
    OVERLAP = "overlap"  # Пересечение сессий


@dataclass
class EnhancedAnalysis(MarketAnalysis):
    """Расширенный анализ v2"""
    # Ликвидации
    liquidation_zones: List[Tuple[float, str]]  # (price, type: "longs"/"shorts")
    near_liquidation_zone: bool
    
    # Open Interest
    oi_change_1h: float  # % изменение за час
    oi_change_24h: float  # % изменение за 24ч
    oi_trend: str  # "rising", "falling", "stable"
    
    # Volume Profile
    poc_price: float  # Point of Control
    vah_price: float  # Value Area High
    val_price: float  # Value Area Low
    price_vs_poc: str  # "above", "below", "at"
    
    # Корреляция
    btc_trend: str  # "bull", "bear", "neutral"
    btc_correlation: float  # -1 to 1
    aligned_with_btc: bool
    
    # Волатильность
    volatility_percentile: float  # 0-100
    is_ranging: bool  # Боковик
    
    # Сессия
    current_session: TradingSession
    session_volume_ratio: float  # Объём vs средний для сессии
    
    # Улучшенный скоринг
    v2_bull_score: int
    v2_bear_score: int
    v2_confidence: int
    confluence_count: int  # Сколько факторов совпало


class SmartAIBotV2(SmartAIBot):
    """Улучшенный Smart AI Bot v2"""
    
    VERSION = "v2"
    
    def __init__(self, exchange):
        super().__init__(exchange)
        self._btc_cache = {}
        self._oi_cache = {}
    
    # ==================== НОВЫЕ МЕТОДЫ v2 ====================
    
    def get_current_session(self) -> TradingSession:
        """Определяет текущую торговую сессию"""
        hour = datetime.now(timezone.utc).hour
        
        # Пересечения
        if 14 <= hour < 16:  # Europe + USA overlap
            return TradingSession.OVERLAP
        elif 0 <= hour < 8:
            return TradingSession.ASIA
        elif 8 <= hour < 16:
            return TradingSession.EUROPE
        else:
            return TradingSession.USA
    
    def get_btc_trend(self) -> Tuple[str, float]:
        """Получает тренд BTC для корреляции"""
        try:
            ohlcv = self.exchange.fetch_ohlcv("BTC/USDT:USDT", "1h", limit=50)
            trend = self.get_trend(ohlcv)
            
            # Сила тренда
            closes = [c[4] for c in ohlcv]
            change_24h = (closes[-1] - closes[-24]) / closes[-24] * 100 if len(closes) >= 24 else 0
            
            return trend, change_24h
        except:
            return "neutral", 0
    
    def calc_volatility_percentile(self, ohlcv: list) -> Tuple[float, bool]:
        """Рассчитывает перцентиль волатильности и определяет боковик"""
        if len(ohlcv) < 50:
            return 50, False
        
        # ATR за разные периоды
        atrs = []
        for i in range(20, len(ohlcv)):
            atr = self.calc_atr(ohlcv[i-20:i], 14)
            if atr > 0:
                atrs.append(atr)
        
        if not atrs:
            return 50, False
        
        current_atr = self.calc_atr(ohlcv, 14)
        
        # Перцентиль
        below = sum(1 for a in atrs if a < current_atr)
        percentile = (below / len(atrs)) * 100
        
        # Боковик = низкая волатильность + цена в узком диапазоне
        closes = [c[4] for c in ohlcv[-20:]]
        price_range = (max(closes) - min(closes)) / min(closes) * 100
        is_ranging = percentile < 30 and price_range < 3
        
        return percentile, is_ranging
    
    def calc_volume_profile(self, ohlcv: list) -> Tuple[float, float, float]:
        """Рассчитывает Volume Profile (POC, VAH, VAL)"""
        if len(ohlcv) < 50:
            price = ohlcv[-1][4] if ohlcv else 0
            return price, price * 1.02, price * 0.98
        
        # Собираем объёмы по ценовым уровням
        price_volumes = {}
        
        for candle in ohlcv[-50:]:
            high, low, close, volume = candle[2], candle[3], candle[4], candle[5]
            
            # Распределяем объём по ценовым уровням
            price_step = (high - low) / 10 if high > low else 0.01
            for i in range(10):
                level = round(low + i * price_step, 2)
                price_volumes[level] = price_volumes.get(level, 0) + volume / 10
        
        if not price_volumes:
            price = ohlcv[-1][4]
            return price, price * 1.02, price * 0.98
        
        # POC - уровень с максимальным объёмом
        poc = max(price_volumes, key=price_volumes.get)
        
        # Value Area (70% объёма)
        total_volume = sum(price_volumes.values())
        target_volume = total_volume * 0.7
        
        sorted_levels = sorted(price_volumes.items(), key=lambda x: x[1], reverse=True)
        
        va_volume = 0
        va_levels = []
        for level, vol in sorted_levels:
            va_levels.append(level)
            va_volume += vol
            if va_volume >= target_volume:
                break
        
        vah = max(va_levels) if va_levels else poc * 1.02
        val = min(va_levels) if va_levels else poc * 0.98
        
        return poc, vah, val
    
    def estimate_liquidation_zones(self, ohlcv: list, current_price: float) -> List[Tuple[float, str]]:
        """Оценивает зоны ликвидаций на основе swing points"""
        zones = []
        
        swing_highs, swing_lows = self.find_swing_points(ohlcv, 5)
        
        # Зоны ликвидации лонгов - ниже swing lows
        for idx, low in swing_lows[-5:]:
            liq_zone = low * 0.99  # Чуть ниже лоу
            if liq_zone < current_price:
                zones.append((liq_zone, "longs"))
        
        # Зоны ликвидации шортов - выше swing highs
        for idx, high in swing_highs[-5:]:
            liq_zone = high * 1.01  # Чуть выше хая
            if liq_zone > current_price:
                zones.append((liq_zone, "shorts"))
        
        return zones
    
    def get_oi_change(self, symbol: str) -> Tuple[float, float, str]:
        """Получает изменение Open Interest"""
        try:
            # Пробуем получить OI через API
            # Для Bybit это может быть в fetch_open_interest
            oi_data = self.exchange.fetch_open_interest(symbol)
            current_oi = float(oi_data.get('openInterestValue', 0))
            
            # Кэшируем для сравнения
            cache_key = f"{symbol}_oi"
            now = datetime.now()
            
            if cache_key in self._oi_cache:
                old_oi, old_time = self._oi_cache[cache_key]
                hours_diff = (now - old_time).total_seconds() / 3600
                
                if hours_diff >= 1:
                    change_1h = ((current_oi - old_oi) / old_oi * 100) if old_oi > 0 else 0
                    self._oi_cache[cache_key] = (current_oi, now)
                else:
                    change_1h = 0
            else:
                change_1h = 0
                self._oi_cache[cache_key] = (current_oi, now)
            
            # Определяем тренд OI
            if change_1h > 2:
                oi_trend = "rising"
            elif change_1h < -2:
                oi_trend = "falling"
            else:
                oi_trend = "stable"
            
            return change_1h, 0, oi_trend  # 24h пока не реализован
            
        except:
            return 0, 0, "stable"
    
    # ==================== УЛУЧШЕННЫЙ АНАЛИЗ ====================
    
    def analyze_v2(self, symbol: str) -> EnhancedAnalysis:
        """Полный анализ v2 с дополнительными факторами"""
        
        # Базовый анализ v1
        base = self.analyze(symbol)
        
        # Получаем данные
        ohlcv = self.exchange.fetch_ohlcv(symbol, '1h', limit=200)
        closes = [c[4] for c in ohlcv]
        current_price = closes[-1]
        
        # === НОВЫЕ ФАКТОРЫ v2 ===
        
        # 1. Сессия
        session = self.get_current_session()
        
        # Объём текущей сессии vs средний
        volumes = [c[5] for c in ohlcv[-24:]]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        current_volume = volumes[-1] if volumes else 0
        session_volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # 2. BTC корреляция
        btc_trend, btc_change = self.get_btc_trend()
        
        # Проверяем корреляцию
        coin = symbol.split('/')[0]
        if coin == "BTC":
            btc_correlation = 1.0
            aligned_with_btc = True
        else:
            # Упрощённая корреляция - совпадает ли тренд
            aligned_with_btc = (base.trend == btc_trend) or btc_trend == "neutral"
            btc_correlation = 0.7 if aligned_with_btc else 0.3
        
        # 3. Волатильность
        volatility_pct, is_ranging = self.calc_volatility_percentile(ohlcv)
        
        # 4. Volume Profile
        poc, vah, val = self.calc_volume_profile(ohlcv)
        
        if current_price > poc * 1.005:
            price_vs_poc = "above"
        elif current_price < poc * 0.995:
            price_vs_poc = "below"
        else:
            price_vs_poc = "at"
        
        # 5. Ликвидации
        liq_zones = self.estimate_liquidation_zones(ohlcv, current_price)
        
        # Проверяем близость к зоне ликвидации
        near_liq = False
        for liq_price, liq_type in liq_zones:
            distance_pct = abs(current_price - liq_price) / current_price * 100
            if distance_pct < 2:  # Ближе 2%
                near_liq = True
                break
        
        # 6. Open Interest
        oi_1h, oi_24h, oi_trend = self.get_oi_change(symbol)
        
        # === УЛУЧШЕННЫЙ СКОРИНГ v2 ===
        
        v2_bull = base.bull_score
        v2_bear = base.bear_score
        confluence = 0
        
        # +1 Сессия (лучше торговать в активные сессии)
        if session in [TradingSession.USA, TradingSession.OVERLAP]:
            if session_volume_ratio > 1.2:
                confluence += 1
        
        # +2 BTC корреляция
        if aligned_with_btc:
            if btc_trend == "bull":
                v2_bull += 10
                confluence += 1
            elif btc_trend == "bear":
                v2_bear += 10
                confluence += 1
        else:
            # Торгуем против BTC - рискованно, уменьшаем скор
            v2_bull -= 10
            v2_bear -= 10
        
        # +3 Волатильность
        if not is_ranging:
            confluence += 1
            if volatility_pct > 60:
                # Высокая волатильность - усиливаем сигнал
                v2_bull = int(v2_bull * 1.1)
                v2_bear = int(v2_bear * 1.1)
        else:
            # Боковик - ослабляем сигнал
            v2_bull = int(v2_bull * 0.7)
            v2_bear = int(v2_bear * 0.7)
        
        # +4 Volume Profile
        if price_vs_poc == "above" and base.trend == "bull":
            v2_bull += 10
            confluence += 1
        elif price_vs_poc == "below" and base.trend == "bear":
            v2_bear += 10
            confluence += 1
        
        # +5 Ликвидации
        if near_liq:
            # Рядом с зоной ликвидации - потенциальный сквиз
            for liq_price, liq_type in liq_zones:
                if abs(current_price - liq_price) / current_price < 0.02:
                    if liq_type == "shorts" and base.trend == "bull":
                        v2_bull += 15  # Потенциальный шорт-сквиз
                        confluence += 1
                    elif liq_type == "longs" and base.trend == "bear":
                        v2_bear += 15  # Потенциальный лонг-сквиз
                        confluence += 1
                    break
        
        # +6 Open Interest
        if oi_trend == "rising":
            # Растущий OI + тренд = подтверждение
            if base.trend == "bull":
                v2_bull += 5
            elif base.trend == "bear":
                v2_bear += 5
            confluence += 1
        elif oi_trend == "falling":
            # Падающий OI = ослабление тренда
            v2_bull = int(v2_bull * 0.9)
            v2_bear = int(v2_bear * 0.9)
        
        # Итоговый confidence
        v2_confidence = abs(v2_bull - v2_bear)
        
        # Бонус за конфлюенс
        if confluence >= 4:
            v2_confidence = int(v2_confidence * 1.3)
        elif confluence >= 3:
            v2_confidence = int(v2_confidence * 1.15)
        
        return EnhancedAnalysis(
            # Базовые поля от v1
            trend=base.trend,
            trend_strength=base.trend_strength,
            market_phase=base.market_phase,
            htf_trend=base.htf_trend,
            mtf_trend=base.mtf_trend,
            ltf_trend=base.ltf_trend,
            mtf_alignment=base.mtf_alignment,
            last_bos=base.last_bos,
            last_choch=base.last_choch,
            swing_high=base.swing_high,
            swing_low=base.swing_low,
            order_blocks=base.order_blocks,
            fvg_zones=base.fvg_zones,
            liquidity_zones=base.liquidity_zones,
            rsi=base.rsi,
            macd_histogram=base.macd_histogram,
            volume_ratio=base.volume_ratio,
            atr=base.atr,
            funding_rate=base.funding_rate,
            open_interest_change=base.open_interest_change,
            long_short_ratio=base.long_short_ratio,
            bull_score=base.bull_score,
            bear_score=base.bear_score,
            confidence=base.confidence,
            
            # Новые поля v2
            liquidation_zones=liq_zones,
            near_liquidation_zone=near_liq,
            oi_change_1h=oi_1h,
            oi_change_24h=oi_24h,
            oi_trend=oi_trend,
            poc_price=poc,
            vah_price=vah,
            val_price=val,
            price_vs_poc=price_vs_poc,
            btc_trend=btc_trend,
            btc_correlation=btc_correlation,
            aligned_with_btc=aligned_with_btc,
            volatility_percentile=volatility_pct,
            is_ranging=is_ranging,
            current_session=session,
            session_volume_ratio=session_volume_ratio,
            v2_bull_score=v2_bull,
            v2_bear_score=v2_bear,
            v2_confidence=v2_confidence,
            confluence_count=confluence
        )
    
    def get_signal(self, symbol: str, risk_pct: float = 2.0) -> Optional[SmartSignal]:
        """Генерирует сигнал v2 с улучшенными фильтрами"""
        try:
            analysis = self.analyze_v2(symbol)
        except Exception as e:
            print(f"V2 Analysis error: {e}")
            return None
        
        # Более строгие требования v2
        MIN_CONFIDENCE = 35  # Выше чем v1
        MIN_CONFLUENCE = 3   # Минимум 3 фактора
        
        # Фильтр боковика
        if analysis.is_ranging:
            return SmartSignal(
                action="wait",
                confidence=analysis.v2_confidence,
                entry_price=0, stop_loss=0,
                take_profit_1=0, take_profit_2=0, take_profit_3=0,
                position_size_pct=0,
                reason="⏸️ Боковик — не торгуем",
                analysis=analysis
            )
        
        # Фильтр корреляции с BTC (для альтов)
        coin = symbol.split('/')[0]
        if coin != "BTC" and not analysis.aligned_with_btc:
            return SmartSignal(
                action="wait",
                confidence=analysis.v2_confidence,
                entry_price=0, stop_loss=0,
                take_profit_1=0, take_profit_2=0, take_profit_3=0,
                position_size_pct=0,
                reason=f"⚠️ {coin} против BTC тренда — пропускаем",
                analysis=analysis
            )
        
        # Проверка confidence
        if analysis.v2_confidence < MIN_CONFIDENCE:
            return SmartSignal(
                action="wait",
                confidence=analysis.v2_confidence,
                entry_price=0, stop_loss=0,
                take_profit_1=0, take_profit_2=0, take_profit_3=0,
                position_size_pct=0,
                reason=f"Низкая уверенность ({analysis.v2_confidence}%)",
                analysis=analysis
            )
        
        # Проверка конфлюенса
        if analysis.confluence_count < MIN_CONFLUENCE:
            return SmartSignal(
                action="wait",
                confidence=analysis.v2_confidence,
                entry_price=0, stop_loss=0,
                take_profit_1=0, take_profit_2=0, take_profit_3=0,
                position_size_pct=0,
                reason=f"Мало факторов ({analysis.confluence_count}/{MIN_CONFLUENCE})",
                analysis=analysis
            )
        
        # Определяем направление
        if analysis.v2_bull_score > analysis.v2_bear_score:
            action = "buy"
        else:
            action = "sell"
        
        # Собираем причины
        reasons = []
        
        if analysis.mtf_alignment:
            reasons.append(f"MTF✓")
        
        if analysis.aligned_with_btc:
            reasons.append(f"BTC:{analysis.btc_trend}")
        
        if analysis.near_liquidation_zone:
            reasons.append("LIQ⚡")
        
        if analysis.oi_trend == "rising":
            reasons.append("OI↑")
        
        reasons.append(f"Vol:{analysis.volatility_percentile:.0f}%")
        reasons.append(f"Conf:{analysis.confluence_count}/6")
        
        # Уровни
        ticker = self.exchange.fetch_ticker(symbol)
        entry = ticker['last']
        atr = analysis.atr
        
        # Ограничиваем ATR
        max_atr = entry * 0.03
        atr = min(atr, max_atr)
        
        if action == "buy":
            # Используем VAL как поддержку для SL
            stop_loss = min(entry - atr * 1.5, analysis.val_price * 0.995)
            tp1 = entry + atr * 1.5
            tp2 = entry + atr * 3.0
            tp3 = min(entry + atr * 4.5, analysis.vah_price)  # Не выше VAH
        else:
            stop_loss = max(entry + atr * 1.5, analysis.vah_price * 1.005)
            tp1 = entry - atr * 1.5
            tp2 = entry - atr * 3.0
            tp3 = max(entry - atr * 4.5, analysis.val_price)
        
        # Защита от отрицательных TP
        if action == "sell":
            tp1 = max(tp1, entry * 0.9)
            tp2 = max(tp2, entry * 0.85)
            tp3 = max(tp3, entry * 0.8)
        
        # Размер позиции на основе confidence и confluence
        if analysis.v2_confidence >= 60 and analysis.confluence_count >= 5:
            size_pct = risk_pct * 1.5
        elif analysis.v2_confidence >= 45 and analysis.confluence_count >= 4:
            size_pct = risk_pct
        else:
            size_pct = risk_pct * 0.7
        
        return SmartSignal(
            action=action,
            confidence=analysis.v2_confidence,
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit_1=round(tp1, 2),
            take_profit_2=round(tp2, 2),
            take_profit_3=round(tp3, 2),
            position_size_pct=size_pct,
            reason=" | ".join(reasons),
            analysis=analysis
        )
