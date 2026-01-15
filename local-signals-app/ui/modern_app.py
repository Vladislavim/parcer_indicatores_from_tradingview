"""
Local Signals Pro - Современное приложение с шейдерами и анимациями
Адаптивный дизайн, плавные переходы, интерактивность
"""
from __future__ import annotations

import sys
import math
import random
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QPoint, QSize, QSettings, QUrl, Property, Signal, QRect, QSequentialAnimationGroup
)
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QLinearGradient, 
    QRadialGradient, QPen, QBrush, QDesktopServices, QScreen, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit,
    QComboBox, QCheckBox, QPlainTextEdit, QMessageBox, QGridLayout,
    QGraphicsDropShadowEffect, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core.worker import Worker
from ui.styles import (
    COLORS, DARK_THEME, LIGHT_THEME, set_theme, get_current_theme, get_label_style,
    AnimatedCard, ModernInput, ModernCombo, SmallButton, BigButton
)


# Кэш иконок - глобальный для всего приложения
_icon_cache: Dict[str, QPixmap] = {}


def get_coin_icon(coin: str, size: int = 24) -> Optional[QPixmap]:
    """Получить иконку монеты из кэша"""
    key = f"{coin}_{size}"
    if key in _icon_cache:
        return _icon_cache[key]
    return None


class CoinIconLoader:
    """Загрузчик иконок монет - синглтон"""
    
    _instance = None
    _manager = None
    _pending: Dict[str, List[callable]] = {}
    _loading: set = set()  # Отслеживаем что уже загружается
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if CoinIconLoader._manager is None:
            CoinIconLoader._manager = QNetworkAccessManager()
            CoinIconLoader._pending = {}
            CoinIconLoader._loading = set()
        
    def load(self, coin: str, callback: callable, size: int = 28):
        """Загрузить иконку асинхронно"""
        key = f"{coin}_{size}"
        
        # Уже в кэше
        if key in _icon_cache:
            callback(_icon_cache[key])
            return
            
        # Добавляем callback в очередь
        if key not in CoinIconLoader._pending:
            CoinIconLoader._pending[key] = []
        CoinIconLoader._pending[key].append(callback)
        
        # Уже загружается - просто ждем
        if key in CoinIconLoader._loading:
            return
            
        url = COIN_ICONS.get(coin)
        if not url:
            # Нет URL - вызываем callback с None
            for cb in CoinIconLoader._pending.pop(key, []):
                cb(None)
            return
        
        CoinIconLoader._loading.add(key)
        
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.PreferCache)
        reply = CoinIconLoader._manager.get(request)
        reply.finished.connect(lambda: self._on_loaded(reply, coin, size))
        
    def _on_loaded(self, reply: QNetworkReply, coin: str, size: int):
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


