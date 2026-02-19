"""
Общие стили и компоненты для приложения
"""
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QLineEdit, QComboBox, QPushButton,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QVBoxLayout
)

# Цветовые палитры
DARK_THEME = {
    "bg_dark": "#0D0D0F",
    "bg_card": "#16161A", 
    "bg_hover": "#1E1E24",
    "bg_secondary": "#1A1A1E",
    "accent": "#6C5CE7",
    "accent_light": "#A29BFE",
    "accent2": "#00CEC9",
    "accent3": "#FD79A8",
    "success": "#00D9A5",
    "danger": "#FF6B6B",
    "warning": "#FDCB6E",
    "text": "#FFFFFF",
    "text_secondary": "#B0B0B8",
    "text_muted": "#72727E",
    "border": "#2D2D35",
}

LIGHT_THEME = {
    "bg_dark": "#F5F5F7",
    "bg_card": "#FFFFFF",
    "bg_secondary": "#F8F8FA", 
    "bg_hover": "#E8E8ED",
    "accent": "#6C5CE7",
    "accent_light": "#A29BFE",
    "accent2": "#00CEC9",
    "accent3": "#FD79A8",
    "success": "#00B894",
    "danger": "#E74C3C",
    "warning": "#F39C12",
    "text": "#1A1A2E",
    "text_secondary": "#4A4A5E",
    "text_muted": "#6B6B7B",
    "border": "#D1D1D6",
}

# Текущая тема (по умолчанию тёмная)
COLORS = DARK_THEME.copy()
_current_theme = "dark"

def set_theme(theme: str):
    """Переключить тему: 'dark' или 'light'"""
    global COLORS, _current_theme
    _current_theme = theme
    if theme == "light":
        COLORS.update(LIGHT_THEME)
    else:
        COLORS.update(DARK_THEME)

def get_current_theme() -> str:
    return _current_theme

def get_label_style():
    return f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent; border: none;"


class AnimatedCard(QFrame):
    """Карточка с анимацией появления и hover эффектами"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._hovered = False
        
    def _setup_style(self):
        is_light = get_current_theme() == "light"
        if is_light:
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 255, 255, 0.95), 
                        stop:1 rgba(248, 248, 250, 0.98));
                    border: 1px solid rgba(209, 209, 214, 0.5);
                    border-radius: 24px;
                }}
            """)
        else:
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
        shadow.setColor(QColor(0, 0, 0, 60 if is_light else 100))
        shadow.setOffset(0, 15)
        self.setGraphicsEffect(shadow)
        
    def enterEvent(self, event):
        self._hovered = True
        is_light = get_current_theme() == "light"
        if is_light:
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(248, 248, 252, 0.98), 
                        stop:1 rgba(240, 240, 245, 0.99));
                    border: 1px solid rgba(108, 92, 231, 0.5);
                    border-radius: 24px;
                }}
            """)
        else:
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
        
    def update_theme(self):
        """Обновить стиль при смене темы"""
        self._setup_style()


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
