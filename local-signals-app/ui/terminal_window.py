"""
Bybit Terminal Pro - Полноценный торговый терминал
Автоторговля по стратегии с индикаторами
"""
from __future__ import annotations

import math
import threading
from datetime import datetime
from typing import List, Optional, Dict
from decimal import Decimal

from PySide6.QtCore import Qt, QTimer, QSettings, QThread, Signal, QObject
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QDialog,
    QLabel, QPushButton, QFrame, QLineEdit, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGraphicsDropShadowEffect, QMessageBox, 
    QScrollArea, QApplication, QComboBox, QGridLayout, QGroupBox
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

try:
    import ccxt
except ImportError:
    ccxt = None

from ui.styles import COLORS, get_current_theme


# Bybit logo URL
BYBIT_LOGO_URL = "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png"


class AutoTradeWorker(QThread):
    """Воркер для автоторговли в отдельном потоке"""
    log_signal = Signal(str)
    profit_signal = Signal(float)
    refresh_signal = Signal()
    open_position_signal = Signal(str, str, float, float, float, int)  # symbol, side, size, sl, tp, leverage
    close_position_signal = Signal(str, float, str)  # symbol, size, side
    
    def __init__(self, exchange, settings: dict, get_signal_func, get_htf_func):
        super().__init__()
        self.exchange = exchange
        self.settings = settings  # leverage, risk_pct, tf, selected_coins
        self.get_signal = get_signal_func
        self.get_htf = get_htf_func
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def run(self):
        """Выполняет проверку сигналов в отдельном потоке"""
        try:
            self._check_signals()
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка автоторговли: {e}")
            
    def _check_signals(self):
        if not self.exchange:
            return
            
        self.log_signal.emit("🔍 Проверяю сигналы...")
        
        leverage = self.settings['leverage']
        risk_pct = self.settings['risk_pct']
        tf = self.settings['tf']
        selected_coins = self.settings['selected_coins']
        
        # Получаем баланс
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            available = float(usdt.get('free') or 0)
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка получения баланса: {e}")
            return
        
        if available < 10:
            self.log_signal.emit("⚠️ Недостаточно средств")
            return
        
        self.log_signal.emit(f"⚙️ ТФ: {tf} | Плечо: {leverage}x | Риск: {risk_pct}%")
        
        if not selected_coins:
            self.log_signal.emit("⚠️ Не выбраны монеты")
            return
        
        # === АВТОЗАКРЫТИЕ ===
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка получения позиций: {e}")
            open_positions = []
        
        for pos in open_positions:
            if self._stop:
                return
                
            pos_symbol = pos.get('symbol', '')
            pos_side = (pos.get('side') or '').lower()
            pos_size = float(pos.get('contracts') or 0)
            pos_pnl = float(pos.get('unrealizedPnl') or 0)
            
            coin_from_pos = pos_symbol.split('/')[0] if '/' in pos_symbol else pos_symbol.replace('USDT', '')
            
            if coin_from_pos not in selected_coins:
                continue
            
            try:
                signal, strength, details = self.get_signal(coin_from_pos)
            except:
                continue
            
            should_close = False
            if pos_side == "long" and signal == "sell" and strength >= 2:
                should_close = True
                self.log_signal.emit(f"🔄 Закрываю {coin_from_pos} LONG — Сигнал ШОРТ ({strength}/3)")
            elif pos_side == "short" and signal == "buy" and strength >= 2:
                should_close = True
                self.log_signal.emit(f"🔄 Закрываю {coin_from_pos} SHORT — Сигнал ЛОНГ ({strength}/3)")
            
            if should_close:
                try:
                    if pos_side == "long":
                        self.exchange.create_market_sell_order(pos_symbol, pos_size, {"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(pos_symbol, pos_size, {"reduceOnly": True})
                    
                    pnl_str = f"{'+'if pos_pnl>=0 else ''}${pos_pnl:.2f}"
                    self.log_signal.emit(f"✅ Закрыто {coin_from_pos} | PnL: {pnl_str}")
                    
                    if pos_pnl >= 5:
                        self.profit_signal.emit(pos_pnl)
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка закрытия: {e}")
        
        # === ОТКРЫТИЕ НОВЫХ ПОЗИЦИЙ ===
        for coin in selected_coins:
            if self._stop:
                return
                
            symbol = f"{coin}/USDT:USDT"
            
            has_position = any(
                p.get('symbol') == symbol and float(p.get('contracts') or 0) > 0 
                for p in open_positions
            )
            
            if has_position:
                continue
            
            try:
                signal, strength, details = self.get_signal(coin)
                self.log_signal.emit(f"📊 {coin}: {details} → {signal} ({strength}/3)")
            except Exception as e:
                self.log_signal.emit(f"⚠️ {coin}: ошибка сигнала - {e}")
                continue
            
            if signal in ["buy", "sell"] and strength >= 2:
                try:
                    htf_trend = self.get_htf(coin, tf)
                except:
                    htf_trend = "neutral"
                
                if signal == "buy" and htf_trend == "bear":
                    self.log_signal.emit(f"⏭️ {coin} ЛОНГ пропущен — HTF медвежий")
                    continue
                if signal == "sell" and htf_trend == "bull":
                    self.log_signal.emit(f"⏭️ {coin} ШОРТ пропущен — HTF бычий")
                    continue
                
                htf_emoji = "🟢" if htf_trend == "bull" else "🔴" if htf_trend == "bear" else "⚪"
                
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    
                    position_usdt = available * (risk_pct / 100)
                    size = (position_usdt * leverage) / price
                    
                    if coin == "BTC":
                        size = round(size, 3)
                    elif coin in ["ETH", "SOL"]:
                        size = round(size, 2)
                    else:
                        size = round(size, 1)
                        
                    if size < 0.001:
                        continue
                        
                    sl_pct = 2.0
                    tp_pct = 4.0
                    
                    direction = "ЛОНГ 📈" if signal == "buy" else "ШОРТ 📉"
                    self.log_signal.emit(f"🔥 КОНФЛЮЕНС {direction} {coin} ({strength}/3) {htf_emoji}HTF")
                    self.log_signal.emit(f"   {details}")
                    self.log_signal.emit(f"   Размер: {size} | Плечо: {leverage}x")
                    
                    # Отправляем сигнал для открытия в главном потоке
                    self.open_position_signal.emit(symbol, signal, size, sl_pct, tp_pct, leverage)
                    
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка открытия {coin}: {e}")
        
        self.refresh_signal.emit()


class ConnectWorker(QThread):
    """Воркер для подключения к API в отдельном потоке"""
    success = Signal(object)  # exchange object
    error = Signal(str)
    log = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        
    def run(self):
        try:
            self.log.emit("🔄 Подключение к Bybit Testnet...")
            
            exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'sandbox': True,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'},
            })
            
            # Проверяем подключение
            exchange.fetch_balance()
            
            self.success.emit(exchange)
            
        except Exception as e:
            self.error.emit(str(e))