class CoinCheckBox(QWidget):
    """Чекбокс с иконкой монеты - иконка слева"""
    
    def __init__(self, symbol: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.coin = symbol.replace("USDT.P", "")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Иконка СЛЕВА
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(28, 28)
        self.icon_lbl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_lbl)
        
        # Чекбокс справа от иконки
        self.cb = QCheckBox()
        self.cb.setChecked(True)
        self.cb.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: none;
                background: {COLORS['bg_hover']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['accent']};
            }}
        """)
        layout.addWidget(self.cb)
        
        loader = CoinIconLoader()
        loader.load(self.coin, self._set_icon, 28)
        
        self.setToolTip(self.coin)
        self.setCursor(Qt.PointingHandCursor)
        
    def _set_icon(self, pixmap: Optional[QPixmap]):
        if pixmap:
            self.icon_lbl.setPixmap(pixmap)
        else:
            self.icon_lbl.setText(self.coin[:2])
            self.icon_lbl.setStyleSheet(f"""
                font-size: 11px; 
                font-weight: 700; 
                color: {COLORS['text']};
                background: transparent;
                border: none;
            """)
            self.icon_lbl.setAlignment(Qt.AlignCenter)
            
    def isChecked(self) -> bool:
        return self.cb.isChecked()
        
    def setChecked(self, checked: bool):
        self.cb.setChecked(checked)

# Константы
MONITOR_SYMBOLS = [
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "XRPUSDT.P", "DOGEUSDT.P",
    "ADAUSDT.P", "AVAXUSDT.P", "LINKUSDT.P", "SUIUSDT.P", "WIFUSDT.P",
]

# URL иконок монет (CoinMarketCap CDN)
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

THREAD_ID_DEV = 5
DEFAULT_CHAT_ID = "-1003065825691"

# Стиль для лейблов без обводки
LABEL_STYLE = get_label_style()


class ColorfulAuraBackground(QWidget):
    """Красочный 3D Aura шейдер с множеством цветов"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time = 0
        self.orbs = []
        self.particles = []
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # Яркие цветные орбы
        orb_colors = [
            (108, 92, 231, 80),    # Фиолетовый
            (162, 155, 254, 70),   # Лавандовый
            (0, 206, 201, 75),     # Бирюзовый
            (253, 121, 168, 65),   # Розовый
            (253, 203, 110, 60),   # Желтый
            (0, 217, 165, 70),     # Зеленый
            (255, 107, 107, 65),   # Красный
        ]
        
        for i in range(8):
            color = random.choice(orb_colors)
            self.orbs.append({
                'x': random.uniform(0.1, 0.9),
                'y': random.uniform(0.1, 0.9),
                'radius': random.uniform(200, 500),
                'color': color,
                'speed_x': random.uniform(-0.0005, 0.0005),
                'speed_y': random.uniform(-0.0005, 0.0005),
                'phase': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.02, 0.05),
            })
        
        # Частицы для живости
        for i in range(50):
            self.particles.append({
                'x': random.uniform(0, 1),
                'y': random.uniform(0, 1),
                'size': random.uniform(1, 3),
                'speed': random.uniform(0.0005, 0.002),
                'alpha': random.uniform(0.3, 0.8),
            })
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(25)
        
    def _animate(self):
        self.time += 0.03
        
        for orb in self.orbs:
            orb['x'] += orb['speed_x'] + 0.0001 * math.sin(self.time * 0.5 + orb['phase'])
            orb['y'] += orb['speed_y'] + 0.0001 * math.cos(self.time * 0.5 + orb['phase'])
            
            if orb['x'] < 0.05 or orb['x'] > 0.95:
                orb['speed_x'] *= -1
            if orb['y'] < 0.05 or orb['y'] > 0.95:
                orb['speed_y'] *= -1
                
        for p in self.particles:
            p['y'] -= p['speed']
            if p['y'] < 0:
                p['y'] = 1
                p['x'] = random.uniform(0, 1)
                
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Градиентный фон в зависимости от темы
        bg = QLinearGradient(0, 0, w, h)
        if get_current_theme() == "light":
            bg.setColorAt(0, QColor(245, 245, 247))
            bg.setColorAt(0.5, QColor(235, 235, 240))
            bg.setColorAt(1, QColor(245, 245, 247))
        else:
            bg.setColorAt(0, QColor(13, 13, 15))
            bg.setColorAt(0.5, QColor(18, 18, 22))
            bg.setColorAt(1, QColor(13, 13, 15))
        painter.fillRect(self.rect(), bg)
        
        # Орбы (менее яркие для светлой темы)
        alpha_mult = 0.5 if get_current_theme() == "light" else 1.0
        for orb in self.orbs:
            cx, cy = int(orb['x'] * w), int(orb['y'] * h)
            pulse = 1 + 0.3 * math.sin(self.time * orb['pulse_speed'] * 50 + orb['phase'])
            radius = int(orb['radius'] * pulse)
            
            gradient = QRadialGradient(cx, cy, radius)
            r, g, b, a = orb['color']
            a = int(a * alpha_mult)
            gradient.setColorAt(0, QColor(r, g, b, a))
            gradient.setColorAt(0.4, QColor(r, g, b, int(a * 0.5)))
            gradient.setColorAt(0.7, QColor(r, g, b, int(a * 0.2)))
            gradient.setColorAt(1, QColor(r, g, b, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        
        # Частицы
        particle_color = 100 if get_current_theme() == "light" else 255
        for p in self.particles:
            px, py = int(p['x'] * w), int(p['y'] * h)
            painter.setBrush(QColor(particle_color, particle_color, particle_color, int(255 * p['alpha'] * (0.5 + 0.5 * math.sin(self.time * 2)))))
            painter.drawEllipse(px, py, int(p['size']), int(p['size']))
        
        # Виньетка
        vignette = QRadialGradient(w/2, h/2, max(w, h) * 0.8)
        vignette.setColorAt(0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.7, QColor(0, 0, 0, 30))
        vignette.setColorAt(1, QColor(0, 0, 0, 120))
        painter.setBrush(vignette)
        painter.drawRect(self.rect())


class PulseIndicator(QWidget):
    """Пульсирующий индикатор с анимацией"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = "na"
        self.pulse = 0
        self.setFixedSize(20, 20)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(30)
        
    def _animate(self):
        self.pulse = (self.pulse + 4) % 360
        self.update()
        
    def set_status(self, status: str):
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        colors = {
            "bull": COLORS["success"],
            "bear": COLORS["danger"],
            "neutral": COLORS["warning"],
            "na": COLORS["text_muted"]
        }
        
        color = QColor(colors.get(self.status, colors["na"]))
        pulse_val = abs(math.sin(math.radians(self.pulse)))
        
        # Внешнее свечение
        glow = QRadialGradient(10, 10, 10)
        glow_color = QColor(color)
        glow_color.setAlphaF(0.4 * pulse_val)
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(0, 0, 20, 20)
        
        # Основной круг
        painter.setBrush(color)
        painter.drawEllipse(5, 5, 10, 10)


class IndicatorBadge(QFrame):
    """Бейдж индикатора - минималистичный без обводок"""
    
    def __init__(self, indicator_key: str, parent=None):
        super().__init__(parent)
        self.indicator_key = indicator_key
        self.status = "na"
        
        self.names = {
            "ema_ms": "EMA",
            "smart_money": "SM",
            "trend_targets": "Тренд"
        }
        
        self.setFixedHeight(26)
        self.setMinimumWidth(60)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"font-size: 8px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.dot)
        
        self.name_lbl = QLabel(self.names.get(indicator_key, indicator_key))
        self.name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.name_lbl)
        
        self._update_style()
        
    def set_status(self, status: str):
        self.status = status
        self._update_style()
        
    def _update_style(self):
        if self.status == "bull":
            self.dot.setStyleSheet(f"font-size: 8px; color: {COLORS['success']}; background: transparent;")
            self.name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['success']}; background: transparent;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0, 217, 165, 0.15);
                    border: none;
                    border-radius: 13px;
                }}
            """)
        elif self.status == "bear":
            self.dot.setStyleSheet(f"font-size: 8px; color: {COLORS['danger']}; background: transparent;")
            self.name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['danger']}; background: transparent;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(255, 107, 107, 0.15);
                    border: none;
                    border-radius: 13px;
                }}
            """)
        elif self.status == "neutral":
            self.dot.setStyleSheet(f"font-size: 8px; color: {COLORS['warning']}; background: transparent;")
            self.name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['warning']}; background: transparent;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(253, 203, 110, 0.1);
                    border: none;
                    border-radius: 13px;
                }}
            """)
        else:
            self.dot.setStyleSheet(f"font-size: 8px; color: {COLORS['text_muted']}; background: transparent;")
            self.name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(45, 45, 53, 0.3);
                    border: none;
                    border-radius: 13px;
                }}
            """)


class SignalCard(QFrame):
    """Карточка сигнала - чистая без лишних обводок"""
    
    clicked = Signal(str)
    
    def __init__(self, symbol: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.status = "na"
        self.indicator_states = {}
        self._setup_ui()
        
    def _setup_ui(self):
        self.setMinimumHeight(70)
        self.setMaximumHeight(70)
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Монета и статус
        left = QVBoxLayout()
        left.setSpacing(2)
        
        coin_name = self.symbol.replace("USDT.P", "")
        self.name_lbl = QLabel(coin_name)
        self.name_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['text']}; background: transparent;")
        left.addWidget(self.name_lbl)
        
        self.action_lbl = QLabel("")
        self.action_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
        left.addWidget(self.action_lbl)
        
        layout.addLayout(left)
        layout.addStretch()
        
        # Бейджи индикаторов
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)
        
        self.badges = {}
        for key in ["ema_ms", "smart_money", "trend_targets"]:
            badge = IndicatorBadge(key)
            self.badges[key] = badge
            badges_layout.addWidget(badge)
            
        layout.addLayout(badges_layout)
        layout.addStretch()
        
        # Время
        self.time_lbl = QLabel("")
        self.time_lbl.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.time_lbl)
        
        # Кнопка графика
        self.chart_btn = QPushButton("📈")
        self.chart_btn.setFixedSize(36, 36)
        self.chart_btn.setCursor(Qt.PointingHandCursor)
        self.chart_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS["accent"]};
                border: none;
                border-radius: 10px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: {COLORS["accent_light"]};
            }}
        """)
        self.chart_btn.clicked.connect(lambda: self.clicked.emit(self.symbol))
        layout.addWidget(self.chart_btn)
        
    def enterEvent(self, event):
        is_light = get_current_theme() == "light"
        hover_bg = "rgba(200, 200, 210, 0.4)" if is_light else "rgba(40, 40, 50, 0.8)"
        self.setStyleSheet(f"""
            QFrame {{
                background: {hover_bg};
                border: 1px solid {COLORS['accent']};
                border-radius: 14px;
            }}
        """)
        
    def leaveEvent(self, event):
        self._update_card_style()
        
    def _update_card_style(self):
        is_light = get_current_theme() == "light"
        if self.status == "bull":
            bg = "rgba(0, 184, 148, 0.15)" if is_light else "rgba(0, 217, 165, 0.1)"
            border = "rgba(0, 217, 165, 0.4)"
            self.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 14px;
                }}
            """)
        elif self.status == "bear":
            bg = "rgba(231, 76, 60, 0.15)" if is_light else "rgba(255, 107, 107, 0.1)"
            border = "rgba(255, 107, 107, 0.4)"
            self.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 14px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 14px;
                }}
            """)
        
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
            self.action_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['success']}; background: transparent;")
        elif bears > bulls and bears > 0:
            self.status = "bear"
            self.action_lbl.setText("ШОРТ")
            self.action_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['danger']}; background: transparent;")
        else:
            self.status = "neutral"
            self.action_lbl.setText("Боковик")
            self.action_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['warning']}; background: transparent;")
            
        self._update_card_style()
            
    def update_signal(self, status: str, detail: str):
        indicator = "ema_ms"
        if "SM" in detail:
            indicator = "smart_money"
        elif "Тренд" in detail:
            indicator = "trend_targets"
        self.update_indicator(indicator, status, detail)


