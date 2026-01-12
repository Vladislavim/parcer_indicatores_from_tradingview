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

# Цветовая палитра
COLORS = {
    "bg_dark": "#0D0D0F",
    "bg_card": "#16161A", 
    "bg_hover": "#1E1E24",
    "accent": "#6C5CE7",
    "accent_light": "#A29BFE",
    "accent2": "#00CEC9",
    "accent3": "#FD79A8",
    "success": "#00D9A5",
    "danger": "#FF6B6B",
    "warning": "#FDCB6E",
    "text": "#FFFFFF",
    "text_muted": "#72727E",
    "border": "#2D2D35",
}

# Стиль для лейблов без обводки
LABEL_STYLE = f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent; border: none;"


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
        
        # Градиентный фон
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor(13, 13, 15))
        bg.setColorAt(0.5, QColor(18, 18, 22))
        bg.setColorAt(1, QColor(13, 13, 15))
        painter.fillRect(self.rect(), bg)
        
        # Орбы
        for orb in self.orbs:
            cx, cy = int(orb['x'] * w), int(orb['y'] * h)
            pulse = 1 + 0.3 * math.sin(self.time * orb['pulse_speed'] * 50 + orb['phase'])
            radius = int(orb['radius'] * pulse)
            
            gradient = QRadialGradient(cx, cy, radius)
            r, g, b, a = orb['color']
            gradient.setColorAt(0, QColor(r, g, b, a))
            gradient.setColorAt(0.4, QColor(r, g, b, int(a * 0.5)))
            gradient.setColorAt(0.7, QColor(r, g, b, int(a * 0.2)))
            gradient.setColorAt(1, QColor(r, g, b, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        
        # Частицы
        for p in self.particles:
            px, py = int(p['x'] * w), int(p['y'] * h)
            painter.setBrush(QColor(255, 255, 255, int(255 * p['alpha'] * (0.5 + 0.5 * math.sin(self.time * 2)))))
            painter.drawEllipse(px, py, int(p['size']), int(p['size']))
        
        # Виньетка
        vignette = QRadialGradient(w/2, h/2, max(w, h) * 0.8)
        vignette.setColorAt(0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.7, QColor(0, 0, 0, 30))
        vignette.setColorAt(1, QColor(0, 0, 0, 120))
        painter.setBrush(vignette)
        painter.drawRect(self.rect())


class AnimatedCard(QFrame):
    """Карточка с анимацией появления и hover эффектами"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._hovered = False
        
    def _setup_style(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(22, 22, 26, 0.9), 
                    stop:1 rgba(18, 18, 22, 0.95));
                border: 1px solid rgba(45, 45, 53, 0.5);
                border-radius: 24px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 15)
        self.setGraphicsEffect(shadow)
        
    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 30, 36, 0.95), 
                    stop:1 rgba(22, 22, 26, 0.98));
                border: 1px solid rgba(108, 92, 231, 0.5);
                border-radius: 24px;
            }}
        """)
        
    def leaveEvent(self, event):
        self._hovered = False
        self._setup_style()
        
    def fade_in(self, duration=300):
        """Плавное появление"""
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._fade_anim = anim


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
                background: transparent;
                border: none;
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
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(30, 30, 36, 0.4);
                border: none;
                border-radius: 12px;
            }}
        """)
        
    def leaveEvent(self, event):
        self._update_card_style()
        
    def _update_card_style(self):
        if self.status == "bull":
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0, 217, 165, 0.06);
                    border: none;
                    border-radius: 12px;
                }}
            """)
        elif self.status == "bear":
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(255, 107, 107, 0.06);
                    border: none;
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
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


class SmallButton(QPushButton):
    """Маленькая кнопка"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
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


class BigButton(QPushButton):
    """Большая кнопка с анимацией"""
    
    def __init__(self, text: str, color: str = "accent", parent=None):
        super().__init__(text, parent)
        self.color = COLORS.get(color, COLORS["accent"])
        self.setMinimumHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_style()
        
    def _setup_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.color}, stop:1 {COLORS["accent_light"]});
                border: none;
                border-radius: 14px;
                color: white;
                font-size: 15px;
                font-weight: 700;
                padding: 14px 28px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS["accent_light"]}, stop:1 {self.color});
            }}
            QPushButton:disabled {{
                background: {COLORS["bg_hover"]};
                color: {COLORS["text_muted"]};
            }}
        """)


class ModernInput(QLineEdit):
    """Современное поле ввода"""
    
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(48)
        self.setStyleSheet(f"""
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
        """)


class ModernCombo(QComboBox):
    """Современный комбобокс"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)
        self.setStyleSheet(f"""
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
            }}
        """)


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
        
        self.settings = QSettings("LocalSignals", "Pro")
        self.worker: Optional[Worker] = None
        self.cards: Dict[str, SignalCard] = {}
        self.chart_windows: List[ChartWindow] = []
        
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
        left = self._create_left_panel()
        layout.addWidget(left, 1)
        
        # Правая панель
        right = self._create_right_panel()
        layout.addWidget(right, 2)
        
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
        title = QLabel("⚙️ Настройки")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        layout.addWidget(title)
        
        # Биржа
        lbl_exchange = QLabel("Биржа")
        lbl_exchange.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl_exchange)
        self.exchange = ModernCombo()
        self.exchange.addItem("Bybit Фьючерсы", "BYBIT_PERP")
        self.exchange.addItem("Binance Спот", "BINANCE_SPOT")
        layout.addWidget(self.exchange)
        
        # Таймфрейм
        lbl_tf = QLabel("Таймфрейм")
        lbl_tf.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl_tf)
        self.tf = ModernCombo()
        for k, v in [("1m", "1 мин"), ("5m", "5 мин"), ("15m", "15 мин"), ("1h", "1 час"), ("4h", "4 часа"), ("1d", "1 день")]:
            self.tf.addItem(v, k)
        self.tf.setCurrentIndex(3)
        layout.addWidget(self.tf)
        
        # Telegram
        lbl_tg = QLabel("Telegram")
        lbl_tg.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl_tg)
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
        
        return panel

        
    def _create_right_panel(self):
        panel = AnimatedCard()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Заголовок
        header = QHBoxLayout()
        title = QLabel("📊 Сигналы")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        header.addWidget(title)
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
            
    def _open_chart(self, symbol: str):
        """Открыть график в отдельном окне"""
        chart = ChartWindow(symbol)
        chart.show()
        self.chart_windows.append(chart)
        
    def _get_selected_coins(self) -> List[str]:
        """Получить текущий список выбранных монет (для горячего обновления)"""
        return [s for s, cb in self.coin_cbs.items() if cb.isChecked()]

        
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
    
    # Шрифт
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run()