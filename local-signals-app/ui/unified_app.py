"""
Local Signals Pro - Unified App
Единое окно: Сигналы слева, Терминал справа
Ничего не закрывается, всё в одном месте
"""
from __future__ import annotations

import sys
import math
import random
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QSettings, QUrl, Signal, QSize
)
from PySide6.QtGui import (
    QColor, QFont, QPainter, QLinearGradient, 
    QRadialGradient, QPixmap, QIcon
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit,
    QComboBox, QCheckBox, QPlainTextEdit, QMessageBox, QGridLayout,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSplitter,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core.worker import Worker
from ui.styles import (
    COLORS, set_theme, get_current_theme, get_label_style,
    AnimatedCard, ModernInput, ModernCombo, SmallButton, BigButton
)

try:
    import ccxt
except ImportError:
    ccxt = None


# ============ CONSTANTS ============

MONITOR_SYMBOLS = [
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "XRPUSDT.P", "DOGEUSDT.P",
    "ADAUSDT.P", "AVAXUSDT.P", "LINKUSDT.P", "SUIUSDT.P", "WIFUSDT.P",
]

COIN_ICONS = {
    "BTC": "https://s2.coinmarketcap.com/static/img/coins/64x64/1.png",
    "ETH": "https://s2.coinmarketcap.com/static/img/coins/64x64/1027.png",
    "SOL": "https://s2.coinmarketcap.com/static/img/coins/64x64/5426.png",
    "XRP": "https://s2.coinmarketcap.com/static/img/coins/64x64/52.png",
    "DOGE": "https://s2.coinmarketcap.com/static/img/coins/64x64/74.png",
    "ADA": "https://s2.coinmarketcap.com/static/img/coins/64x64/2010.png",
    "AVAX": "https://s2.coinmarketcap.com/static/img/coins/64x64/5805.png",
    "LINK": "https://s2.coinmarketcap.com/static/img/coins/64x64/1975.png",
    "SUI": "https://s2.coinmarketcap.com/static/img/coins/64x64/20947.png",
    "WIF": "https://s2.coinmarketcap.com/static/img/coins/64x64/28752.png",
}

BYBIT_LOGO_URL = "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png"
THREAD_ID_DEV = 5
DEFAULT_CHAT_ID = "-1003065825691"
LABEL_STYLE = get_label_style()

_icon_cache: Dict[str, QPixmap] = {}


# ============ ICON LOADERS ============

class CoinIconLoader:
    _instance = None
    _manager = None
    _pending: Dict[str, List] = {}
    _loading: set = set()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if CoinIconLoader._manager is None:
            CoinIconLoader._manager = QNetworkAccessManager()
            CoinIconLoader._pending = {}
            CoinIconLoader._loading = set()
        
    def load(self, coin: str, callback, size: int = 28):
        key = f"{coin}_{size}"
        if key in _icon_cache:
            callback(_icon_cache[key])
            return
        if key not in CoinIconLoader._pending:
            CoinIconLoader._pending[key] = []
        CoinIconLoader._pending[key].append(callback)
        if key in CoinIconLoader._loading:
            return
        url = COIN_ICONS.get(coin)
        if not url:
            for cb in CoinIconLoader._pending.pop(key, []):
                cb(None)
            return
        CoinIconLoader._loading.add(key)
        request = QNetworkRequest(QUrl(url))
        reply = CoinIconLoader._manager.get(request)
        reply.finished.connect(lambda: self._on_loaded(reply, coin, size))
        
    def _on_loaded(self, reply, coin: str, size: int):
        key = f"{coin}_{size}"
        CoinIconLoader._loading.discard(key)
        callbacks = CoinIconLoader._pending.pop(key, [])
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data.data())
            if not pixmap.isNull():
                pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                _icon_cache[key] = pixmap
                for cb in callbacks:
                    cb(pixmap)
                reply.deleteLater()
                return
        for cb in callbacks:
            cb(None)
        reply.deleteLater()


# ============ BACKGROUND ============

class UnifiedBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time = 0
        self.orbs = []
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        orb_colors = [
            (108, 92, 231, 60), (162, 155, 254, 50), (0, 206, 201, 55),
            (253, 121, 168, 45), (253, 203, 110, 40), (0, 217, 165, 50),
        ]
        for i in range(6):
            color = random.choice(orb_colors)
            self.orbs.append({
                'x': random.uniform(0.1, 0.9), 'y': random.uniform(0.1, 0.9),
                'radius': random.uniform(200, 400), 'color': color,
                'speed_x': random.uniform(-0.0003, 0.0003),
                'speed_y': random.uniform(-0.0003, 0.0003),
                'phase': random.uniform(0, 6.28),
            })
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)
        
    def _animate(self):
        self.time += 0.02
        for orb in self.orbs:
            orb['x'] += orb['speed_x']
            orb['y'] += orb['speed_y']
            if orb['x'] < 0.05 or orb['x'] > 0.95: orb['speed_x'] *= -1
            if orb['y'] < 0.05 or orb['y'] > 0.95: orb['speed_y'] *= -1
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        bg = QLinearGradient(0, 0, w, h)
        if get_current_theme() == "light":
            bg.setColorAt(0, QColor(245, 245, 247))
            bg.setColorAt(1, QColor(235, 235, 240))
        else:
            bg.setColorAt(0, QColor(13, 13, 15))
            bg.setColorAt(1, QColor(16, 16, 20))
        painter.fillRect(self.rect(), bg)
        
        alpha_mult = 0.4 if get_current_theme() == "light" else 1.0
        for orb in self.orbs:
            cx, cy = int(orb['x'] * w), int(orb['y'] * h)
            pulse = 1 + 0.2 * math.sin(self.time * 2 + orb['phase'])
            radius = int(orb['radius'] * pulse)
            gradient = QRadialGradient(cx, cy, radius)
            r, g, b, a = orb['color']
            a = int(a * alpha_mult)
            gradient.setColorAt(0, QColor(r, g, b, a))
            gradient.setColorAt(0.5, QColor(r, g, b, int(a * 0.3)))
            gradient.setColorAt(1, QColor(r, g, b, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)


# ============ SIGNAL COMPONENTS ============

class CoinCheckBox(QWidget):
    def __init__(self, symbol: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.coin = symbol.replace("USDT.P", "")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(24, 24)
        layout.addWidget(self.icon_lbl)
        
        self.cb = QCheckBox()
        self.cb.setChecked(True)
        self.cb.setStyleSheet(f"""
            QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px; background: {COLORS['bg_hover']}; }}
            QCheckBox::indicator:checked {{ background: {COLORS['accent']}; }}
        """)
        layout.addWidget(self.cb)
        
        loader = CoinIconLoader()
        loader.load(self.coin, self._set_icon, 24)
        self.setToolTip(self.coin)
        self.setCursor(Qt.PointingHandCursor)
        
    def _set_icon(self, pixmap):
        if pixmap:
            self.icon_lbl.setPixmap(pixmap)
        else:
            self.icon_lbl.setText(self.coin[:2])
            self.icon_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text']};")
            
    def isChecked(self): return self.cb.isChecked()
    def setChecked(self, checked): self.cb.setChecked(checked)


class IndicatorBadge(QFrame):
    def __init__(self, indicator_key: str, parent=None):
        super().__init__(parent)
        self.indicator_key = indicator_key
        self.status = "na"
        self.names = {"ema_ms": "EMA", "smart_money": "SM", "trend_targets": "Тренд"}
        self.setFixedHeight(22)
        self.setMinimumWidth(50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(3)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"font-size: 7px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.dot)
        
        self.name_lbl = QLabel(self.names.get(indicator_key, indicator_key))
        self.name_lbl.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.name_lbl)
        self._update_style()
        
    def set_status(self, status: str):
        self.status = status
        self._update_style()
        
    def _update_style(self):
        colors = {"bull": COLORS['success'], "bear": COLORS['danger'], "neutral": COLORS['warning']}
        color = colors.get(self.status, COLORS['text_muted'])
        bg_alpha = "0.15" if self.status in colors else "0.05"
        self.dot.setStyleSheet(f"font-size: 7px; color: {color}; background: transparent;")
        self.name_lbl.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {color}; background: transparent;")
        self.setStyleSheet(f"QFrame {{ background: rgba({','.join(str(int(color.lstrip('#')[i:i+2], 16)) for i in (0, 2, 4))}, {bg_alpha}); border: none; border-radius: 11px; }}")


class SignalCard(QFrame):
    clicked = Signal(str)
    
    def __init__(self, symbol: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.status = "na"
        self.indicator_states = {}
        self._setup_ui()
        
    def _setup_ui(self):
        self.setFixedHeight(60)
        self.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)
        
        coin_name = self.symbol.replace("USDT.P", "")
        self.name_lbl = QLabel(coin_name)
        self.name_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLORS['text']}; background: transparent;")
        layout.addWidget(self.name_lbl)
        
        self.action_lbl = QLabel("")
        self.action_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.action_lbl)
        
        layout.addStretch()
        
        self.badges = {}
        for key in ["ema_ms", "smart_money", "trend_targets"]:
            badge = IndicatorBadge(key)
            self.badges[key] = badge
            layout.addWidget(badge)
            
        self.time_lbl = QLabel("")
        self.time_lbl.setStyleSheet(f"font-size: 9px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.time_lbl)
        
        self.chart_btn = QPushButton("📈")
        self.chart_btn.setFixedSize(30, 30)
        self.chart_btn.setCursor(Qt.PointingHandCursor)
        self.chart_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; border: none; border-radius: 8px; font-size: 14px; }} QPushButton:hover {{ background: {COLORS['accent_light']}; }}")
        self.chart_btn.clicked.connect(lambda: self.clicked.emit(self.symbol))
        layout.addWidget(self.chart_btn)
        
    def update_indicator(self, indicator: str, status: str, detail: str):
        self.indicator_states[indicator] = status
        self.time_lbl.setText(datetime.now().strftime("%H:%M:%S"))
        if indicator in self.badges:
            self.badges[indicator].set_status(status)
        self._update_composite_status()
        
    def _update_composite_status(self):
        bulls = sum(1 for s in self.indicator_states.values() if s == "bull")
        bears = sum(1 for s in self.indicator_states.values() if s == "bear")
        
        if bulls > bears and bulls > 0:
            self.status = "bull"
            self.action_lbl.setText("ЛОНГ")
            self.action_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['success']}; background: transparent;")
            border = "rgba(0, 217, 165, 0.4)"
        elif bears > bulls and bears > 0:
            self.status = "bear"
            self.action_lbl.setText("ШОРТ")
            self.action_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['danger']}; background: transparent;")
            border = "rgba(255, 107, 107, 0.4)"
        else:
            self.status = "neutral"
            self.action_lbl.setText("—")
            self.action_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
            border = COLORS['border']
        
        self.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {border}; border-radius: 12px; }}")


# ============ TERMINAL COMPONENTS ============

class BalanceWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}")
        self.setFixedHeight(70)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(20)
        
        for title, attr in [("Доступно", "avail_lbl"), ("Эквити", "equity_lbl"), ("PnL", "pnl_lbl")]:
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
            col.addWidget(t)
            lbl = QLabel("$0.00")
            lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
            setattr(self, attr, lbl)
            col.addWidget(lbl)
            layout.addLayout(col)
        layout.addStretch()
        
    def update_balance(self, available: float, equity: float, pnl: float):
        self.avail_lbl.setText(f"${available:,.2f}")
        self.equity_lbl.setText(f"${equity:,.2f}")
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        self.pnl_lbl.setText(f"{'+'if pnl>=0 else ''}${pnl:,.2f}")
        self.pnl_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {pnl_color};")