class RefreshWorker(QThread):
    """Воркер для обновления данных в отдельном потоке"""
    data_ready = Signal(float, float, float, list)  # available, total, pnl, positions
    price_ready = Signal(float)  # current price
    error = Signal(str)
    
    def __init__(self, exchange, symbol: str = None):
        super().__init__()
        self.exchange = exchange
        self.symbol = symbol
        
    def run(self):
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            
            available = float(usdt.get('free') or 0)
            total = float(usdt.get('total') or 0)
            
            positions = self.exchange.fetch_positions()
            open_pos = [p for p in positions if float(p.get('contracts') or 0) > 0]
            
            total_pnl = sum(float(p.get('unrealizedPnl') or 0) for p in open_pos)
            
            self.data_ready.emit(available, total, total_pnl, open_pos)
            
            # Получаем цену если указан символ
            if self.symbol:
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.price_ready.emit(ticker['last'])
                except:
                    pass
                    
        except Exception as e:
            self.error.emit(str(e))


class LogoLoader:
    """Загрузчик логотипа"""
    _pixmap: Optional[QPixmap] = None
    _manager: Optional[QNetworkAccessManager] = None
    _callbacks: List = []
    
    @classmethod
    def load(cls, callback):
        if cls._pixmap:
            callback(cls._pixmap)
            return
            
        cls._callbacks.append(callback)
        
        if cls._manager is None:
            from PySide6.QtCore import QUrl
            cls._manager = QNetworkAccessManager()
            request = QNetworkRequest(QUrl(BYBIT_LOGO_URL))
            reply = cls._manager.get(request)
            reply.finished.connect(lambda: cls._on_loaded(reply))
    
    @classmethod        
    def _on_loaded(cls, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data.data())
            if not pixmap.isNull():
                cls._pixmap = pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        for cb in cls._callbacks:
            cb(cls._pixmap)
        cls._callbacks.clear()
        reply.deleteLater()