class LiveProgress(QWidget):
    """Живой индикатор прогресса"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.pos = 0
        self.active = False
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        
    def start(self):
        self.active = True
        self.timer.start(20)
        self.show()
        
    def stop(self):
        self.active = False
        self.timer.stop()
        self.hide()
        
    def _animate(self):
        self.pos = (self.pos + 3) % (self.width() + 100)
        self.update()
        
    def paintEvent(self, event):
        if not self.active:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фон
        painter.fillRect(self.rect(), QColor(COLORS["bg_hover"]))
        
        # Бегущая полоса
        gradient = QLinearGradient(self.pos - 100, 0, self.pos, 0)
        gradient.setColorAt(0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.5, QColor(COLORS["accent"]))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(self.pos - 100, 0, 100, 4, 2, 2)


class ChartWindow(QMainWindow):
    """Окно с графиком - открывает TradingView в браузере с индикаторами"""
    
    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol.replace("USDT.P", "USDT")
        self.setWindowTitle(f"📈 {self.symbol}")
        self.setMinimumSize(1000, 700)
        
        # Адаптивный размер
        screen = QApplication.primaryScreen().geometry()
        self.resize(int(screen.width() * 0.85), int(screen.height() * 0.85))
        
        self._setup_ui()
        self._animate_open()
        
        # СРАЗУ открываем в браузере где есть твои индикаторы
        self._open_browser()
        
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background: #131722;")
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Компактный заголовок
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background: {COLORS['bg_card']}; border-bottom: 1px solid {COLORS['border']};")
        
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel(f"📈 {self.symbol}")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        h_layout.addWidget(title)
        h_layout.addStretch()
        
        # Информация
        info = QLabel("График открыт в браузере с твоими индикаторами")
        info.setStyleSheet(f"font-size: 13px; color: {COLORS['success']};")
        h_layout.addWidget(info)
        
        h_layout.addStretch()
        
        btn = SmallButton("Открыть ещё раз")
        btn.clicked.connect(self._open_browser)
        h_layout.addWidget(btn)
        
        layout.addWidget(header)
        
        # Превью графика в виджете (базовый)
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.web = QWebEngineView()
            self.web.setStyleSheet("background: #131722;")
            
            html = f'''<!DOCTYPE html>
<html style="height:100%;margin:0;padding:0;">
<head><meta charset="utf-8">
<style>
    html, body {{ height: 100%; margin: 0; padding: 0; overflow: hidden; background: #131722; }}
    #tv_chart {{ width: 100%; height: 100%; }}
</style>
</head>
<body style="height:100%;margin:0;padding:0;">
<div id="tv_chart" style="width:100%;height:100%;"></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>
new TradingView.widget({{
    "autosize": true,
    "symbol": "BYBIT:{self.symbol}",
    "interval": "60",
    "timezone": "Etc/UTC",
    "theme": "dark",
    "style": "1",
    "locale": "ru",
    "toolbar_bg": "#131722",
    "enable_publishing": false,
    "container_id": "tv_chart",
    "hide_side_toolbar": false,
    "allow_symbol_change": true,
    "studies": ["MAExp@tv-basicstudies", "RSI@tv-basicstudies"],
    "overrides": {{
        "paneProperties.background": "#131722",
        "mainSeriesProperties.candleStyle.upColor": "#00D9A5",
        "mainSeriesProperties.candleStyle.downColor": "#FF6B6B",
        "mainSeriesProperties.candleStyle.borderUpColor": "#00D9A5",
        "mainSeriesProperties.candleStyle.borderDownColor": "#FF6B6B"
    }}
}});
</script>
</body>
</html>'''
            self.web.setHtml(html)
            layout.addWidget(self.web, 1)
        except ImportError:
            lbl = QLabel("Превью недоступно\nГрафик открыт в браузере")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 16px;")
            layout.addWidget(lbl, 1)
            
    def _open_browser(self):
        """Открыть TradingView в браузере - там будут твои сохраненные индикаторы"""
        url = f"https://www.tradingview.com/chart/?symbol=BYBIT:{self.symbol}"
        QDesktopServices.openUrl(QUrl(url))
        
    def _animate_open(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim


class MainWindow(QMainWindow):
    """Главное окно с адаптивным дизайном"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local Signals Pro")
        
        # Иконка приложения
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = QSettings("LocalSignals", "Pro")
        self.worker: Optional[Worker] = None
        self.cards: Dict[str, SignalCard] = {}
        self.chart_windows: List[ChartWindow] = []
        self.terminal = None
        
        self._setup_ui()
        self._load_settings()
        self._animate_open()
        
        # Адаптивный размер
        screen = QApplication.primaryScreen().geometry()
        self.resize(int(screen.width() * 0.85), int(screen.height() * 0.85))
        self.move(int(screen.width() * 0.075), int(screen.height() * 0.075))
        
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        # Фон
        self.bg = ColorfulAuraBackground(central)
        
        # Контент
        content = QWidget(central)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Левая панель
        self.left_panel = self._create_left_panel()
        layout.addWidget(self.left_panel, 1)
        
        # Правая панель
        self.right_panel = self._create_right_panel()
        layout.addWidget(self.right_panel, 2)
        
        # Главный layout
        main = QVBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(content)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bg'):
            self.bg.setGeometry(self.centralWidget().rect())
            
    def _create_left_panel(self):
        panel = AnimatedCard()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Заголовок
        self.title_left = QLabel("⚙️ Настройки")
        self.title_left.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        layout.addWidget(self.title_left)
        
        # Биржа
        self.lbl_exchange = QLabel("Биржа")
        self.lbl_exchange.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self.lbl_exchange)
        self.exchange = ModernCombo()
        self.exchange.addItem("Bybit Фьючерсы", "BYBIT_PERP")
        self.exchange.addItem("Binance Спот", "BINANCE_SPOT")
        layout.addWidget(self.exchange)
        
        # Таймфрейм
        self.lbl_tf = QLabel("Таймфрейм")
        self.lbl_tf.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self.lbl_tf)
        self.tf = ModernCombo()
        for k, v in [("1m", "1 мин"), ("5m", "5 мин"), ("15m", "15 мин"), ("1h", "1 час"), ("4h", "4 часа"), ("1d", "1 день")]:
            self.tf.addItem(v, k)
        self.tf.setCurrentIndex(3)
        layout.addWidget(self.tf)
        
        # Telegram
        self.lbl_tg = QLabel("Telegram")
        self.lbl_tg.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self.lbl_tg)
        self.tg_token = ModernInput("Токен бота")
        self.tg_token.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.tg_token)
        
        self.tg_chat = ModernInput("ID чата")
        self.tg_chat.setText(DEFAULT_CHAT_ID)
        layout.addWidget(self.tg_chat)
        
        # Маленькая кнопка теста
        self.test_btn = SmallButton("🔔 Тест")
        self.test_btn.clicked.connect(self._test_tg)
        layout.addWidget(self.test_btn)
        
        # Переключатель темы
        theme_row = QHBoxLayout()
        self.lbl_theme = QLabel("Тема")
        self.lbl_theme.setStyleSheet(LABEL_STYLE)
        theme_row.addWidget(self.lbl_theme)
        theme_row.addStretch()
        
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("Переключить тему")
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 10px;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']};
            }}
        """)
        self.theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self.theme_btn)
        layout.addLayout(theme_row)
        
        layout.addStretch()
        
        # Прогресс
        self.progress = LiveProgress()
        self.progress.hide()
        layout.addWidget(self.progress)
        
        # Кнопки
        self.start_btn = BigButton("▶ Запустить", "success")
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = BigButton("⏹ Остановить", "danger")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # Кнопка терминала с иконкой Bybit
        self.terminal_btn = QPushButton("  Bybit Terminal")
        self.terminal_btn.setFixedHeight(40)
        self.terminal_btn.setCursor(Qt.PointingHandCursor)
        self.terminal_btn.setStyleSheet(f"""
            QPushButton {{
                background: #f7a600;
                border: none;
                border-radius: 10px;
                color: #000;
                font-size: 13px;
                font-weight: 700;
                padding-left: 8px;
            }}
            QPushButton:hover {{
                background: #ffb820;
            }}
        """)
        self.terminal_btn.clicked.connect(self._open_terminal)
        layout.addWidget(self.terminal_btn)
        
        # Загружаем иконку Bybit для кнопки
        self._load_bybit_icon()
        
        return panel

        
    def _create_right_panel(self):
        panel = AnimatedCard()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Заголовок
        header = QHBoxLayout()
        self.title_right = QLabel("📊 Сигналы")
        self.title_right.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        header.addWidget(self.title_right)
        header.addStretch()
        
        self.status_lbl = QLabel("Ожидание")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['text_muted']};
            background: {COLORS['bg_hover']}; padding: 6px 12px; border-radius: 8px;
        """)
        header.addWidget(self.status_lbl)
        layout.addLayout(header)
        
        # Чекбоксы монет с иконками
        coins_grid = QGridLayout()
        coins_grid.setSpacing(4)
        self.coin_cbs: Dict[str, CoinCheckBox] = {}
        
        for i, sym in enumerate(MONITOR_SYMBOLS):
            cb = CoinCheckBox(sym)
            self.coin_cbs[sym] = cb
            coins_grid.addWidget(cb, i // 5, i % 5)
        layout.addLayout(coins_grid)
        
        # Карточки сигналов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {COLORS['bg_card']}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['accent']}; border-radius: 3px; min-height: 30px;
            }}
        """)
        
        scroll_w = QWidget()
        self.cards_layout = QVBoxLayout(scroll_w)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 8, 0, 0)
        
        for sym in MONITOR_SYMBOLS:
            card = SignalCard(sym)
            card.clicked.connect(self._open_chart)
            self.cards[sym] = card
            self.cards_layout.addWidget(card)
            
        self.cards_layout.addStretch()
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll, 1)
        
        # Лог
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet(f"""
            QPlainTextEdit {{
                background: rgba(13, 13, 15, 0.8);
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                color: {COLORS['text_muted']};
            }}
        """)
        layout.addWidget(self.log)
        
        return panel
        
    def _log(self, msg: str):
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    def _test_tg(self):
        token, chat = self.tg_token.text().strip(), self.tg_chat.text().strip()
        if not token or not chat:
            QMessageBox.warning(self, "Ошибка", "Заполните токен и чат")
            return
        try:
            from core.worker import send_telegram_message
            send_telegram_message(token, chat, "✅ Local Signals Pro - тест успешен!", THREAD_ID_DEV)
            self._log("Telegram тест OK")
        except Exception as e:
            self._log(f"Ошибка: {e}")
    
    def _toggle_theme(self):
        """Переключить тему между тёмной и светлой"""
        current = get_current_theme()
        new_theme = "light" if current == "dark" else "dark"
        set_theme(new_theme)
        
        # Обновляем иконку кнопки
        self.theme_btn.setText("☀️" if new_theme == "dark" else "🌙")
        
        # Сохраняем выбор
        self.settings.setValue("theme", new_theme)
        
        # Перезагружаем UI
        self._apply_theme()
        self._log(f"Тема: {'тёмная' if new_theme == 'dark' else 'светлая'}")
    
    def _apply_theme(self):
        """Применить текущую тему ко всем элементам"""
        is_light = get_current_theme() == "light"
        
        # Обновляем фон
        if hasattr(self, 'bg'):
            self.bg.update()
        
        # Обновляем кнопку темы
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_hover']};
                border: none;
                border-radius: 10px;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']};
            }}
        """)
        
        # Обновляем лог
        self.log.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                color: {COLORS['text']};
            }}
        """)
        
        # Обновляем статус
        if self.worker and self.worker.isRunning():
            self.status_lbl.setStyleSheet(f"""
                font-size: 12px; color: {COLORS['success']};
                background: rgba(0, 217, 165, 0.15); padding: 6px 12px; border-radius: 8px;
            """)
        else:
            self.status_lbl.setStyleSheet(f"""
                font-size: 12px; color: {COLORS['text_muted']};
                background: {COLORS['bg_hover']}; padding: 6px 12px; border-radius: 8px;
            """)
        
        # Обновляем комбобоксы
        combo_style = f"""
            QComboBox {{
                background: {COLORS["bg_card"]};
                border: 2px solid {COLORS["border"]};
                border-radius: 14px;
                padding: 12px 16px;
                font-size: 14px;
                color: {COLORS["text"]};
            }}
            QComboBox:hover {{ border-color: {COLORS["accent"]}; }}
            QComboBox::drop-down {{ border: none; width: 35px; }}
            QComboBox::down-arrow {{
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {COLORS["text_muted"]};
            }}
            QComboBox QAbstractItemView {{
                background: {COLORS["bg_card"]};
                border: 2px solid {COLORS["border"]};
                border-radius: 12px;
                selection-background-color: {COLORS["accent"]};
                color: {COLORS["text"]};
            }}
        """
        self.exchange.setStyleSheet(combo_style)
        self.tf.setStyleSheet(combo_style)
        
        # Обновляем инпуты
        input_style = f"""
            QLineEdit {{
                background: {COLORS["bg_card"]};
                border: 2px solid {COLORS["border"]};
                border-radius: 14px;
                padding: 12px 16px;
                font-size: 14px;
                color: {COLORS["text"]};
            }}
            QLineEdit:focus {{
                border-color: {COLORS["accent"]};
            }}
        """
        self.tg_token.setStyleSheet(input_style)
        self.tg_chat.setStyleSheet(input_style)
        
        # Обновляем кнопки
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS["bg_hover"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 10px;
                color: {COLORS["text"]};
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: {COLORS["accent"]};
                border-color: {COLORS["accent"]};
            }}
        """)
        
        # Обновляем карточки сигналов
        for card in self.cards.values():
            card.name_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['text']}; background: transparent;")
            card.time_lbl.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']}; background: transparent;")
            card.action_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent;")
            card._update_card_style()
            # Обновляем бейджи
            for badge in card.badges.values():
                badge._update_style()
        
        # Обновляем панели (левую и правую)
        if hasattr(self, 'left_panel'):
            self.left_panel.update_theme()
        if hasattr(self, 'right_panel'):
            self.right_panel.update_theme()
        
        # Обновляем заголовки
        if hasattr(self, 'title_left'):
            self.title_left.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        if hasattr(self, 'title_right'):
            self.title_right.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        
        # Обновляем лейблы
        label_style = f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent; border: none;"
        for lbl in [self.lbl_exchange, self.lbl_tf, self.lbl_tg, self.lbl_theme]:
            lbl.setStyleSheet(label_style)
            
    def _open_chart(self, symbol: str):
        """Открыть график в отдельном окне"""
        chart = ChartWindow(symbol)
        chart.show()
        self.chart_windows.append(chart)
    
    def _load_bybit_icon(self):
        """Загружает иконку Bybit для кнопки терминала"""
        self._icon_manager = QNetworkAccessManager()
        url = "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png"
        request = QNetworkRequest(QUrl(url))
        reply = self._icon_manager.get(request)
        reply.finished.connect(lambda: self._on_bybit_icon_loaded(reply))
        
    def _on_bybit_icon_loaded(self, reply):
        """Callback когда иконка загружена"""
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data.data())
            if not pixmap.isNull():
                icon_pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                from PySide6.QtGui import QIcon
                self.terminal_btn.setIcon(QIcon(icon_pixmap))
                self.terminal_btn.setIconSize(QSize(20, 20))
        reply.deleteLater()
    
    def _open_terminal(self):
        """Открыть терминал Bybit"""
        # Ленивый импорт чтобы избежать циклических зависимостей
        from ui.terminal_window import BybitTerminal
        
        if not hasattr(self, 'terminal') or self.terminal is None:
            self.terminal = BybitTerminal(self)
        self.terminal.show()
        self.terminal.raise_()
        self.terminal.activateWindow()
        
    def _get_selected_coins(self) -> List[str]:
        """Получить текущий список выбранных монет (для горячего обновления)"""
        return [s for s, cb in self.coin_cbs.items() if cb.isChecked()]
    
    def _get_current_source(self) -> str:
        """Получить текущую биржу (для горячего обновления)"""
        return self.exchange.currentData()
    
    def _get_current_timeframe(self) -> str:
        """Получить текущий таймфрейм (для горячего обновления)"""
        return self.tf.currentData()

        
    def _start(self):
        if self.worker and self.worker.isRunning():
            return
            
        selected = [s for s, cb in self.coin_cbs.items() if cb.isChecked()]
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
            "tg_mention": "",
            "get_alert_symbols": self._get_selected_coins,  # Callback для горячего обновления
            "get_source": self._get_current_source,  # Callback для горячего обновления биржи
            "get_timeframe": self._get_current_timeframe,  # Callback для горячего обновления ТФ
        }
        
        self._save_settings()
        
        self.worker = Worker(config)
        self.worker.log.connect(self._log)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.start()
        
        self.status_lbl.setText("🟢 Активен")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['success']};
            background: rgba(0, 217, 165, 0.15); padding: 6px 12px; border-radius: 8px;
        """)
        
        self._log(f"Запуск: {len(selected)} монет, ТФ={config['timeframe']}")
        self.worker.start()
        
    def _stop(self):
        if self.worker:
            self.worker.stop()
            self._log("Остановка...")
            
    def _on_finished(self):
        self.worker = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.stop()
        
        self.status_lbl.setText("Остановлен")
        self.status_lbl.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['text_muted']};
            background: {COLORS['bg_hover']}; padding: 6px 12px; border-radius: 8px;
        """)
        self._log("Остановлен")
        
    def _on_status(self, symbol: str, indicator: str, status: str, detail: str, updated: str):
        # Пробуем разные форматы ключа
        possible_keys = [
            f"{symbol}USDT.P",
            f"{symbol}.P", 
            symbol,
            symbol.replace("USDT", "USDT.P")
        ]
        
        for key in possible_keys:
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
        
        # Всегда тёмная тема по умолчанию
        set_theme("dark")
        self.theme_btn.setText("🌙")
        
    def _animate_open(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim
        
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(self, "Выход", "Мониторинг активен. Выйти?")
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.stop()
        self._save_settings()
        for w in self.chart_windows:
            w.close()
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Не закрывать при закрытии последнего окна (для работы в трее)
    app.setQuitOnLastWindowClosed(False)
    
    # Настройки для запоминания последнего окна
    settings = QSettings("LocalSignals", "Pro")
    
    # Иконка приложения (для панели задач)
    import os
    from PySide6.QtGui import QIcon, QAction
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu
    
    icon_path = os.path.join(os.path.dirname(__file__), "..", "content", "icon.ico")
    app_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
    app.setWindowIcon(app_icon)
    
    # Шрифт
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    
    # Переменная для хранения последнего активного окна
    last_active_window = {"window": "main"}  # "main" или "terminal"
    
    # Отслеживаем активацию окон
    def on_window_activated(w):
        if w == window:
            last_active_window["window"] = "main"
            settings.setValue("last_window", "main")
        elif hasattr(window, 'terminal') and w == window.terminal:
            last_active_window["window"] = "terminal"
            settings.setValue("last_window", "terminal")
    
    app.focusWindowChanged.connect(on_window_activated)
    
    # Системный трей
    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip("Local Signals Pro")
    
    # Функция для показа последнего активного окна
    def show_last_window():
        last = settings.value("last_window", "main")
        if last == "terminal" and hasattr(window, 'terminal') and window.terminal:
            window.terminal.show()
            window.terminal.raise_()
            window.terminal.activateWindow()
        else:
            window.show()
            window.raise_()
            window.activateWindow()
    
    # Меню трея
    tray_menu = QMenu()
    
    show_action = QAction("📊 Открыть", tray_menu)
    show_action.triggered.connect(show_last_window)
    tray_menu.addAction(show_action)
    
    # Отдельные пункты для окон
    tray_menu.addSeparator()
    
    main_action = QAction("🏠 Главное окно", tray_menu)
    main_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
    tray_menu.addAction(main_action)
    
    terminal_action = QAction("💹 Терминал", tray_menu)
    def show_terminal():
        if hasattr(window, 'terminal') and window.terminal:
            window.terminal.show()
            window.terminal.raise_()
            window.terminal.activateWindow()
        else:
            window._open_terminal()
    terminal_action.triggered.connect(show_terminal)
    tray_menu.addAction(terminal_action)
    
    tray_menu.addSeparator()
    
    # Статус
    status_action = QAction("⚪ Не подключено", tray_menu)
    status_action.setEnabled(False)
    tray_menu.addAction(status_action)
    
    tray_menu.addSeparator()
    
    quit_action = QAction("❌ Выход", tray_menu)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)
    
    tray.setContextMenu(tray_menu)
    tray.show()
    
    # Двойной клик по трею — открыть последнее окно
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.DoubleClick:
            show_last_window()
    tray.activated.connect(on_tray_activated)
    
    # Переопределяем закрытие окна — сворачиваем в трей
    original_close = window.closeEvent
    def close_to_tray(event):
        if tray.isVisible():
            window.hide()
            # НЕ скрываем терминал — он работает независимо
            tray.showMessage(
                "Local Signals Pro",
                "Приложение работает в фоне. Кликните на иконку в трее.",
                QSystemTrayIcon.Information,
                2000
            )
            event.ignore()
        else:
            original_close(event)
    window.closeEvent = close_to_tray
    
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run()