class PositionRow(QFrame):
    close_clicked = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = ""
        self.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 8px; }}")
        self.setFixedHeight(44)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)
        
        self.symbol_lbl = QLabel("—")
        self.symbol_lbl.setFixedWidth(50)
        self.symbol_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(self.symbol_lbl)
        
        self.side_lbl = QLabel("—")
        self.side_lbl.setFixedWidth(50)
        layout.addWidget(self.side_lbl)
        
        self.size_lbl = QLabel("—")
        self.size_lbl.setFixedWidth(70)
        self.size_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text']};")
        layout.addWidget(self.size_lbl)
        
        self.pnl_lbl = QLabel("—")
        self.pnl_lbl.setFixedWidth(90)
        layout.addWidget(self.pnl_lbl)
        
        layout.addStretch()
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['danger']}; border: none; border-radius: 6px; color: white; font-size: 12px; }} QPushButton:hover {{ background: #ff4444; }}")
        self.close_btn.clicked.connect(lambda: self.close_clicked.emit(self.symbol))
        layout.addWidget(self.close_btn)
        
    def update_data(self, symbol: str, side: str, size: float, entry: float, mark: float, pnl: float, pnl_pct: float, leverage: int):
        self.symbol = symbol
        self.symbol_lbl.setText(symbol.replace("/USDT:USDT", ""))
        
        side_color = COLORS['success'] if side == "long" else COLORS['danger']
        self.side_lbl.setText("ЛОНГ" if side == "long" else "ШОРТ")
        self.side_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {side_color};")
        
        self.size_lbl.setText(f"{size:.4f}")
        
        if entry > 0 and leverage > 0:
            margin = (size * entry) / leverage
            if margin > 0:
                pnl_pct = (pnl / margin) * 100
        
        pnl_color = COLORS['success'] if pnl >= 0 else COLORS['danger']
        self.pnl_lbl.setText(f"{'+'if pnl>=0 else ''}${pnl:.2f} ({pnl_pct:+.1f}%)")
        self.pnl_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {pnl_color};")



# ============ WORKERS ============

from PySide6.QtCore import QThread

class ConnectWorker(QThread):
    success = Signal(object)
    error = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        
    def run(self):
        try:
            exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'sandbox': True,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'},
            })
            exchange.fetch_balance()
            self.success.emit(exchange)
        except Exception as e:
            self.error.emit(str(e))


class RefreshWorker(QThread):
    data_ready = Signal(float, float, float, list)
    price_ready = Signal(float)
    
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
            if self.symbol:
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.price_ready.emit(ticker['last'])
                except: pass
        except: pass


