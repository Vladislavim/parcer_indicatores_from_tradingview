from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests
from PySide6.QtCore import QThread, Signal


# ====== Пытаемся импортировать реальные индикаторы ======
# Если в модуле нет get_signal, используем временную заглушку
def _stub_ema(symbol: str, timeframe: str, source: str):
    return "neutral", "EMA/BOS (демо режим)"


def _stub_sm(symbol: str, timeframe: str, source: str):
    return "neutral", "Smart Money (демо режим)"


def _stub_cf(symbol: str, timeframe: str, source: str):
    return "neutral", "Confirmations (демо режим)"


try:
    from indicators.boswaves_ema_market_structure import (  # type: ignore
        get_signal as ema_ms_get_signal,
    )
except Exception:
    ema_ms_get_signal = _stub_ema  # type: ignore

try:
    from indicators.algoalpha_smart_money_breakout import (  # type: ignore
        get_signal as sm_get_signal,
    )
except Exception:
    sm_get_signal = _stub_sm  # type: ignore

try:
    from indicators.confirmation_stack import (  # type: ignore
        get_signal as cf_get_signal,
    )
except Exception:
    cf_get_signal = _stub_cf  # type: ignore


# ====== HTF (Higher Timeframe) маппинг ======
HTF_MAP = {
    "1m": "15m",   # 1 мин -> смотрим 15 мин
    "5m": "1h",    # 5 мин -> смотрим 1 час
    "15m": "4h",   # 15 мин -> смотрим 4 часа
    "1h": "4h",    # 1 час -> смотрим 4 часа
    "4h": "1d",    # 4 часа -> смотрим день
    "1d": "1w",    # день -> смотрим неделю
}


# ====== Общие структуры ======


@dataclass
class IndicatorState:
    status: str        # bull / bear / neutral / na
    detail: str        # короткий текст для UI/Telegram
    raw: dict          # сырые данные по индикатору (если надо)


@dataclass
class CompositeSignal:
    symbol: str
    status: str                     # bull / bear / neutral
    indicators: Dict[str, IndicatorState]


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ========= Telegram =========

def send_telegram_message(token: str,
                          chat_id: str,
                          text: str,
                          thread_id: Optional[int] = None) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


# ========= Worker =========