class InstructionDialog(QDialog):
    """Диалог с инструкцией"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка Bybit API")
        self.setFixedSize(450, 420)
        self.setStyleSheet(f"background: {COLORS['bg_dark']};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("🔑 Получение API ключей Bybit Testnet")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(title)
        
        steps = QLabel(
            "1. Перейди на <b>testnet.bybit.com</b><br><br>"
            "2. Создай аккаунт (отдельный от реального)<br><br>"
            "3. <b>Assets → Derivatives → Request Test Coins</b><br><br>"
            "4. <b>Профиль → API Management → Create New Key</b><br><br>"
            "5. Тип: <b>API ключи, созданные системой</b><br><br>"
            "6. Разрешения: <b>Чтение и запись</b>, галочка <b>Ордера</b><br><br>"
            "7. Скопируй <b>API Key</b> и <b>Secret</b> в терминал"
        )
        steps.setStyleSheet(f"""
            font-size: 13px; color: {COLORS['text_muted']}; 
            background: {COLORS['bg_card']}; 
            padding: 16px; border-radius: 12px;
        """)
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.RichText)
        layout.addWidget(steps)
        
        link_btn = QPushButton("🌐 Открыть testnet.bybit.com")
        link_btn.setCursor(Qt.PointingHandCursor)
        link_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {COLORS['accent']};
                border-radius: 10px;
                color: {COLORS['accent']};
                font-size: 13px;
                padding: 10px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}
        """)
        link_btn.clicked.connect(self._open_link)
        layout.addWidget(link_btn)
        
        layout.addStretch()
        
        self.dont_show = QCheckBox("Больше не показывать")
        self.dont_show.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.dont_show)
        
        ok_btn = QPushButton("Понятно")
        ok_btn.setFixedHeight(44)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        
    def _open_link(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://testnet.bybit.com"))


class TerminalBackground(QWidget):
    """Анимированный фон"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time = 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)
        
    def _animate(self):
        self.time += 0.015
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor(13, 13, 15))
        bg.setColorAt(1, QColor(16, 16, 20))
        painter.fillRect(self.rect(), bg)
        
        # Subtle orbs
        orbs = [
            (0.15, 0.2, 250, (245, 158, 11, 20)),
            (0.85, 0.8, 300, (108, 92, 231, 15)),
        ]
        
        for ox, oy, radius, color in orbs:
            cx, cy = int(ox * w), int(oy * h)
            pulse = 1 + 0.1 * math.sin(self.time * 1.5 + ox * 5)
            r = int(radius * pulse)
            
            gradient = QRadialGradient(cx, cy, r)
            gradient.setColorAt(0, QColor(*color))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)


class BalanceWidget(QFrame):
    """Виджет баланса"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(24)
        
        # Available
        avail_layout = QVBoxLayout()
        avail_layout.setSpacing(2)
        avail_title = QLabel("Доступно")
        avail_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        avail_layout.addWidget(avail_title)
        self.avail_lbl = QLabel("$0.00")
        self.avail_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        avail_layout.addWidget(self.avail_lbl)
        layout.addLayout(avail_layout)
        
        # Equity
        equity_layout = QVBoxLayout()
        equity_layout.setSpacing(2)
        equity_title = QLabel("Эквити")
        equity_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        equity_layout.addWidget(equity_title)
        self.equity_lbl = QLabel("$0.00")
        self.equity_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        equity_layout.addWidget(self.equity_lbl)
        layout.addLayout(equity_layout)
        
        # Unrealized PnL
        pnl_layout = QVBoxLayout()
        pnl_layout.setSpacing(2)
        pnl_title = QLabel("Нереализ. PnL")
        pnl_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        pnl_layout.addWidget(pnl_title)
        self.pnl_lbl = QLabel("$0.00")
        self.pnl_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        pnl_layout.addWidget(self.pnl_lbl)
        layout.addLayout(pnl_layout)
        
        layout.addStretch()
        
    def update_balance(self, available: float, equity: float, pnl: float):
        self.avail_lbl.setText(f"${available:,.2f}")
        self.equity_lbl.setText(f"${equity:,.2f}")
        
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        pnl_sign = "+" if pnl >= 0 else ""
        self.pnl_lbl.setText(f"{pnl_sign}${pnl:,.2f}")
        self.pnl_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {pnl_color};")


class PositionRow(QFrame):
    """Строка позиции"""
    
    close_clicked = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = ""
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        self.setFixedHeight(52)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)
        
        self.symbol_lbl = QLabel("—")
        self.symbol_lbl.setFixedWidth(70)
        self.symbol_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(self.symbol_lbl)
        
        self.side_lbl = QLabel("—")
        self.side_lbl.setFixedWidth(60)
        layout.addWidget(self.side_lbl)
        
        self.size_lbl = QLabel("—")
        self.size_lbl.setFixedWidth(80)
        self.size_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        layout.addWidget(self.size_lbl)
        
        self.entry_lbl = QLabel("—")
        self.entry_lbl.setFixedWidth(90)
        self.entry_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.entry_lbl)
        
        self.mark_lbl = QLabel("—")
        self.mark_lbl.setFixedWidth(90)
        self.mark_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
        layout.addWidget(self.mark_lbl)
        
        self.pnl_lbl = QLabel("—")
        self.pnl_lbl.setFixedWidth(100)
        layout.addWidget(self.pnl_lbl)
        
        self.leverage_lbl = QLabel("—")
        self.leverage_lbl.setFixedWidth(40)
        self.leverage_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['warning']};")
        layout.addWidget(self.leverage_lbl)
        
        layout.addStretch()
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setFixedSize(70, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['danger']};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #ff4444; }}
        """)
        self.close_btn.clicked.connect(lambda: self.close_clicked.emit(self.symbol))
        layout.addWidget(self.close_btn)
        
    def update_data(self, symbol: str, side: str, size: float, entry: float, mark: float, pnl: float, pnl_pct: float, leverage: int):
        self.symbol = symbol
        
        self.symbol_lbl.setText(symbol.replace("/USDT:USDT", ""))
        
        side_color = COLORS['success'] if side == "long" else COLORS['danger']
        self.side_lbl.setText("ЛОНГ" if side == "long" else "ШОРТ")
        self.side_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {side_color};")
        
        self.size_lbl.setText(f"{size:.4f}")
        self.entry_lbl.setText(f"${entry:,.2f}")
        self.mark_lbl.setText(f"${mark:,.2f}")
        
        # Считаем процент вручную: PnL% = (PnL / маржа) * 100
        # Маржа = (размер * цена входа) / плечо
        if entry > 0 and leverage > 0:
            margin = (size * entry) / leverage
            if margin > 0:
                pnl_pct = (pnl / margin) * 100
        
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        pnl_sign = "+" if pnl >= 0 else ""
        self.pnl_lbl.setText(f"{pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.1f}%)")
        self.pnl_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {pnl_color};")
        
        self.leverage_lbl.setText(f"{leverage}x")


class OrderPanel(QFrame):
    """Панель создания ордера как на Bybit"""
    
    order_submitted = Signal(str, str, float, float, float, int)  # symbol, side, size, sl, tp, leverage
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_price = 0.0
        self.setStyleSheet(f"""
            QFrame#OrderPanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("OrderPanel")
        self.setMinimumHeight(480)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("📊 Новый ордер")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: white; background: transparent;")
        layout.addWidget(title)
        
        # Монета
        layout.addWidget(self._create_field_group("Монета", self._create_combo()))
        
        # Плечо
        layout.addWidget(self._create_field_group("Плечо", self._create_leverage_spin()))
        
        # Размер позиции (в USDT)
        layout.addWidget(self._create_field_group("Размер позиции (USDT)", self._create_position_spin()))
        
        # Расчёт (информационный блок)
        self.calc_label = QLabel("Маржа: $0 | Кол-во: 0")
        self.calc_label.setStyleSheet("""
            font-size: 12px; color: #00D9A5; 
            background: #1a2a25; 
            padding: 10px 12px; border-radius: 8px;
            border: 1px solid #00D9A5;
        """)
        self.calc_label.setWordWrap(True)
        layout.addWidget(self.calc_label)
        
        # SL и TP
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addWidget(self._create_field_group("Stop Loss", self._create_sl_spin()))
        row2.addWidget(self._create_field_group("Take Profit", self._create_tp_spin()))
        layout.addLayout(row2)
        
        # Buttons
        layout.addSpacing(8)
        btns = QHBoxLayout()
        btns.setSpacing(12)
        
        self.long_btn = QPushButton("ЛОНГ 📈")
        self.long_btn.setFixedHeight(48)
        self.long_btn.setCursor(Qt.PointingHandCursor)
        self.long_btn.setEnabled(False)
        self.long_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #00c9a7; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.long_btn.clicked.connect(lambda: self._submit("buy"))
        btns.addWidget(self.long_btn)
        
        self.short_btn = QPushButton("ШОРТ 📉")
        self.short_btn.setFixedHeight(48)
        self.short_btn.setCursor(Qt.PointingHandCursor)
        self.short_btn.setEnabled(False)
        self.short_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['danger']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #ff4444; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.short_btn.clicked.connect(lambda: self._submit("sell"))
        btns.addWidget(self.short_btn)
        
        layout.addLayout(btns)
        
    def _create_field_group(self, label_text: str, widget: QWidget) -> QWidget:
        """Создаёт группу: лейбл + поле ввода"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; color: #888; font-weight: 500; background: transparent;")
        vbox.addWidget(label)
        vbox.addWidget(widget)
        
        return container
        
    def _create_combo(self) -> QComboBox:
        self.symbol_combo = QComboBox()
        self.symbol_combo.setFixedHeight(50)
        self.symbol_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox::down-arrow { 
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #aaa;
            }
            QComboBox QAbstractItemView {
                background: #2a2a35;
                color: #ffffff;
                selection-background-color: #6C5CE7;
            }
        """)
        for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"]:
            self.symbol_combo.addItem(sym.replace("/USDT:USDT", ""), sym)
        return self.symbol_combo
        
    def _create_size_spin(self) -> QDoubleSpinBox:
        """Старый метод для совместимости"""
        return self._create_position_spin()
        
    def _create_position_spin(self) -> QDoubleSpinBox:
        """Размер позиции в USDT (как на Bybit)"""
        self.position_input = QDoubleSpinBox()
        self.position_input.setFixedHeight(50)
        self.position_input.setRange(10, 1000000)
        self.position_input.setValue(1000)
        self.position_input.setDecimals(0)
        self.position_input.setSingleStep(100)
        self.position_input.setPrefix("$")
        self.position_input.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        self.position_input.valueChanged.connect(self._update_calc)
        return self.position_input
        
    def _create_leverage_spin(self) -> QSpinBox:
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setFixedHeight(50)
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(10)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setStyleSheet("""
            QSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        self.leverage_spin.valueChanged.connect(self._update_calc)
        return self.leverage_spin
        
    def _create_sl_spin(self) -> QDoubleSpinBox:
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setFixedHeight(50)
        self.sl_spin.setRange(0.5, 50)
        self.sl_spin.setValue(2.0)
        self.sl_spin.setDecimals(1)
        self.sl_spin.setSuffix("%")
        self.sl_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.sl_spin
        
    def _create_tp_spin(self) -> QDoubleSpinBox:
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setFixedHeight(50)
        self.tp_spin.setRange(0.5, 100)
        self.tp_spin.setValue(4.0)
        self.tp_spin.setDecimals(1)
        self.tp_spin.setSuffix("%")
        self.tp_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px 14px;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.tp_spin
        
    def _submit(self, side: str):
        position_usdt = self.position_input.value()
        leverage = self.leverage_spin.value()
        # Передаём размер позиции в USDT (не маржу!)
        self.order_submitted.emit(
            self.symbol_combo.currentData(),
            side,
            position_usdt,  # размер позиции в USDT
            self.sl_spin.value(),
            self.tp_spin.value(),
            leverage
        )
        
    def _update_calc(self):
        """Обновляет расчёт маржи и количества монет"""
        if not hasattr(self, 'calc_label') or not hasattr(self, 'position_input'):
            return
            
        position_usdt = self.position_input.value()
        leverage = self.leverage_spin.value()
        
        # Маржа = позиция / плечо
        margin = position_usdt / leverage
        
        # Количество монет (если есть цена)
        if self.current_price > 0:
            qty = position_usdt / self.current_price
            coin = self.symbol_combo.currentText()
            self.calc_label.setText(
                f"Маржа: ${margin:,.0f} | Позиция: ${position_usdt:,.0f}\n"
                f"Кол-во: {qty:,.4f} {coin} @ ${self.current_price:,.2f}"
            )
        else:
            self.calc_label.setText(f"Маржа: ${margin:,.0f} | Позиция: ${position_usdt:,.0f}")
    
    def set_price(self, price: float):
        """Устанавливает текущую цену для расчёта"""
        self.current_price = price
        self._update_calc()
        
    def set_enabled(self, enabled: bool):
        self.long_btn.setEnabled(enabled)
        self.short_btn.setEnabled(enabled)


class AutoTradePanel(QFrame):
    """Панель автоторговли по сигналам"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame#AutoTradePanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("AutoTradePanel")
        self.setMinimumHeight(340)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("🤖 Автоторговля")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        
        self.status_lbl = QLabel("⚪ Выкл")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        header.addWidget(self.status_lbl)
        layout.addLayout(header)
        
        # Info
        info = QLabel("Конфлюенс: EMA + Smart Money + Trend\nHTF фильтр | Минимум 2/3 | SL: 2% | TP: 4%")
        info.setStyleSheet("""
            font-size: 12px; color: #888; 
            background: #1a1a22; 
            padding: 12px; border-radius: 8px;
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Settings row
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.addWidget(self._create_field_group("Таймфрейм", self._create_tf_combo()))
        row1.addWidget(self._create_field_group("Плечо", self._create_leverage_spin()))
        row1.addWidget(self._create_field_group("% баланса", self._create_risk_spin()))
        layout.addLayout(row1)
        
        # Coins
        coins_lbl = QLabel("Монеты:")
        coins_lbl.setStyleSheet("font-size: 13px; color: #888; font-weight: 500; background: transparent;")
        layout.addWidget(coins_lbl)
        
        coins_row = QHBoxLayout()
        coins_row.setSpacing(12)
        self.coin_checks: Dict[str, QCheckBox] = {}
        
        for coin in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
            cb = QCheckBox(coin)
            cb.setChecked(coin in ["BTC", "ETH"])
            cb.setStyleSheet("""
                QCheckBox {
                    color: white; 
                    font-size: 13px;
                    spacing: 6px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 2px solid #444;
                    background: #1a1a22;
                }
                QCheckBox::indicator:checked {
                    background: #6C5CE7;
                    border-color: #6C5CE7;
                }
            """)
            self.coin_checks[coin] = cb
            coins_row.addWidget(cb)
        coins_row.addStretch()
        layout.addLayout(coins_row)
        
        # Button
        layout.addSpacing(4)
        self.toggle_btn = QPushButton("▶ Запустить автоторговлю")
        self.toggle_btn.setFixedHeight(48)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        layout.addWidget(self.toggle_btn)
        
    def _create_field_group(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 12px; color: #888; font-weight: 500; background: transparent;")
        vbox.addWidget(label)
        vbox.addWidget(widget)
        
        return container
        
    def _create_tf_combo(self) -> QComboBox:
        self.tf_combo = QComboBox()
        self.tf_combo.setFixedHeight(46)
        self.tf_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow { 
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
            }
            QComboBox QAbstractItemView {
                background: #2a2a35;
                color: #ffffff;
                selection-background-color: #6C5CE7;
            }
        """)
        for tf, name in [("1h", "1 час"), ("4h", "4 часа"), ("1d", "1 день")]:
            self.tf_combo.addItem(name, tf)
        return self.tf_combo
        
    def _create_leverage_spin(self) -> QSpinBox:
        self.auto_leverage = QSpinBox()
        self.auto_leverage.setFixedHeight(46)
        self.auto_leverage.setRange(1, 20)
        self.auto_leverage.setValue(10)
        self.auto_leverage.setSuffix("x")
        self.auto_leverage.setStyleSheet("""
            QSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.auto_leverage
        
    def _create_risk_spin(self) -> QDoubleSpinBox:
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setFixedHeight(46)
        self.risk_spin.setRange(1, 20)
        self.risk_spin.setValue(7.0)
        self.risk_spin.setDecimals(0)
        self.risk_spin.setSuffix("%")
        self.risk_spin.setStyleSheet("""
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                background: #3a3a45;
                border: none;
            }
        """)
        return self.risk_spin
        
    def set_enabled(self, enabled: bool):
        self.toggle_btn.setEnabled(enabled)
        
    def set_running(self, running: bool):
        if running:
            self.status_lbl.setText("🟢 Активна")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #00D9A5; background: transparent;")
            self.toggle_btn.setText("⏹ Остановить")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['danger']};
                    border: none;
                    border-radius: 10px;
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: #ff4444; }}
            """)
        else:
            self.status_lbl.setText("⚪ Выкл")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
            self.toggle_btn.setText("▶ Запустить автоторговлю")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent']};
                    border: none;
                    border-radius: 10px;
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            """)


class TradeHistoryTable(QFrame):
    """Таблица истории сделок"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        title = QLabel("📜 История сделок")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Время", "Монета", "Тип", "Размер", "Цена", "PnL"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: transparent;
                border: none;
                color: {COLORS['text']};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background: {COLORS['bg_hover']};
                color: {COLORS['text_muted']};
                border: none;
                padding: 6px;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)
        
    def add_trade(self, time: str, symbol: str, side: str, size: float, price: float, pnl: float):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(time))
        self.table.setItem(row, 1, QTableWidgetItem(symbol))
        
        side_item = QTableWidgetItem("ЛОНГ" if side == "buy" else "ШОРТ")
        side_item.setForeground(QColor(COLORS['success'] if side == "buy" else COLORS['danger']))
        self.table.setItem(row, 2, side_item)
        
        self.table.setItem(row, 3, QTableWidgetItem(f"{size:.4f}"))
        self.table.setItem(row, 4, QTableWidgetItem(f"${price:,.2f}"))
        
        pnl_item = QTableWidgetItem(f"{'+'if pnl>=0 else ''}${pnl:.2f}")
        pnl_item.setForeground(QColor(COLORS['success'] if pnl >= 0 else COLORS['danger']))
        self.table.setItem(row, 5, pnl_item)


