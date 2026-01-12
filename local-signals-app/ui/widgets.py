"""
Дополнительные виджеты для улучшения UX
"""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt, QTimer, pyqtSignal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, 
    QFrame, QProgressBar, QGraphicsDropShadowEffect
)

class AnimatedStatusCard(QFrame):
    """Анимированная карточка статуса с эффектами"""
    
    def __init__(self, title: str, value: str = "—", status: str = "na"):
        super().__init__()
        self.current_status = status
        self.setup_ui(title, value)
        self.setup_animation()
        
    def setup_ui(self, title: str, value: str):
        self.setFrameStyle(QFrame.Box)
        self.setFixedSize(140, 80)
        
        # Добавляем тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #94a3b8; font-size: 9pt; font-weight: 600;")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 18pt; font-weight: 700;")
        self.value_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label, 1)
        
        self.update_status(self.current_status)
        
    def setup_animation(self):
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.pulse_effect)
        self.pulse_opacity = 1.0
        self.pulse_direction = -1
        
    def update_status(self, status: str, value: str = None):
        if value:
            self.value_label.setText(value)
            
        self.current_status = status
        
        # Цвета для разных статусов
        colors = {
            "bull": "#10b981",
            "bear": "#ef4444", 
            "neutral": "#94a3b8",
            "na": "#64748b",
            "warning": "#f59e0b"
        }
        
        color = colors.get(status, colors["na"])
        
        # Обновляем стили
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #1e293b, stop:1 #0f172a);
                border: 2px solid {color};
                border-radius: 12px;
            }}
        """)
        
        self.value_label.setStyleSheet(f"color: {color}; font-size: 18pt; font-weight: 700;")
        
        # Запускаем пульсацию для активных статусов
        if status in ["bull", "bear"]:
            self.pulse_timer.start(100)
        else:
            self.pulse_timer.stop()
            
    def pulse_effect(self):
        """Эффект пульсации для активных статусов"""
        self.pulse_opacity += self.pulse_direction * 0.05
        
        if self.pulse_opacity <= 0.7:
            self.pulse_direction = 1
        elif self.pulse_opacity >= 1.0:
            self.pulse_direction = -1
            
        self.setWindowOpacity(self.pulse_opacity)

class TradingSignalWidget(QWidget):
    """Виджет для отображения торгового сигнала"""
    
    def __init__(self, symbol: str, signal_type: str, price: float, timestamp: str):
        super().__init__()
        self.setup_ui(symbol, signal_type, price, timestamp)
        
    def setup_ui(self, symbol: str, signal_type: str, price: float, timestamp: str):
        self.setFixedHeight(60)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid #334155;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Эмодзи для типа сигнала
        emoji_map = {
            "BUY": "🟢",
            "SELL": "🔴",
            "INFO": "ℹ️"
        }
        
        emoji_label = QLabel(emoji_map.get(signal_type, "📊"))
        emoji_label.setStyleSheet("font-size: 20pt;")
        
        # Информация о сигнале
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        symbol_label = QLabel(symbol)
        symbol_label.setStyleSheet("font-size: 12pt; font-weight: 700; color: #e2e8f0;")
        
        details_label = QLabel(f"{signal_type} @ ${price:.4f}")
        details_label.setStyleSheet("font-size: 10pt; color: #94a3b8;")
        
        info_layout.addWidget(symbol_label)
        info_layout.addWidget(details_label)
        
        # Время
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("font-size: 9pt; color: #64748b;")
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(emoji_label)
        layout.addLayout(info_layout, 1)
        layout.addWidget(time_label)

class ModernProgressBar(QProgressBar):
    """Современный прогресс-бар с анимацией"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_animation()
        
    def setup_ui(self):
        self.setFixedHeight(6)
        self.setTextVisible(False)
        self.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: #1e293b;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:0.5 #60a5fa, stop:1 #3b82f6);
                border-radius: 3px;
            }
        """)
        
    def setup_animation(self):
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_progress)
        self.animation_value = 0
        self.animation_direction = 1
        
    def start_animation(self):
        """Запустить анимацию загрузки"""
        self.setRange(0, 100)
        self.animation_timer.start(50)
        
    def stop_animation(self):
        """Остановить анимацию"""
        self.animation_timer.stop()
        self.setValue(0)
        
    def animate_progress(self):
        """Анимация прогресса"""
        self.animation_value += self.animation_direction * 2
        
        if self.animation_value >= 100:
            self.animation_direction = -1
        elif self.animation_value <= 0:
            self.animation_direction = 1
            
        self.setValue(self.animation_value)

class NotificationToast(QWidget):
    """Всплывающее уведомление"""
    
    def __init__(self, message: str, notification_type: str = "info"):
        super().__init__()
        self.setup_ui(message, notification_type)
        self.setup_animation()
        
    def setup_ui(self, message: str, notification_type: str):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 80)
        
        # Цвета для разных типов
        colors = {
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b", 
            "info": "#3b82f6"
        }
        
        color = colors.get(notification_type, colors["info"])
        
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #1e293b, stop:1 #0f172a);
                border: 2px solid {color};
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Эмодзи для типа
        emoji_map = {
            "success": "✅",
            "error": "❌", 
            "warning": "⚠️",
            "info": "ℹ️"
        }
        
        emoji_label = QLabel(emoji_map.get(notification_type, "ℹ️"))
        emoji_label.setStyleSheet("font-size: 20pt;")
        
        message_label = QLabel(message)
        message_label.setStyleSheet("color: #e2e8f0; font-size: 11pt; font-weight: 600;")
        message_label.setWordWrap(True)
        
        layout.addWidget(emoji_label)
        layout.addWidget(message_label, 1)
        
    def setup_animation(self):
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.fade_out)
        self.opacity = 1.0
        
        # Автоматически скрываем через 3 секунды
        QTimer.singleShot(3000, self.start_fade)
        
    def start_fade(self):
        """Начать исчезновение"""
        self.fade_timer.start(50)
        
    def fade_out(self):
        """Плавное исчезновение"""
        self.opacity -= 0.05
        self.setWindowOpacity(self.opacity)
        
        if self.opacity <= 0:
            self.fade_timer.stop()
            self.close()
            
    def show_notification(self, parent_widget: QWidget):
        """Показать уведомление относительно родительского виджета"""
        if parent_widget:
            parent_rect = parent_widget.geometry()
            x = parent_rect.right() - self.width() - 20
            y = parent_rect.top() + 20
            self.move(x, y)
        
        self.show()
        self.raise_()