class AutoTradeWorker(QThread):
    log_signal = Signal(str)
    profit_signal = Signal(float)
    refresh_signal = Signal()
    open_position_signal = Signal(str, str, float, float, float, int)
    
    def __init__(self, exchange, settings: dict, get_signal_func, get_htf_func):
        super().__init__()
        self.exchange = exchange
        self.settings = settings
        self.get_signal = get_signal_func
        self.get_htf = get_htf_func
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def run(self):
        if not self.exchange:
            return
        self.log_signal.emit("🔍 Проверяю сигналы...")
        
        leverage = self.settings['leverage']
        risk_pct = self.settings['risk_pct']
        tf = self.settings['tf']
        selected_coins = self.settings['selected_coins']
        
        try:
            balance = self.exchange.fetch_balance()
            available = float(balance.get('USDT', {}).get('free') or 0)
        except:
            return
        
        if available < 10:
            self.log_signal.emit("⚠️ Недостаточно средств")
            return
        
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]
        except:
            open_positions = []
        
        # Автозакрытие
        for pos in open_positions:
            if self._stop: return
            pos_symbol = pos.get('symbol', '')
            pos_side = (pos.get('side') or '').lower()
            pos_size = float(pos.get('contracts') or 0)
            pos_pnl = float(pos.get('unrealizedPnl') or 0)
            coin = pos_symbol.split('/')[0] if '/' in pos_symbol else pos_symbol.replace('USDT', '')
            
            if coin not in selected_coins:
                continue
            
            try:
                signal, strength, _ = self.get_signal(coin)
            except:
                continue
            
            should_close = False
            if pos_side == "long" and signal == "sell" and strength >= 2:
                should_close = True
            elif pos_side == "short" and signal == "buy" and strength >= 2:
                should_close = True
            
            if should_close:
                try:
                    if pos_side == "long":
                        self.exchange.create_market_sell_order(pos_symbol, pos_size, {"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(pos_symbol, pos_size, {"reduceOnly": True})
                    self.log_signal.emit(f"✅ Закрыто {coin} | PnL: {'+'if pos_pnl>=0 else ''}${pos_pnl:.2f}")
                    if pos_pnl >= 5:
                        self.profit_signal.emit(pos_pnl)
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка закрытия: {e}")
        
        # Открытие новых
        for coin in selected_coins:
            if self._stop: return
            symbol = f"{coin}/USDT:USDT"
            
            has_position = any(p.get('symbol') == symbol and float(p.get('contracts') or 0) > 0 for p in open_positions)
            if has_position:
                continue
            
            try:
                signal, strength, details = self.get_signal(coin)
            except:
                continue
            
            if signal in ["buy", "sell"] and strength >= 2:
                try:
                    htf_trend = self.get_htf(coin, tf)
                except:
                    htf_trend = "neutral"
                
                if signal == "buy" and htf_trend == "bear":
                    continue
                if signal == "sell" and htf_trend == "bull":
                    continue
                
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    position_usdt = available * (risk_pct / 100)
                    size = (position_usdt * leverage) / price
                    
                    if coin == "BTC": size = round(size, 3)
                    elif coin in ["ETH", "SOL"]: size = round(size, 2)
                    else: size = round(size, 1)
                    
                    if size >= 0.001:
                        self.open_position_signal.emit(symbol, signal, size, 2.0, 4.0, leverage)
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка: {e}")
        
        self.refresh_signal.emit()


# ============ SIGNALS PANEL ============

class SignalsPanel(QFrame):
    """Левая панель - Сигналы и настройки"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.worker: Optional[Worker] = None
        self.cards: Dict[str, SignalCard] = {}
        self.settings = QSettings("LocalSignals", "Pro")
        
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 8, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("📊 Сигналы")
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['text']};")
        header.addWidget(title)
        header.addStretch()
        
        self.status_lbl = QLabel("⚪ Ожидание")
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: {COLORS['bg_hover']}; padding: 4px 10px; border-radius: 6px;")
        header.addWidget(self.status_lbl)
        
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setFixedSize(32, 32)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['bg_hover']}; border: none; border-radius: 8px; font-size: 16px; }} QPushButton:hover {{ background: {COLORS['accent']}; }}")
        self.theme_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_btn)
        layout.addLayout(header)
        
        # Settings card
        settings_card = QFrame()
        settings_card.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}")
        s_layout = QVBoxLayout(settings_card)
        s_layout.setContentsMargins(12, 12, 12, 12)
        s_layout.setSpacing(8)
        
        # Exchange & TF
        row1 = QHBoxLayout()
        self.exchange = ModernCombo()
        self.exchange.addItem("Bybit", "BYBIT_PERP")
        self.exchange.addItem("Binance", "BINANCE_SPOT")
        self.exchange.setFixedHeight(36)
        row1.addWidget(self.exchange)
        
        self.tf = ModernCombo()
        for k, v in [("1m", "1м"), ("5m", "5м"), ("15m", "15м"), ("1h", "1ч"), ("4h", "4ч"), ("1d", "1д")]:
            self.tf.addItem(v, k)
        self.tf.setCurrentIndex(3)
        self.tf.setFixedHeight(36)
        row1.addWidget(self.tf)
        s_layout.addLayout(row1)
        
        # Telegram
        self.tg_token = ModernInput("TG Token")
        self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_token.setFixedHeight(36)
        s_layout.addWidget(self.tg_token)
        
        self.tg_chat = ModernInput("TG Chat ID")
        self.tg_chat.setText(DEFAULT_CHAT_ID)
        self.tg_chat.setFixedHeight(36)
        s_layout.addWidget(self.tg_chat)
        
        layout.addWidget(settings_card)
        
        # Coins
        coins_grid = QGridLayout()
        coins_grid.setSpacing(2)
        self.coin_cbs: Dict[str, CoinCheckBox] = {}
        for i, sym in enumerate(MONITOR_SYMBOLS):
            cb = CoinCheckBox(sym)
            self.coin_cbs[sym] = cb
            coins_grid.addWidget(cb, i // 5, i % 5)
        layout.addLayout(coins_grid)
        
        # Buttons
        btns = QHBoxLayout()
        self.start_btn = QPushButton("▶ Старт")
        self.start_btn.setFixedHeight(38)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['success']}; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: 600; }} QPushButton:hover {{ background: #00c9a7; }}")
        self.start_btn.clicked.connect(self._start)
        btns.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ Стоп")
        self.stop_btn.setFixedHeight(38)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['danger']}; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: 600; }} QPushButton:hover {{ background: #ff4444; }} QPushButton:disabled {{ background: #2a2a35; color: #555; }}")
        self.stop_btn.clicked.connect(self._stop)
        btns.addWidget(self.stop_btn)
        layout.addLayout(btns)
        
        # Cards scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} QScrollBar:vertical {{ background: transparent; width: 4px; }} QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 2px; }}")
        
        scroll_w = QWidget()
        self.cards_layout = QVBoxLayout(scroll_w)
        self.cards_layout.setSpacing(6)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        
        for sym in MONITOR_SYMBOLS:
            card = SignalCard(sym)
            card.clicked.connect(self._open_chart)
            self.cards[sym] = card
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch()
        
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll, 1)
        
        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.setStyleSheet(f"QPlainTextEdit {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 6px; font-family: Consolas; font-size: 10px; color: {COLORS['text_muted']}; }}")
        layout.addWidget(self.log)
        
    def _log(self, msg: str):
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    def _toggle_theme(self):
        current = get_current_theme()
        new_theme = "light" if current == "dark" else "dark"
        set_theme(new_theme)
        self.theme_btn.setText("☀️" if new_theme == "dark" else "🌙")
        self.settings.setValue("theme", new_theme)
        
    def _open_chart(self, symbol: str):
        from PySide6.QtGui import QDesktopServices
        sym = symbol.replace("USDT.P", "USDT")
        QDesktopServices.openUrl(QUrl(f"https://www.tradingview.com/chart/?symbol=BYBIT:{sym}"))
        
    def _get_selected_coins(self) -> List[str]:
        return [s for s, cb in self.coin_cbs.items() if cb.isChecked()]
    
    def _get_current_source(self) -> str:
        return self.exchange.currentData()
    
    def _get_current_timeframe(self) -> str:
        return self.tf.currentData()
        
    def _start(self):
        if self.worker and self.worker.isRunning():
            return
        selected = self._get_selected_coins()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите монеты")
            return
            
        config = {
            "source": self.exchange.currentData(),
            "timeframe": self.tf.currentData(),
            "symbols": MONITOR_SYMBOLS,
            "alert_symbols": selected,
            "indicators": ["ema_ms", "smart_money", "trend_targets"],
            "tg_token": self.tg_token.text().strip(),
            "tg_chat": self.tg_chat.text().strip(),
            "tg_thread": THREAD_ID_DEV,
            "get_alert_symbols": self._get_selected_coins,
            "get_source": self._get_current_source,
            "get_timeframe": self._get_current_timeframe,
        }
        
        self._save_settings()
        self.worker = Worker(config)
        self.worker.log.connect(self._log)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_lbl.setText("🟢 Активен")
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['success']}; background: rgba(0, 217, 165, 0.15); padding: 4px 10px; border-radius: 6px;")
        self._log(f"Запуск: {len(selected)} монет")
        self.worker.start()
        
    def _stop(self):
        if self.worker:
            self.worker.stop()
            
    def _on_finished(self):
        self.worker = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("⚪ Остановлен")
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: {COLORS['bg_hover']}; padding: 4px 10px; border-radius: 6px;")
        
    def _on_status(self, symbol: str, indicator: str, status: str, detail: str, updated: str):
        for key in [f"{symbol}USDT.P", f"{symbol}.P", symbol]:
            if key in self.cards:
                self.cards[key].update_indicator(indicator, status, detail)
                return
                
    def _save_settings(self):
        self.settings.setValue("exchange", self.exchange.currentData())
        self.settings.setValue("tf", self.tf.currentData())
        self.settings.setValue("token", self.tg_token.text())
        self.settings.setValue("chat", self.tg_chat.text())
        
    def _load_settings(self):
        ex = self.settings.value("exchange", "BYBIT_PERP")
        tf = self.settings.value("tf", "1h")
        token = self.settings.value("token", "")
        chat = self.settings.value("chat", DEFAULT_CHAT_ID)
        
        idx = self.exchange.findData(ex)
        if idx >= 0: self.exchange.setCurrentIndex(idx)
        idx = self.tf.findData(tf)
        if idx >= 0: self.tf.setCurrentIndex(idx)
        self.tg_token.setText(token)
        self.tg_chat.setText(chat)
        set_theme("dark")



# ============ TERMINAL PANEL ============

class TerminalPanel(QFrame):
    """Правая панель - Терминал Bybit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.exchange = None
        self.positions: List[dict] = []
        self.position_rows: List[PositionRow] = []
        self.auto_trading = False
        self.settings = QSettings("LocalSignals", "Terminal")
        
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("⚡ Bybit Terminal")
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['text']};")
        header.addWidget(title)
        
        demo = QLabel("TESTNET")
        demo.setStyleSheet(f"font-size: 9px; font-weight: 700; color: {COLORS['warning']}; background: rgba(253, 203, 110, 0.2); padding: 3px 8px; border-radius: 4px;")
        header.addWidget(demo)
        header.addStretch()
        
        self.conn_status = QLabel("⚪ Не подключено")
        self.conn_status.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: {COLORS['bg_hover']}; padding: 4px 10px; border-radius: 6px;")
        header.addWidget(self.conn_status)
        layout.addLayout(header)
        
        # API Card
        api_card = QFrame()
        api_card.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(12, 10, 12, 10)
        api_layout.setSpacing(6)
        
        api_row = QHBoxLayout()
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("API Key")
        self.api_key.setFixedHeight(34)
        self.api_key.setStyleSheet(f"QLineEdit {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 10px; color: {COLORS['text']}; font-size: 11px; }}")
        api_row.addWidget(self.api_key)
        
        self.api_secret = QLineEdit()
        self.api_secret.setPlaceholderText("API Secret")
        self.api_secret.setEchoMode(QLineEdit.Password)
        self.api_secret.setFixedHeight(34)
        self.api_secret.setStyleSheet(self.api_key.styleSheet())
        api_row.addWidget(self.api_secret)
        
        self.connect_btn = QPushButton("🔌 Подключить")
        self.connect_btn.setFixedSize(100, 34)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; border: none; border-radius: 6px; color: white; font-size: 11px; font-weight: 600; }} QPushButton:hover {{ background: {COLORS['accent_light']}; }}")
        self.connect_btn.clicked.connect(self._connect)
        api_row.addWidget(self.connect_btn)
        api_layout.addLayout(api_row)
        layout.addWidget(api_card)
        
        # Balance
        self.balance_widget = BalanceWidget()
        layout.addWidget(self.balance_widget)
        
        # Main content - Order + Positions
        content = QHBoxLayout()
        content.setSpacing(12)
        
        # Left - Order panel
        order_card = QFrame()
        order_card.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}")
        order_card.setFixedWidth(280)
        o_layout = QVBoxLayout(order_card)
        o_layout.setContentsMargins(12, 12, 12, 12)
        o_layout.setSpacing(8)
        
        o_title = QLabel("📊 Новый ордер")
        o_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        o_layout.addWidget(o_title)
        
        # Symbol
        self.symbol_combo = QComboBox()
        self.symbol_combo.setFixedHeight(36)
        for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"]:
            self.symbol_combo.addItem(sym.replace("/USDT:USDT", ""), sym)
        self.symbol_combo.setStyleSheet(f"QComboBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 10px; color: {COLORS['text']}; font-size: 12px; }} QComboBox::drop-down {{ border: none; width: 24px; }}")
        o_layout.addWidget(self.symbol_combo)
        
        # Position size
        row1 = QHBoxLayout()
        self.position_input = QDoubleSpinBox()
        self.position_input.setRange(10, 100000)
        self.position_input.setValue(1000)
        self.position_input.setPrefix("$")
        self.position_input.setDecimals(0)
        self.position_input.setFixedHeight(36)
        self.position_input.setStyleSheet(f"QDoubleSpinBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 10px; color: {COLORS['text']}; font-size: 12px; }}")
        row1.addWidget(self.position_input)
        
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(10)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setFixedHeight(36)
        self.leverage_spin.setFixedWidth(70)
        self.leverage_spin.setStyleSheet(f"QSpinBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 10px; color: {COLORS['text']}; font-size: 12px; }}")
        row1.addWidget(self.leverage_spin)
        o_layout.addLayout(row1)
        
        # Calc label
        self.calc_label = QLabel("Маржа: $100 | Кол-во: 0")
        self.calc_label.setStyleSheet(f"font-size: 10px; color: {COLORS['success']}; background: rgba(0, 217, 165, 0.1); padding: 6px; border-radius: 4px;")
        self.calc_label.setWordWrap(True)
        o_layout.addWidget(self.calc_label)
        self.position_input.valueChanged.connect(self._update_calc)
        self.leverage_spin.valueChanged.connect(self._update_calc)
        
        # SL/TP
        row2 = QHBoxLayout()
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setRange(0.5, 50)
        self.sl_spin.setValue(2.0)
        self.sl_spin.setSuffix("% SL")
        self.sl_spin.setFixedHeight(32)
        self.sl_spin.setStyleSheet(f"QDoubleSpinBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 8px; color: {COLORS['text']}; font-size: 11px; }}")
        row2.addWidget(self.sl_spin)
        
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setRange(0.5, 100)
        self.tp_spin.setValue(4.0)
        self.tp_spin.setSuffix("% TP")
        self.tp_spin.setFixedHeight(32)
        self.tp_spin.setStyleSheet(self.sl_spin.styleSheet())
        row2.addWidget(self.tp_spin)
        o_layout.addLayout(row2)
        
        # Buttons
        btns = QHBoxLayout()
        self.long_btn = QPushButton("ЛОНГ 📈")
        self.long_btn.setFixedHeight(40)
        self.long_btn.setCursor(Qt.PointingHandCursor)
        self.long_btn.setEnabled(False)
        self.long_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['success']}; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: 700; }} QPushButton:hover {{ background: #00c9a7; }} QPushButton:disabled {{ background: #2a2a35; color: #555; }}")
        self.long_btn.clicked.connect(lambda: self._submit_order("buy"))
        btns.addWidget(self.long_btn)
        
        self.short_btn = QPushButton("ШОРТ 📉")
        self.short_btn.setFixedHeight(40)
        self.short_btn.setCursor(Qt.PointingHandCursor)
        self.short_btn.setEnabled(False)
        self.short_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['danger']}; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: 700; }} QPushButton:hover {{ background: #ff4444; }} QPushButton:disabled {{ background: #2a2a35; color: #555; }}")
        self.short_btn.clicked.connect(lambda: self._submit_order("sell"))
        btns.addWidget(self.short_btn)
        o_layout.addLayout(btns)
        
        o_layout.addStretch()
        content.addWidget(order_card)
        
        # Right - Positions + Auto
        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        
        # Positions
        pos_header = QHBoxLayout()
        pos_title = QLabel("📈 Позиции")
        pos_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        pos_header.addWidget(pos_title)
        pos_header.addStretch()
        
        self.pos_count = QLabel("0")
        self.pos_count.setStyleSheet(f"font-size: 10px; color: white; background: {COLORS['accent']}; padding: 2px 8px; border-radius: 4px;")
        pos_header.addWidget(self.pos_count)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(26, 26)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; }} QPushButton:hover {{ background: {COLORS['accent']}; }}")
        self.refresh_btn.clicked.connect(self._refresh_data)
        pos_header.addWidget(self.refresh_btn)
        right_col.addLayout(pos_header)
        
        # Positions scroll
        self.pos_scroll = QScrollArea()
        self.pos_scroll.setWidgetResizable(True)
        self.pos_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} QScrollBar:vertical {{ width: 4px; background: transparent; }} QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 2px; }}")
        self.pos_scroll.setMinimumHeight(120)
        
        self.pos_widget = QWidget()
        self.pos_layout = QVBoxLayout(self.pos_widget)
        self.pos_layout.setSpacing(6)
        self.pos_layout.setContentsMargins(0, 0, 0, 0)
        
        self.no_pos_lbl = QLabel("Нет позиций")
        self.no_pos_lbl.setAlignment(Qt.AlignCenter)
        self.no_pos_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; padding: 20px;")
        self.pos_layout.addWidget(self.no_pos_lbl)
        self.pos_layout.addStretch()
        
        self.pos_scroll.setWidget(self.pos_widget)
        right_col.addWidget(self.pos_scroll)
        
        content.addLayout(right_col, 1)
        layout.addLayout(content, 1)
        
        # Auto trade panel
        auto_card = QFrame()
        auto_card.setStyleSheet(f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}")
        a_layout = QVBoxLayout(auto_card)
        a_layout.setContentsMargins(12, 10, 12, 10)
        a_layout.setSpacing(8)
        
        a_header = QHBoxLayout()
        a_title = QLabel("🤖 Автоторговля")
        a_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        a_header.addWidget(a_title)
        a_header.addStretch()
        self.auto_status = QLabel("⚪ Выкл")
        self.auto_status.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        a_header.addWidget(self.auto_status)
        a_layout.addLayout(a_header)
        
        # Auto settings
        auto_row = QHBoxLayout()
        self.auto_tf = QComboBox()
        self.auto_tf.setFixedHeight(32)
        for tf, name in [("1h", "1ч"), ("4h", "4ч"), ("1d", "1д")]:
            self.auto_tf.addItem(name, tf)
        self.auto_tf.setStyleSheet(f"QComboBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 8px; color: {COLORS['text']}; font-size: 11px; }}")
        auto_row.addWidget(self.auto_tf)
        
        self.auto_leverage = QSpinBox()
        self.auto_leverage.setRange(1, 20)
        self.auto_leverage.setValue(10)
        self.auto_leverage.setSuffix("x")
        self.auto_leverage.setFixedHeight(32)
        self.auto_leverage.setStyleSheet(f"QSpinBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 8px; color: {COLORS['text']}; font-size: 11px; }}")
        auto_row.addWidget(self.auto_leverage)
        
        self.auto_risk = QDoubleSpinBox()
        self.auto_risk.setRange(1, 20)
        self.auto_risk.setValue(7)
        self.auto_risk.setDecimals(0)
        self.auto_risk.setSuffix("%")
        self.auto_risk.setFixedHeight(32)
        self.auto_risk.setStyleSheet(f"QDoubleSpinBox {{ background: {COLORS['bg_hover']}; border: none; border-radius: 6px; padding: 0 8px; color: {COLORS['text']}; font-size: 11px; }}")
        auto_row.addWidget(self.auto_risk)
        a_layout.addLayout(auto_row)
        
        # Coins
        coins_row = QHBoxLayout()
        self.auto_coins: Dict[str, QCheckBox] = {}
        for coin in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
            cb = QCheckBox(coin)
            cb.setChecked(coin in ["BTC", "ETH"])
            cb.setStyleSheet(f"QCheckBox {{ color: {COLORS['text']}; font-size: 11px; }} QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px; background: {COLORS['bg_hover']}; }} QCheckBox::indicator:checked {{ background: {COLORS['accent']}; }}")
            self.auto_coins[coin] = cb
            coins_row.addWidget(cb)
        coins_row.addStretch()
        a_layout.addLayout(coins_row)
        
        self.auto_btn = QPushButton("▶ Запустить")
        self.auto_btn.setFixedHeight(36)
        self.auto_btn.setCursor(Qt.PointingHandCursor)
        self.auto_btn.setEnabled(False)
        self.auto_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; border: none; border-radius: 8px; color: white; font-size: 12px; font-weight: 600; }} QPushButton:hover {{ background: {COLORS['accent_light']}; }} QPushButton:disabled {{ background: #2a2a35; color: #555; }}")
        self.auto_btn.clicked.connect(self._toggle_auto)
        a_layout.addWidget(self.auto_btn)
        
        layout.addWidget(auto_card)
        
        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.setStyleSheet(f"QPlainTextEdit {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 6px; font-family: Consolas; font-size: 10px; color: {COLORS['text_muted']}; }}")
        layout.addWidget(self.log)
        
        self.current_price = 0.0

    def _log(self, msg: str):
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    def _update_calc(self):
        pos = self.position_input.value()
        lev = self.leverage_spin.value()
        margin = pos / lev
        if self.current_price > 0:
            qty = pos / self.current_price
            coin = self.symbol_combo.currentText()
            self.calc_label.setText(f"Маржа: ${margin:,.0f} | Кол-во: {qty:,.4f} {coin}")
        else:
            self.calc_label.setText(f"Маржа: ${margin:,.0f}")
            
    def _load_settings(self):
        self.api_key.setText(self.settings.value("api_key", ""))
        self.api_secret.setText(self.settings.value("api_secret", ""))
        self.auto_leverage.setValue(self.settings.value("auto_leverage", 10, type=int))
        self.auto_risk.setValue(self.settings.value("auto_risk", 7.0, type=float))
        
    def _connect(self):
        if ccxt is None:
            QMessageBox.critical(self, "Ошибка", "pip install ccxt")
            return
        key = self.api_key.text().strip()
        secret = self.api_secret.text().strip()
        if not key or not secret:
            QMessageBox.warning(self, "Ошибка", "Введи API Key и Secret")
            return
        
        self.connect_btn.setText("⏳...")
        self.connect_btn.setEnabled(False)
        
        self.connect_worker = ConnectWorker(key, secret)
        self.connect_worker.success.connect(self._on_connect_success)
        self.connect_worker.error.connect(self._on_connect_error)
        self.connect_worker.start()
        
    def _on_connect_success(self, exchange):
        self.exchange = exchange
        self.settings.setValue("api_key", self.api_key.text().strip())
        self.settings.setValue("api_secret", self.api_secret.text().strip())
        
        self.conn_status.setText("🟢 Подключено")
        self.conn_status.setStyleSheet(f"font-size: 11px; color: {COLORS['success']}; background: rgba(0, 217, 165, 0.15); padding: 4px 10px; border-radius: 6px;")
        self.connect_btn.setText("✓")
        
        self.long_btn.setEnabled(True)
        self.short_btn.setEnabled(True)
        self.auto_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        
        self._log("✅ Подключено к Bybit Testnet")
        self._refresh_data()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(5000)
        
        # Автозапуск если была включена
        if self.settings.value("auto_trading", "false") == "true":
            QTimer.singleShot(2000, self._start_auto)
            
    def _on_connect_error(self, error: str):
        self.connect_btn.setText("🔌 Подключить")
        self.connect_btn.setEnabled(True)
        self._log(f"❌ Ошибка: {error}")
        
    def _refresh_data(self):
        if not self.exchange:
            return
        if hasattr(self, 'refresh_worker') and self.refresh_worker.isRunning():
            return
        symbol = self.symbol_combo.currentData()
        self.refresh_worker = RefreshWorker(self.exchange, symbol)
        self.refresh_worker.data_ready.connect(self._on_data_ready)
        self.refresh_worker.price_ready.connect(self._on_price_ready)
        self.refresh_worker.start()
        
    def _on_data_ready(self, available: float, total: float, pnl: float, positions: list):
        self.balance_widget.update_balance(available, total, pnl)
        self._update_positions(positions)
        
    def _on_price_ready(self, price: float):
        self.current_price = price
        self._update_calc()
        
    def _update_positions(self, positions: list):
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
                    pos.get('symbol') or '', (pos.get('side') or '').lower(),
                    float(pos.get('contracts') or 0), float(pos.get('entryPrice') or 0),
                    float(pos.get('markPrice') or 0), float(pos.get('unrealizedPnl') or 0),
                    float(pos.get('percentage') or 0), int(pos.get('leverage') or 1)
                )
                row.close_clicked.connect(self._close_position)
                self.pos_layout.insertWidget(self.pos_layout.count() - 1, row)
                self.position_rows.append(row)

    def _set_leverage_safe(self, leverage: int, symbol: str):
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            if "110043" not in str(e) and "not modified" not in str(e).lower():
                raise e
                
    def _submit_order(self, side: str):
        if not self.exchange:
            return
        try:
            symbol = self.symbol_combo.currentData()
            position_usdt = self.position_input.value()
            leverage = self.leverage_spin.value()
            
            self._set_leverage_safe(leverage, symbol)
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            margin = position_usdt / leverage
            qty = position_usdt / price
            
            coin = symbol.split('/')[0]
            if coin == "BTC": qty = round(qty, 3)
            elif coin == "ETH": qty = round(qty, 2)
            elif coin == "SOL": qty = round(qty, 1)
            else: qty = round(qty, 0)
            
            self._log(f"{'ЛОНГ 📈' if side == 'buy' else 'ШОРТ 📉'} {coin} | ${position_usdt:,.0f} | Маржа: ${margin:,.0f}")
            
            if side == "buy":
                self.exchange.create_market_buy_order(symbol, qty)
            else:
                self.exchange.create_market_sell_order(symbol, qty)
            
            self._log(f"✅ Ордер исполнен: {qty} {coin} @ ${price:,.2f}")
            self._refresh_data()
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")
            
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
                    self._log(f"✅ Закрыто {coin} | PnL: {'+'if pnl>=0 else ''}${pnl:.2f}")
                    self._refresh_data()
                except Exception as e:
                    self._log(f"❌ Ошибка: {e}")
                break
                
    def _toggle_auto(self):
        self.auto_trading = not self.auto_trading
        self._save_auto_settings()
        
        if self.auto_trading:
            self._start_auto()
        else:
            self.auto_status.setText("⚪ Выкл")
            self.auto_status.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
            self.auto_btn.setText("▶ Запустить")
            self.auto_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; border: none; border-radius: 8px; color: white; font-size: 12px; font-weight: 600; }} QPushButton:hover {{ background: {COLORS['accent_light']}; }}")
            self._log("🤖 Автоторговля остановлена")
            if hasattr(self, 'auto_timer'):
                self.auto_timer.stop()
                
    def _start_auto(self):
        self.auto_trading = True
        self.auto_status.setText("🟢 Активна")
        self.auto_status.setStyleSheet(f"font-size: 10px; color: {COLORS['success']};")
        self.auto_btn.setText("⏹ Остановить")
        self.auto_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['danger']}; border: none; border-radius: 8px; color: white; font-size: 12px; font-weight: 600; }} QPushButton:hover {{ background: #ff4444; }}")
        self._log("🤖 Автоторговля запущена")
        
        if not hasattr(self, 'auto_timer'):
            self.auto_timer = QTimer()
            self.auto_timer.timeout.connect(self._run_auto_worker)
        self.auto_timer.start(60000)
        QTimer.singleShot(1000, self._run_auto_worker)
        
    def _save_auto_settings(self):
        self.settings.setValue("auto_trading", "true" if self.auto_trading else "false")
        self.settings.setValue("auto_leverage", self.auto_leverage.value())
        self.settings.setValue("auto_risk", self.auto_risk.value())
        selected = [c for c, cb in self.auto_coins.items() if cb.isChecked()]
        self.settings.setValue("auto_coins", ",".join(selected))
        
    def _run_auto_worker(self):
        if not self.auto_trading or not self.exchange:
            return
        if hasattr(self, 'auto_worker') and self.auto_worker.isRunning():
            return
        
        settings = {
            'leverage': self.auto_leverage.value(),
            'risk_pct': self.auto_risk.value(),
            'tf': self.auto_tf.currentData() or "1h",
            'selected_coins': [c for c, cb in self.auto_coins.items() if cb.isChecked()]
        }
        
        self.auto_worker = AutoTradeWorker(self.exchange, settings, self._get_confluence_signal, self._get_htf_trend)
        self.auto_worker.log_signal.connect(self._log)
        self.auto_worker.refresh_signal.connect(self._refresh_data)
        self.auto_worker.open_position_signal.connect(self._auto_open_position)
        self.auto_worker.start()

    def _get_htf_trend(self, coin: str, tf: str) -> str:
        htf_map = {"1m": "15m", "5m": "1h", "15m": "4h", "1h": "4h", "4h": "1d", "1d": "1w"}
        htf = htf_map.get(tf, "4h")
        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            res = ema_get_signal(f"{coin}USDT.P", htf, "BYBIT_PERP")
            if isinstance(res, (list, tuple)) and len(res) >= 1:
                return str(res[0])
        except: pass
        return "neutral"
        
    def _get_confluence_signal(self, coin: str) -> tuple:
        try:
            from indicators.boswaves_ema_market_structure import get_signal as ema_get_signal
            from indicators.algoalpha_smart_money_breakout import get_signal as sm_get_signal
            from indicators.algoalpha_trend_targets import get_signal as tt_get_signal
        except:
            return "none", 0, "Индикаторы не найдены"
        
        symbol = f"{coin}USDT.P"
        tf = self.auto_tf.currentData() or "1h"
        results = {}
        
        for name, func in [("EMA", ema_get_signal), ("SM", sm_get_signal), ("Trend", tt_get_signal)]:
            try:
                res = func(symbol, tf, "BYBIT_PERP")
                results[name] = str(res[0]) if isinstance(res, (list, tuple)) else "neutral"
            except:
                results[name] = "neutral"
        
        bulls = sum(1 for v in results.values() if v == "bull")
        bears = sum(1 for v in results.values() if v == "bear")
        emoji = {"bull": "🟢", "bear": "🔴", "neutral": "⚪"}
        details = " | ".join([f"{emoji.get(v, '⚪')}{k}" for k, v in results.items()])
        
        if bulls >= 2 and bulls > bears:
            return "buy", bulls, details
        elif bears >= 2 and bears > bulls:
            return "sell", bears, details
        return "none", 0, details
        
    def _auto_open_position(self, symbol: str, side: str, size: float, sl_pct: float, tp_pct: float, leverage: int):
        try:
            self._set_leverage_safe(leverage, symbol)
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            if side == "buy":
                self.exchange.create_market_buy_order(symbol, size)
            else:
                self.exchange.create_market_sell_order(symbol, size)
            
            coin = symbol.split('/')[0]
            self._log(f"✅ АВТО {'ЛОНГ' if side == 'buy' else 'ШОРТ'} {size} {coin} @ ${price:,.2f}")
            self._refresh_data()
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")


# ============ MAIN WINDOW ============

class UnifiedWindow(QMainWindow):
    """Единое окно: Сигналы слева, Терминал справа"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local Signals Pro")
        self.setMinimumSize(1400, 800)
        
        # Icon
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = QSettings("LocalSignals", "Unified")
        self._setup_ui()
        self._load_geometry()
        
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        # Background
        self.bg = UnifiedBackground(central)
        
        # Content
        content = QWidget(central)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Splitter для изменения размеров панелей
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{ background: {COLORS['border']}; width: 2px; }}
            QSplitter::handle:hover {{ background: {COLORS['accent']}; }}
        """)
        
        # Left panel - Signals
        self.signals_panel = SignalsPanel()
        self.signals_panel.setMinimumWidth(400)
        self.splitter.addWidget(self.signals_panel)
        
        # Right panel - Terminal
        self.terminal_panel = TerminalPanel()
        self.terminal_panel.setMinimumWidth(500)
        self.splitter.addWidget(self.terminal_panel)
        
        # Default sizes (40% / 60%)
        self.splitter.setSizes([500, 900])
        
        layout.addWidget(self.splitter)
        
        # Root layout
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bg'):
            self.bg.setGeometry(self.centralWidget().rect())
            
    def _load_geometry(self):
        # Fullscreen by default
        screen = QApplication.primaryScreen().geometry()
        w = int(screen.width() * 0.92)
        h = int(screen.height() * 0.88)
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        
        # Restore splitter sizes
        sizes = self.settings.value("splitter_sizes")
        if sizes:
            self.splitter.setSizes([int(s) for s in sizes])
            
    def closeEvent(self, event):
        # Save splitter sizes
        self.settings.setValue("splitter_sizes", self.splitter.sizes())
        
        # Stop workers
        if self.signals_panel.worker and self.signals_panel.worker.isRunning():
            reply = QMessageBox.question(self, "Выход", "Мониторинг активен. Выйти?")
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self.signals_panel.worker.stop()
        
        if self.terminal_panel.auto_trading:
            self.terminal_panel.auto_trading = False
            if hasattr(self.terminal_panel, 'auto_timer'):
                self.terminal_panel.auto_timer.stop()
        
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    import os
    icon_path = os.path.join(os.path.dirname(__file__), "..", "content", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = UnifiedWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