class Worker(QThread):
    log = Signal(str)  # строка в лог
    status = Signal(str, str, str, str, str)
    # (symbol(base), indicator_key, status, detail, updated_str)
    
    # Новые сигналы для улучшенного UX
    progress = Signal(int)  # прогресс обработки (0-100)
    error = Signal(str)     # критические ошибки
    notification = Signal(str, str)  # (message, type) для тостов

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._stop = threading.Event()
        self.prev_composite: Dict[str, CompositeSignal] = {}
        self.htf_trend: Dict[str, str] = {}  # {symbol: "bull"/"bear"/"neutral"}
        self.htf_last_update: Dict[str, float] = {}  # когда обновляли HTF
        
        # Статистика
        self.stats = {
            "total_cycles": 0,
            "successful_cycles": 0,
            "errors": 0,
            "signals_sent": 0,
            "filtered_by_htf": 0  # сколько сигналов отфильтровано HTF
        }

    # ------- служебное -------

    def stop(self):
        self._stop.set()
        
    # ------- HTF (Higher Timeframe) анализ -------
    
    def _get_htf_trend(self, symbol: str) -> str:
        """
        Получить тренд на старшем таймфрейме.
        Обновляем раз в 5 минут чтобы не спамить API.
        """
        now = time.time()
        last_update = self.htf_last_update.get(symbol, 0)
        
        # Кэшируем на 5 минут
        if symbol in self.htf_trend and (now - last_update) < 300:
            return self.htf_trend[symbol]
        
        # Горячее обновление таймфрейма и биржи
        get_timeframe = self.cfg.get("get_timeframe")
        if get_timeframe and callable(get_timeframe):
            try:
                tf = get_timeframe()
            except:
                tf = self.cfg["timeframe"]
        else:
            tf = self.cfg["timeframe"]
            
        get_source = self.cfg.get("get_source")
        if get_source and callable(get_source):
            try:
                src = get_source()
            except:
                src = self.cfg["source"]
        else:
            src = self.cfg["source"]
        
        htf = HTF_MAP.get(tf, "4h")
        
        try:
            # Используем EMA индикатор для определения тренда на HTF
            res = ema_ms_get_signal(symbol, htf, src)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                htf_status = str(res[0])
            else:
                htf_status = "neutral"
                
            self.htf_trend[symbol] = htf_status
            self.htf_last_update[symbol] = now
            self.log.emit(f"[{symbol}] HTF ({htf}): {htf_status}")
            return htf_status
            
        except Exception as e:
            self.log.emit(f"[{symbol}] HTF error: {e}")
            return "neutral"  # При ошибке не блокируем сигналы

    # ------- обёртки вокруг реальных индикаторов -------

    def _to_state(self, result: Any, fallback_detail: str) -> IndicatorState:
        """
        Приводим результат функций индикаторов к IndicatorState.

        Поддерживаем два варианта:
        1) функция вернула уже IndicatorState
        2) функция вернула кортеж (status, detail)
        """
        if isinstance(result, IndicatorState):
            return result
        if isinstance(result, (list, tuple)) and len(result) >= 1:
            status = str(result[0])
            detail = str(result[1]) if len(result) > 1 else fallback_detail
            return IndicatorState(status=status, detail=detail, raw={})
        # если что-то другое — считаем, что индикатор не дал сигнал
        return IndicatorState(status="na", detail=fallback_detail, raw={"raw": result})

    def _get_live_source(self) -> str:
        """Получить актуальную биржу (с горячим обновлением)"""
        get_source = self.cfg.get("get_source")
        if get_source and callable(get_source):
            try:
                return get_source()
            except:
                pass
        return self.cfg["source"]
    
    def _get_live_timeframe(self) -> str:
        """Получить актуальный таймфрейм (с горячим обновлением)"""
        get_timeframe = self.cfg.get("get_timeframe")
        if get_timeframe and callable(get_timeframe):
            try:
                return get_timeframe()
            except:
                pass
        return self.cfg["timeframe"]

    def _calc_ema_ms(self, symbol: str) -> IndicatorState:
        src = self._get_live_source()
        tf = self._get_live_timeframe()
        try:
            res = ema_ms_get_signal(symbol, tf, src)
            state = self._to_state(res, "EMA/BOS")
            return state
        except Exception as e:
            self.log.emit(f"[{symbol}] EMA_MS error: {e}")
            return IndicatorState(status="na", detail="EMA/BOS error", raw={"error": str(e)})

    def _calc_smart_money(self, symbol: str) -> IndicatorState:
        src = self._get_live_source()
        tf = self._get_live_timeframe()
        try:
            res = sm_get_signal(symbol, tf, src)
            state = self._to_state(res, "Smart Money")
            return state
        except Exception as e:
            self.log.emit(f"[{symbol}] SmartMoney error: {e}")
            return IndicatorState(status="na", detail="SmartMoney error", raw={"error": str(e)})

    def _calc_confirmations(self, symbol: str) -> IndicatorState:
        src = self._get_live_source()
        tf = self._get_live_timeframe()
        try:
            res = cf_get_signal(symbol, tf, src)
            state = self._to_state(res, "Confirmations")
            return state
        except Exception as e:
            self.log.emit(f"[{symbol}] Confirmations error: {e}")
            return IndicatorState(status="na", detail="Confirmations error", raw={"error": str(e)})

    def _calc_all_indicators(self, symbol: str, enabled: List[str]) -> Dict[str, IndicatorState]:
        out: Dict[str, IndicatorState] = {}
        if "ema_ms" in enabled:
            out["ema_ms"] = self._calc_ema_ms(symbol)
        if "smart_money" in enabled:
            out["smart_money"] = self._calc_smart_money(symbol)
        if "confirmations" in enabled:
            out["confirmations"] = self._calc_confirmations(symbol)
        return out

    # ------- сводный статус -------

    @staticmethod
    def _compose_status(ind_states: Dict[str, IndicatorState]) -> str:
        bulls = sum(1 for s in ind_states.values() if s.status == "bull")
        bears = sum(1 for s in ind_states.values() if s.status == "bear")

        if bulls > bears and bulls > 0:
            return "bull"
        if bears > bulls and bears > 0:
            return "bear"
        return "neutral"

    # ------- форматирование Telegram -------

    def _format_telegram_message(
        self,
        symbol: str,
        direction: str,
        indicators: Dict[str, IndicatorState],
        strength: int,
        htf_trend: str,
    ) -> str:
        """Форматирование сообщения для конфлюенс-сигнала"""
        
        tf = self._get_live_timeframe()
        htf = HTF_MAP.get(tf, "4h")
        
        # Эмодзи и текст в зависимости от силы
        if strength == 3:
            header_emoji = "🔥" if direction == "bull" else "💀"
            strength_text = "СИЛЬНЫЙ"
            strength_bar = "███████████"
        elif strength == 2:
            header_emoji = "🟢" if direction == "bull" else "🔴"
            strength_text = "Хороший"
            strength_bar = "███████░░░░"
        else:
            header_emoji = "⚪"
            strength_text = "Слабый"
            strength_bar = "███░░░░░░░░"
        
        direction_text = "ЛОНГ 📈" if direction == "bull" else "ШОРТ 📉"
        htf_emoji = "🟢" if htf_trend == "bull" else "🔴" if htf_trend == "bear" else "⚪"
        htf_text = "бычий" if htf_trend == "bull" else "медвежий" if htf_trend == "bear" else "боковик"
        
        # Названия индикаторов
        ind_names = {
            "ema_ms": "EMA",
            "smart_money": "SM",
            "confirmations": "CONF"
        }
        
        ind_emoji = {
            "bull": "🟢",
            "bear": "🔴",
            "neutral": "⚪",
            "na": "⏳"
        }
        
        lines = [
            f"{header_emoji} <b>{symbol}</b> — <b>{direction_text}</b>",
            f"",
            f"⚡ {strength_text} [{strength_bar}]",
            f"{htf_emoji} HTF ({htf}): {htf_text}",
            f"",
        ]
        
        # Показываем все индикаторы
        for key, state in indicators.items():
            emoji = ind_emoji.get(state.status, "⏳")
            name = ind_names.get(key, key)
            lines.append(f"{emoji} {name}: {state.detail}")
        
        lines.extend([
            f"",
            f"⏰ {datetime.now().strftime('%H:%M:%S')} | ТФ: {tf}"
        ])

        return "\n".join(lines)

    def _notify_if_changed(
        self,
        symbol: str,
        prev: Optional[CompositeSignal],
        cur: CompositeSignal,
    ):
        """
        Умная система уведомлений как у топ-трейдера:
        
        1. HTF ФИЛЬТР - не торгуем против старшего ТФ
           - Лонг только если HTF = bull или neutral
           - Шорт только если HTF = bear или neutral
           
        2. КОНФЛЮЕНС - минимум 2/3 индикатора в одну сторону
        
        3. АНТИСПАМ - только при смене направления или усилении
        """
        token = self.cfg.get("tg_token") or ""
        chat = self.cfg.get("tg_chat") or ""
        if not token or not chat:
            return

        # Горячее обновление списка монет через callback
        get_alert_symbols = self.cfg.get("get_alert_symbols")
        if get_alert_symbols and callable(get_alert_symbols):
            try:
                alert_symbols = set(get_alert_symbols())
            except:
                alert_symbols = set(self.cfg.get("alert_symbols", []))
        else:
            alert_symbols = set(self.cfg.get("alert_symbols", []))
        
        # Проверяем символ
        symbol_variants = [symbol, f"{symbol}USDT.P", symbol.replace("USDT", "USDT.P")]
        symbol_in_alerts = any(s in alert_symbols or s.replace(".P", "") in [a.replace(".P", "") for a in alert_symbols] for s in symbol_variants)
        
        if not symbol_in_alerts:
            return

        # Считаем силу сигнала
        bulls = sum(1 for s in cur.indicators.values() if s.status == "bull")
        bears = sum(1 for s in cur.indicators.values() if s.status == "bear")
        
        # Определяем направление и силу
        if bulls >= 2 and bulls > bears:
            direction = "bull"
            strength = bulls
        elif bears >= 2 and bears > bulls:
            direction = "bear"
            strength = bears
        else:
            # Нет конфлюенса — не отправляем
            return
        
        # === HTF ФИЛЬТР ===
        # symbol уже в формате "BTCUSDT" (без .P)
        htf_symbol = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        htf_trend = self._get_htf_trend(htf_symbol)
        
        # Не торгуем против тренда на старшем ТФ
        if direction == "bull" and htf_trend == "bear":
            self.stats["filtered_by_htf"] += 1
            self.log.emit(f"[{symbol}] ЛОНГ отфильтрован — HTF медвежий")
            return
        if direction == "bear" and htf_trend == "bull":
            self.stats["filtered_by_htf"] += 1
            self.log.emit(f"[{symbol}] ШОРТ отфильтрован — HTF бычий")
            return
        
        # Проверяем изменение направления (не спамим одинаковыми сигналами)
        prev_direction = None
        if prev:
            prev_bulls = sum(1 for s in prev.indicators.values() if s.status == "bull")
            prev_bears = sum(1 for s in prev.indicators.values() if s.status == "bear")
            if prev_bulls >= 2 and prev_bulls > prev_bears:
                prev_direction = "bull"
            elif prev_bears >= 2 and prev_bears > prev_bulls:
                prev_direction = "bear"
        
        # Отправляем только если направление изменилось или усилилось
        if prev_direction == direction:
            # Проверяем усиление (было 2, стало 3)
            if prev:
                prev_strength = max(
                    sum(1 for s in prev.indicators.values() if s.status == "bull"),
                    sum(1 for s in prev.indicators.values() if s.status == "bear")
                )
                if strength <= prev_strength:
                    return  # Сила не увеличилась — не спамим
        
        htf_text = "по тренду" if htf_trend == direction else "нейтрал"
        self.log.emit(f"[{symbol}] КОНФЛЮЕНС {direction.upper()} ({strength}/3) HTF: {htf_text}")
        
        mention = self.cfg.get("tg_mention", "").strip()
        text = self._format_telegram_message(symbol, direction, cur.indicators, strength, htf_trend)
        
        if mention:
            text += f"\n\n{mention}"

        try:
            send_telegram_message(
                token,
                chat,
                text,
                thread_id=self.cfg.get("tg_thread"),
            )
            self.stats["signals_sent"] += 1
            self.log.emit(f"Telegram: {symbol} {direction} {strength}/3")
            self.notification.emit(f"{symbol}: {direction.upper()} {strength}/3", "success")
        except Exception as e:
            self.stats["errors"] += 1
            self.log.emit(f"Telegram error: {e}")
            self.error.emit(f"Telegram error: {e}")

    # ------- основной цикл -------

    def run(self):
        src = self._get_live_source()
        tf = self._get_live_timeframe()
        symbols: List[str] = self.cfg["symbols"]
        enabled_inds: List[str] = self.cfg["indicators"]
        
        # Умная логика интервалов в зависимости от таймфрейма
        timeframe_intervals = {
            "1m": 15,   # Каждые 15 секунд для 1-минутных свечей
            "5m": 30,   # Каждые 30 секунд для 5-минутных
            "15m": 60,  # Каждую минуту для 15-минутных
            "1h": 120,  # Каждые 2 минуты для часовых
            "4h": 300,  # Каждые 5 минут для 4-часовых
            "1d": 600   # Каждые 10 минут для дневных
        }
        
        poll_sec = timeframe_intervals.get(tf, 60)  # По умолчанию 60 секунд
        alert_symbols = set(self.cfg.get("alert_symbols", []))

        self.log.emit(
            f"Воркер запущен: {src}, ТФ={tf}, интервал={poll_sec}с, "
            f"мониторинг {len(symbols)} монет, {len(enabled_inds)} индикаторов, "
            f"{len(alert_symbols)} уведомлений"
        )
        
        self.notification.emit("Мониторинг успешно запущен!", "success")

        # Информация о времени ожидания сигналов
        signal_info = {
            "1m": "Сигналы каждые 15-30 секунд (быстрые изменения)",
            "5m": "Сигналы каждые 30-60 секунд (средняя скорость)",
            "15m": "Сигналы каждые 1-2 минуты (стабильные)",
            "1h": "Сигналы каждые 2-5 минут (надежные)",
            "4h": "Сигналы каждые 5-15 минут (сильные)",
            "1d": "Сигналы каждые 10-30 минут (долгосрочные)"
        }
        
        if tf in signal_info:
            self.log.emit(f"📊 {signal_info[tf]}")
            self.notification.emit(signal_info[tf], "info")
        
        # Отслеживаем изменения настроек
        last_tf = tf
        last_src = src

        while not self._stop.is_set():
            loop_start = time.time()
            self.stats["total_cycles"] += 1
            
            # Проверяем изменения настроек
            current_tf = self._get_live_timeframe()
            current_src = self._get_live_source()
            
            if current_tf != last_tf or current_src != last_src:
                poll_sec = timeframe_intervals.get(current_tf, 60)
                self.log.emit(f"⚡ Настройки обновлены: {current_src}, ТФ={current_tf}, интервал={poll_sec}с")
                # Сбрасываем кэш HTF при смене настроек
                self.htf_trend.clear()
                self.htf_last_update.clear()
                last_tf = current_tf
                last_src = current_src
            
            try:
                successful_symbols = 0
                
                for i, sym in enumerate(symbols):
                    if self._stop.is_set():
                        break

                    # Обновляем прогресс
                    progress_pct = int((i / len(symbols)) * 100)
                    self.progress.emit(progress_pct)

                    base_sym = sym.replace(".P", "")

                    try:
                        ind_states = self._calc_all_indicators(sym, enabled_inds)
                        comp_status = self._compose_status(ind_states)

                        composite = CompositeSignal(
                            symbol=base_sym,
                            status=comp_status,
                            indicators=ind_states,
                        )

                        prev = self.prev_composite.get(base_sym)
                        self.prev_composite[base_sym] = composite

                        updated = now_str()

                        # сигнал в Dashboard
                        for key, state in ind_states.items():
                            self.status.emit(
                                base_sym,
                                key,
                                state.status,
                                state.detail,
                                updated,
                            )

                        # уведомление в Telegram
                        self._notify_if_changed(base_sym, prev, composite)
                        
                        successful_symbols += 1

                    except Exception as e:
                        self.stats["errors"] += 1
                        self.log.emit(f"[{sym}] Processing error: {e}")

                # Завершаем прогресс
                self.progress.emit(100)
                
                if successful_symbols == len(symbols):
                    self.stats["successful_cycles"] += 1
                    
                # Логируем статистику каждые 10 циклов
                if self.stats["total_cycles"] % 10 == 0:
                    success_rate = (self.stats["successful_cycles"] / self.stats["total_cycles"]) * 100
                    self.log.emit(
                        f"Stats: {self.stats['total_cycles']} циклов, "
                        f"{success_rate:.0f}% успех, {self.stats['signals_sent']} алертов, "
                        f"{self.stats['filtered_by_htf']} отфильтровано HTF"
                    )

            except Exception as e:
                self.stats["errors"] += 1
                self.log.emit(f"Critical cycle error: {e}")
                self.error.emit(f"Critical error in monitoring cycle: {e}")

            if self._stop.is_set():
                break

            elapsed = time.time() - loop_start
            sleep_for = max(0.0, poll_sec - elapsed)
            
            if sleep_for > 0:
                time.sleep(sleep_for)

        self.log.emit("Worker finished successfully")
        self.notification.emit("Monitoring stopped", "info")