class BybitTerminal(QMainWindow):
    """Полноценный терминал Bybit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bybit Terminal Pro")
        self.setMinimumSize(1100, 700)
        
        self.exchange = None
        self.positions: List[dict] = []
        self.settings = QSettings("LocalSignals", "Terminal")
        self.auto_trading = False
        self.position_rows: List[PositionRow] = []
        
        self._setup_ui()
        
        # Начальный лог
        QTimer.singleShot(100, lambda: self._log("Подключись к Bybit Testnet для начала торговли"))
        
        # Адаптивный размер - на весь экран
        screen = QApplication.primaryScreen().geometry()
        w = max(1100, int(screen.width() * 0.85))
        h = max(700, int(screen.height() * 0.8))
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        
        # Показываем инструкцию при первом запуске
        if not self.settings.value("instruction_shown", False):
            QTimer.singleShot(500, self._show_instruction)
        
    def _show_instruction(self):
        dialog = InstructionDialog(self)
        if dialog.exec():
            if dialog.dont_show.isChecked():
                self.settings.setValue("instruction_shown", True)
                
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        # Фон
        self.bg = TerminalBackground(central)
        
        # Контент
        content = QWidget(central)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content
        main = QHBoxLayout()
        main.setSpacing(16)
        
        # Left column - Trading
        left = QVBoxLayout()
        left.setSpacing(12)
        
        # API Connection
        api_card = self._create_api_card()
        left.addWidget(api_card)
        
        # Order panel
        self.order_panel = OrderPanel()
        self.order_panel.order_submitted.connect(self._submit_order)
        left.addWidget(self.order_panel)
        
        # Auto trade panel
        self.auto_panel = AutoTradePanel()
        self.auto_panel.toggle_btn.clicked.connect(self._toggle_auto_trade)
        left.addWidget(self.auto_panel)
        
        # Загружаем сохранённые настройки автоторговли
        self._load_auto_settings()
        
        left.addStretch()
        
        # Wrap left column in scroll area
        left_content = QWidget()
        left_content.setLayout(left)
        left_content.setStyleSheet("background: transparent;")
        
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_content)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(360)
        left_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main.addWidget(left_scroll)
        
        # Right column - Info
        right = QVBoxLayout()
        right.setSpacing(12)
        
        # Balance
        self.balance_widget = BalanceWidget()
        right.addWidget(self.balance_widget)
        
        # Positions
        pos_header = QHBoxLayout()
        pos_title = QLabel("📈 Открытые позиции")
        pos_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        pos_header.addWidget(pos_title)
        pos_header.addStretch()
        
        self.pos_count = QLabel("0")
        self.pos_count.setStyleSheet(f"""
            font-size: 11px; color: white;
            background: {COLORS['accent']}; padding: 3px 10px; border-radius: 6px;
        """)
        pos_header.addWidget(self.pos_count)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_data)
        pos_header.addWidget(self.refresh_btn)
        
        right.addLayout(pos_header)
        
        # Positions scroll
        self.positions_scroll = QScrollArea()
        self.positions_scroll.setWidgetResizable(True)
        self.positions_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {COLORS['bg_card']}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['accent']}; border-radius: 3px;
            }}
        """)
        self.positions_scroll.setMinimumHeight(200)
        
        self.positions_widget = QWidget()
        self.positions_layout = QVBoxLayout(self.positions_widget)
        self.positions_layout.setSpacing(8)
        self.positions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.no_pos_lbl = QLabel("Нет открытых позиций")
        self.no_pos_lbl.setAlignment(Qt.AlignCenter)
        self.no_pos_lbl.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; padding: 30px;")
        self.positions_layout.addWidget(self.no_pos_lbl)
        self.positions_layout.addStretch()
        
        self.positions_scroll.setWidget(self.positions_widget)
        right.addWidget(self.positions_scroll)
        
        # Trade history
        self.history_table = TradeHistoryTable()
        right.addWidget(self.history_table, 1)
        
        main.addLayout(right, 1)
        layout.addLayout(main, 1)
        
        # Log panel - полноценная панель логов
        log_frame = QFrame()
        log_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        log_frame.setFixedHeight(120)
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 8, 12, 8)
        log_layout.setSpacing(4)
        
        log_header = QHBoxLayout()
        log_title = QLabel("📋 Логи торговли")
        log_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        log_header.addWidget(log_title)
        log_header.addStretch()
        
        # Profit badge
        self.profit_badge = QLabel("")
        self.profit_badge.setStyleSheet(f"""
            font-size: 11px; font-weight: 700; color: {COLORS['success']};
            background: rgba(0, 217, 165, 0.15); padding: 4px 10px; border-radius: 6px;
        """)
        self.profit_badge.hide()
        log_header.addWidget(self.profit_badge)
        
        log_layout.addLayout(log_header)
        
        # Log scroll area
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 2px; }}
        """)
        
        self.log_widget = QWidget()
        self.log_layout = QVBoxLayout(self.log_widget)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(2)
        self.log_layout.addStretch()
        
        self.log_scroll.setWidget(self.log_widget)
        log_layout.addWidget(self.log_scroll)
        
        layout.addWidget(log_frame)
        
        # Для совместимости
        self.log_lbl = None
        self.log_messages = []
        
        # Root layout
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content)
        
    def _create_header(self):
        header = QFrame()
        header.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Logo
        self.logo_lbl = QLabel()
        self.logo_lbl.setFixedSize(28, 28)
        LogoLoader.load(self._set_logo)
        layout.addWidget(self.logo_lbl)
        
        title = QLabel("Bybit Terminal Pro")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text']}; margin-left: 8px;")
        layout.addWidget(title)
        
        demo_badge = QLabel("TESTNET")
        demo_badge.setStyleSheet(f"""
            font-size: 10px; font-weight: 700; color: {COLORS['warning']};
            background: rgba(253, 203, 110, 0.2);
            padding: 4px 10px; border-radius: 6px;
            margin-left: 12px;
        """)
        layout.addWidget(demo_badge)
        
        layout.addStretch()
        
        # Status
        self.status_lbl = QLabel("⚪ Не подключено")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['text_muted']};
            background: {COLORS['bg_hover']}; padding: 6px 14px; border-radius: 8px;
        """)
        layout.addWidget(self.status_lbl)
        
        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(28, 28)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 14px;
                color: {COLORS['text_muted']};
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}
        """)
        help_btn.clicked.connect(self._show_instruction)
        layout.addWidget(help_btn)
        
        return header
        
    def _set_logo(self, pixmap):
        if pixmap:
            self.logo_lbl.setPixmap(pixmap)
        else:
            self.logo_lbl.setText("🟠")
            self.logo_lbl.setStyleSheet("font-size: 20px;")
            
    def _create_api_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        title = QLabel("🔑 Подключение")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(title)
        
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("API Key")
        self.api_key.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 11px;
                color: {COLORS['text']};
            }}
        """)
        # Загружаем сохранённый ключ
        saved_key = self.settings.value("api_key", "")
        if saved_key:
            self.api_key.setText(saved_key)
        layout.addWidget(self.api_key)
        
        self.api_secret = QLineEdit()
        self.api_secret.setPlaceholderText("API Secret")
        self.api_secret.setEchoMode(QLineEdit.Password)
        self.api_secret.setStyleSheet(self.api_key.styleSheet())
        # Загружаем сохранённый секрет
        saved_secret = self.settings.value("api_secret", "")
        if saved_secret:
            self.api_secret.setText(saved_secret)
        layout.addWidget(self.api_secret)
        
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(34)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
        """)
        self.connect_btn.clicked.connect(self._connect)
        layout.addWidget(self.connect_btn)
        
        return card
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bg'):
            self.bg.setGeometry(self.centralWidget().rect())
            
    def _log(self, msg: str, msg_type: str = "info"):
        """Добавляет сообщение в лог. msg_type: info, success, error, profit"""
        time_str = datetime.now().strftime('%H:%M:%S')
        
        # Определяем цвет
        if msg_type == "success" or "✅" in msg:
            color = COLORS['success']
        elif msg_type == "error" or "❌" in msg:
            color = COLORS['danger']
        elif msg_type == "profit":
            color = COLORS['warning']
        else:
            color = COLORS['text_muted']
        
        # Создаём лейбл
        log_entry = QLabel(f"[{time_str}] {msg}")
        log_entry.setStyleSheet(f"font-size: 11px; color: {color}; padding: 2px 0;")
        log_entry.setWordWrap(True)
        
        # Добавляем в начало (перед stretch)
        self.log_layout.insertWidget(self.log_layout.count() - 1, log_entry)
        
        # Ограничиваем количество логов
        if self.log_layout.count() > 51:  # 50 логов + stretch
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Скроллим вниз
        QTimer.singleShot(50, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()
        ))
        
    def _show_profit(self, pnl: float):
        """Показывает бейдж с профитом если он хороший"""
        if pnl >= 5:  # Если профит >= $5
            self.profit_badge.setText(f"🎉 +${pnl:.2f}")
            self.profit_badge.show()
            # Скрываем через 10 секунд
            QTimer.singleShot(10000, self.profit_badge.hide)
        
    def _connect(self):
        if ccxt is None:
            QMessageBox.critical(self, "Ошибка", "pip install ccxt")
            return
            
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Ошибка", "Введи API Key и Secret")
            return
        
        # Показываем что идёт подключение
        self.connect_btn.setText("⏳ Подключение...")
        self.connect_btn.setEnabled(False)
        self.status_lbl.setText("🔄 Подключение...")
        
        # Запускаем воркер
        self.connect_worker = ConnectWorker(api_key, api_secret)
        self.connect_worker.success.connect(self._on_connect_success)
        self.connect_worker.error.connect(self._on_connect_error)
        self.connect_worker.log.connect(self._log)
        self.connect_worker.start()
        
    def _on_connect_success(self, exchange):
        """Вызывается при успешном подключении"""
        self.exchange = exchange
        
        # Сохраняем ключи
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()
        self.settings.setValue("api_key", api_key)
        self.settings.setValue("api_secret", api_secret)
        
        self.status_lbl.setText("🟢 Подключено")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['success']};
            background: rgba(0, 217, 165, 0.15); padding: 6px 14px; border-radius: 8px;
        """)
        
        self.connect_btn.setText("✓ Подключено")
        self.connect_btn.setEnabled(False)
        
        self.order_panel.set_enabled(True)
        self.auto_panel.set_enabled(True)
        self.refresh_btn.setEnabled(True)
        
        self._log("✅ Успешно подключено к Bybit Testnet!")
        self._refresh_data()
        
        # Auto refresh каждые 5 сек
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(5000)
        
        # Автозапуск автоторговли если была включена
        was_auto_trading = self.settings.value("auto_trading", "false")
        if was_auto_trading == "true" or was_auto_trading == True:
            self._log("🔄 Восстанавливаю автоторговлю...")
            QTimer.singleShot(2000, self._start_auto_trade)  # Запускаем через 2 сек
            
    def _start_auto_trade(self):
        """Запускает автоторговлю (без toggle)"""
        if self.auto_trading:
            return  # Уже запущена
            
        self.auto_trading = True
        self.auto_panel.set_running(True)
        self._save_auto_settings()
        
        self._log("🤖 Автоторговля запущена - торгую на 5-10% от баланса")
        
        # Проверяем есть ли открытые позиции от бота
        bot_coins = self.settings.value("auto_coins", "").split(",")
        if bot_coins:
            for pos in self.positions:
                coin = pos.get('symbol', '').split('/')[0]
                if coin in bot_coins:
                    self._log(f"📍 Найдена позиция бота: {coin}")
        
        if not hasattr(self, 'auto_timer'):
            self.auto_timer = QTimer()
            self.auto_timer.timeout.connect(self._run_auto_worker)
        self.auto_timer.start(60000)
        QTimer.singleShot(1000, self._run_auto_worker)
        
    def _on_connect_error(self, error: str):
        """Вызывается при ошибке подключения"""
        self.connect_btn.setText("🔌 Подключить")
        self.connect_btn.setEnabled(True)
        self.status_lbl.setText("⚪ Не подключено")
        self._log(f"❌ Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка подключения", error)
            
    def _refresh_data(self):
        if not self.exchange:
            return
        
        # Если уже идёт обновление - пропускаем
        if hasattr(self, 'refresh_worker') and self.refresh_worker.isRunning():
            return
            
        symbol = self.order_panel.symbol_combo.currentData()
        self.refresh_worker = RefreshWorker(self.exchange, symbol)
        self.refresh_worker.data_ready.connect(self._on_data_ready)
        self.refresh_worker.price_ready.connect(self._on_price_ready)
        self.refresh_worker.error.connect(lambda e: self._log(f"Ошибка обновления: {e}"))
        self.refresh_worker.start()
        
    def _on_data_ready(self, available: float, total: float, pnl: float, positions: list):
        """Вызывается когда данные готовы"""
        self.balance_widget.update_balance(available, total, pnl)
        self._update_positions(positions)
        
    def _on_price_ready(self, price: float):
        """Вызывается когда цена готова"""
        self.order_panel.set_price(price)
            
    def _update_positions(self, positions: list):
        # Clear old
        for row in self.position_rows:
            row.deleteLater()
        self.position_rows.clear()
        
        self.positions = positions
        self.pos_count.setText(str(len(positions)))
        
        if not positions:
            self.no_pos_lbl.show()
        else:
            self.no_pos_lbl.hide()
            
            for pos in positions:
                row = PositionRow()
                row.update_data(
                    pos.get('symbol') or '',
                    (pos.get('side') or '').lower(),
                    float(pos.get('contracts') or 0),
                    float(pos.get('entryPrice') or 0),
                    float(pos.get('markPrice') or 0),
                    float(pos.get('unrealizedPnl') or 0),
                    float(pos.get('percentage') or 0),
                    int(pos.get('leverage') or 1)
                )
                row.close_clicked.connect(self._close_position)
                self.positions_layout.insertWidget(self.positions_layout.count() - 1, row)
                self.position_rows.append(row)
                
    def _set_leverage_safe(self, leverage: int, symbol: str):
        """Установить плечо, игнорируя ошибку если уже установлено"""
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            # Игнорируем ошибку "leverage not modified" - плечо уже установлено
            if "110043" not in str(e) and "not modified" not in str(e).lower():
                raise e
                
    def _submit_order(self, symbol: str, side: str, position_usdt: float, sl_pct: float, tp_pct: float, leverage: int):
        """
        Создаёт ордер.
        position_usdt - размер позиции в USDT (НЕ маржа!)
        Маржа = position_usdt / leverage
        """
        if not self.exchange:
            return
            
        try:
            # Set leverage
            self._set_leverage_safe(leverage, symbol)
            
            # Get current price
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # Расчёт как на Bybit:
            # position_usdt = размер позиции в долларах
            # margin = position_usdt / leverage (сколько спишется с баланса)
            # qty = position_usdt / price (сколько монет купим)
            
            margin = position_usdt / leverage
            qty = position_usdt / price
            
            # Округляем количество
            coin = symbol.split('/')[0]
            if coin == "BTC":
                qty = round(qty, 3)
            elif coin == "ETH":
                qty = round(qty, 2)
            elif coin in ["SOL"]:
                qty = round(qty, 1)
            else:
                qty = round(qty, 0)  # XRP, DOGE - целые числа
            
            self._log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log(f"📊 {'ЛОНГ 📈' if side == 'buy' else 'ШОРТ 📉'} {coin}")
            self._log(f"   Позиция: ${position_usdt:,.0f}")
            self._log(f"   Маржа: ${margin:,.0f} (плечо {leverage}x)")
            self._log(f"   Кол-во: {qty} {coin} @ ${price:,.2f}")
            
            # Calculate SL/TP prices
            if side == "buy":
                sl_price = price * (1 - sl_pct / 100)
                tp_price = price * (1 + tp_pct / 100)
                order = self.exchange.create_market_buy_order(symbol, qty)
            else:
                sl_price = price * (1 + sl_pct / 100)
                tp_price = price * (1 - tp_pct / 100)
                order = self.exchange.create_market_sell_order(symbol, qty)
            
            self._log(f"   SL: ${sl_price:,.2f} ({sl_pct}%) | TP: ${tp_price:,.2f} ({tp_pct}%)")
            self._log(f"✅ Ордер исполнен!")
            
            # Add to history
            self.history_table.add_trade(
                datetime.now().strftime("%H:%M:%S"),
                coin,
                side,
                qty,
                price,
                0
            )
            
            self._refresh_data()
            
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")
            QMessageBox.critical(self, "Ошибка ордера", str(e))
            
    def _close_position(self, symbol: str):
        if not self.exchange:
            return
            
        for pos in self.positions:
            if pos.get('symbol') == symbol:
                side = (pos.get('side') or '').lower()
                size = float(pos.get('contracts') or 0)
                pnl = float(pos.get('unrealizedPnl') or 0)
                
                try:
                    if side == "long":
                        self.exchange.create_market_sell_order(symbol, size, {"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(symbol, size, {"reduceOnly": True})
                    
                    coin = symbol.split('/')[0]
                    pnl_str = f"{'+'if pnl>=0 else ''}${pnl:.2f}"
                    self._log(f"✅ Закрыто {coin} | PnL: {pnl_str}", "success" if pnl >= 0 else "error")
                    
                    # Показываем бейдж если хороший профит
                    if pnl >= 5:
                        self._show_profit(pnl)
                    
                    # Add to history
                    ticker = self.exchange.fetch_ticker(symbol)
                    self.history_table.add_trade(
                        datetime.now().strftime("%H:%M:%S"),
                        coin,
                        "sell" if side == "long" else "buy",
                        size,
                        ticker['last'],
                        pnl
                    )
                    
                    self._refresh_data()
                    
                except Exception as e:
                    self._log(f"❌ Ошибка: {e}", "error")
                break
                
    def _toggle_auto_trade(self):
        self.auto_trading = not self.auto_trading
        self.auto_panel.set_running(self.auto_trading)
        
        # Сохраняем настройки
        self._save_auto_settings()
        
        if self.auto_trading:
            self._log("🤖 Автоторговля запущена - торгую на 5-10% от баланса")
            # Запускаем таймер проверки сигналов каждые 60 сек
            if not hasattr(self, 'auto_timer'):
                self.auto_timer = QTimer()
                self.auto_timer.timeout.connect(self._run_auto_worker)
            self.auto_timer.start(60000)  # Каждую минуту
            # Сразу проверяем
            QTimer.singleShot(1000, self._run_auto_worker)
        else:
            self._log("🤖 Автоторговля остановлена")
            if hasattr(self, 'auto_timer'):
                self.auto_timer.stop()
            if hasattr(self, 'auto_worker') and self.auto_worker.isRunning():
                self.auto_worker.stop()
    
    def _save_auto_settings(self):
        """Сохраняет настройки автоторговли"""
        self.settings.setValue("auto_trading", "true" if self.auto_trading else "false")
        self.settings.setValue("auto_leverage", self.auto_panel.auto_leverage.value())
        self.settings.setValue("auto_risk", self.auto_panel.risk_spin.value())
        self.settings.setValue("auto_tf", self.auto_panel.tf_combo.currentData())
        
        # Сохраняем выбранные монеты
        selected = [coin for coin, cb in self.auto_panel.coin_checks.items() if cb.isChecked()]
        self.settings.setValue("auto_coins", ",".join(selected))
        
    def _load_auto_settings(self):
        """Загружает настройки автоторговли"""
        # Плечо
        leverage = self.settings.value("auto_leverage", 10, type=int)
        self.auto_panel.auto_leverage.setValue(leverage)
        
        # Риск
        risk = self.settings.value("auto_risk", 7.0, type=float)
        self.auto_panel.risk_spin.setValue(risk)
        
        # Таймфрейм
        tf = self.settings.value("auto_tf", "1h")
        idx = self.auto_panel.tf_combo.findData(tf)
        if idx >= 0:
            self.auto_panel.tf_combo.setCurrentIndex(idx)
        
        # Монеты
        coins_str = self.settings.value("auto_coins", "BTC,ETH")
        selected_coins = coins_str.split(",") if coins_str else []
        for coin, cb in self.auto_panel.coin_checks.items():
            cb.setChecked(coin in selected_coins)
                
    def _run_auto_worker(self):
        """Запускает воркер автоторговли в отдельном потоке"""
        if not self.auto_trading or not self.exchange:
            return
            
        # Если предыдущий воркер ещё работает - пропускаем
        if hasattr(self, 'auto_worker') and self.auto_worker.isRunning():
            return
        
        # Собираем настройки из UI в главном потоке
        settings = {
            'leverage': self.auto_panel.auto_leverage.value(),
            'risk_pct': self.auto_panel.risk_spin.value(),
            'tf': self.auto_panel.tf_combo.currentData() or "1m",
            'selected_coins': [coin for coin, cb in self.auto_panel.coin_checks.items() if cb.isChecked()]
        }
            
        self.auto_worker = AutoTradeWorker(
            self.exchange,
            settings,
            self._get_confluence_signal,
            self._get_htf_trend
        )
        self.auto_worker.log_signal.connect(self._log)
        self.auto_worker.profit_signal.connect(self._show_profit)
        self.auto_worker.refresh_signal.connect(self._refresh_data)
        self.auto_worker.open_position_signal.connect(self._auto_open_position)
        self.auto_worker.start()
                
    def _get_htf_trend(self, coin: str, tf: str) -> str:
        """Получает тренд на старшем таймфрейме для фильтрации"""
        # Маппинг на старший ТФ
        htf_map = {
            "1m": "15m",
            "5m": "1h", 
            "15m": "4h",
            "1h": "4h",
            "4h": "1d",
            "1d": "1w",
        }
        htf = htf_map.get(tf, "4h")
        
        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            
            symbol = f"{coin}USDT.P"
            res = ema_get_signal(symbol, htf, "BYBIT_PERP")
            
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                return str(res[0])
            return "neutral"
        except:
            return "neutral"
            
    def _get_confluence_signal(self, coin: str) -> tuple:
        """
        Получает торговый сигнал по конфлюенс стратегии (3 индикатора).
        Возвращает: (signal, strength, details)
        - signal: "buy", "sell", "none"
        - strength: 0-3 (сколько индикаторов согласны)
        - details: строка с деталями
        """
        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            from indicators.algoalpha_smart_money_breakout import get_signal as sm_get_signal
            from indicators.algoalpha_trend_targets import get_signal as tt_get_signal
        except ImportError:
            return "none", 0, "Индикаторы не найдены"
            
        symbol = f"{coin}USDT.P"
        tf = self.auto_panel.tf_combo.currentData() or "1m"
        source = "BYBIT_PERP"
        
        results = {}
        
        # EMA Market Structure
        try:
            res = ema_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["EMA"] = str(res[0])
            else:
                results["EMA"] = "neutral"
        except:
            results["EMA"] = "neutral"
            
        # Smart Money Breakout
        try:
            res = sm_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["SM"] = str(res[0])
            else:
                results["SM"] = "neutral"
        except:
            results["SM"] = "neutral"
            
        # Trend Targets
        try:
            res = tt_get_signal(symbol, tf, source)
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                results["Trend"] = str(res[0])
            else:
                results["Trend"] = "neutral"
        except:
            results["Trend"] = "neutral"
            
        # Считаем конфлюенс
        bulls = sum(1 for v in results.values() if v == "bull")
        bears = sum(1 for v in results.values() if v == "bear")
        
        # Формируем детали
        emoji_map = {"bull": "🟢", "bear": "🔴", "neutral": "⚪"}
        details = " | ".join([f"{emoji_map.get(v, '⚪')}{k}" for k, v in results.items()])
        
        if bulls >= 2 and bulls > bears:
            return "buy", bulls, details
        elif bears >= 2 and bears > bulls:
            return "sell", bears, details
        else:
            return "none", 0, details
            
    def _calc_ema(self, data: list, period: int) -> list:
        """Рассчитывает EMA"""
        ema = []
        multiplier = 2 / (period + 1)
        
        # Первое значение = SMA
        sma = sum(data[:period]) / period
        ema.append(sma)
        
        for price in data[period:]:
            ema_val = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)
            
        return ema
        
    def _auto_open_position(self, symbol: str, side: str, size: float, sl_pct: float, tp_pct: float, leverage: int):
        """Открывает позицию автоматически"""
        try:
            # Устанавливаем плечо
            self._set_leverage_safe(leverage, symbol)
            
            # Получаем цену
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # Открываем ордер
            if side == "buy":
                order = self.exchange.create_market_buy_order(symbol, size)
            else:
                order = self.exchange.create_market_sell_order(symbol, size)
                
            coin = symbol.split('/')[0]
            self._log(f"✅ АВТО {'ЛОНГ' if side == 'buy' else 'ШОРТ'} {size} {coin} @ ${price:,.2f}")
            
            # Добавляем в историю
            self.history_table.add_trade(
                datetime.now().strftime("%H:%M:%S"),
                coin,
                side,
                size,
                price,
                0
            )
            
            self._refresh_data()
            
        except Exception as e:
            self._log(f"❌ Ошибка авто-ордера: {e}")
