"""
Премиальная 3D тема для Local Signals
Современный объемный дизайн с плавными анимациями и русским интерфейсом
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QFont

# 3D Премиальная тема с объемными элементами
PREMIUM_3D_QSS = """
/* Основные настройки - Красивый русский шрифт */
* { 
    font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif; 
    font-size: 14px;
    font-weight: 500;
}

QWidget { 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #0a0a0b, stop:0.3 #111113, stop:0.7 #0f0f11, stop:1 #0a0a0b);
    color: #ffffff; 
    border: none;
}

/* Главное окно - 3D градиент */
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #0a0a0b, stop:0.2 #1a1a1c, stop:0.5 #111113, stop:0.8 #1a1a1c, stop:1 #0a0a0b);
}

/* 3D Кнопки с объемом и тенями */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(0, 122, 255, 0.95), 
        stop:0.3 rgba(0, 140, 255, 0.85), 
        stop:0.7 rgba(0, 100, 220, 0.85),
        stop:1 rgba(0, 80, 200, 0.9));
    border: 3px solid rgba(255, 255, 255, 0.4);
    border-radius: 24px;
    padding: 20px 36px;
    font-weight: 800;
    font-size: 16px;
    color: #ffffff;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4), 
                0 6px 12px rgba(0, 122, 255, 0.3),
                inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(20, 140, 255, 1.0), 
        stop:0.3 rgba(0, 160, 255, 0.95), 
        stop:0.7 rgba(0, 120, 240, 0.95),
        stop:1 rgba(0, 100, 220, 1.0));
    border: 3px solid rgba(255, 255, 255, 0.6);
    transform: translateY(-4px);
    box-shadow: 0 16px 32px rgba(0, 0, 0, 0.5), 
                0 8px 16px rgba(0, 122, 255, 0.5),
                inset 0 3px 6px rgba(255, 255, 255, 0.3);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(0, 100, 200, 0.8), 
        stop:0.3 rgba(0, 122, 255, 0.7), 
        stop:0.7 rgba(0, 140, 255, 0.7),
        stop:1 rgba(0, 120, 240, 0.8));
    transform: translateY(2px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3), 
                0 3px 6px rgba(0, 122, 255, 0.2),
                inset 0 1px 2px rgba(0, 0, 0, 0.3);
}

QPushButton:disabled {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(100, 100, 100, 0.4), 
        stop:1 rgba(80, 80, 80, 0.3));
    color: rgba(255, 255, 255, 0.4);
    border: 3px solid rgba(255, 255, 255, 0.1);
    box-shadow: none;
    text-shadow: none;
}

/* Специальные кнопки */
QPushButton[class="success"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(48, 209, 88, 0.95), 
        stop:0.3 rgba(60, 220, 100, 0.85), 
        stop:0.7 rgba(40, 180, 70, 0.85),
        stop:1 rgba(30, 160, 60, 0.9));
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4), 
                0 6px 12px rgba(48, 209, 88, 0.4),
                inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

QPushButton[class="success"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(70, 230, 110, 1.0), 
        stop:0.3 rgba(48, 209, 88, 0.95), 
        stop:0.7 rgba(50, 190, 80, 0.95),
        stop:1 rgba(40, 170, 70, 1.0));
    box-shadow: 0 16px 32px rgba(0, 0, 0, 0.5), 
                0 8px 16px rgba(48, 209, 88, 0.6),
                inset 0 3px 6px rgba(255, 255, 255, 0.3);
}

QPushButton[class="danger"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 59, 48, 0.95), 
        stop:0.3 rgba(255, 80, 70, 0.85), 
        stop:0.7 rgba(220, 50, 40, 0.85),
        stop:1 rgba(200, 40, 30, 0.9));
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4), 
                0 6px 12px rgba(255, 59, 48, 0.4),
                inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

QPushButton[class="danger"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 90, 80, 1.0), 
        stop:0.3 rgba(255, 59, 48, 0.95), 
        stop:0.7 rgba(240, 60, 50, 0.95),
        stop:1 rgba(220, 50, 40, 1.0));
    box-shadow: 0 16px 32px rgba(0, 0, 0, 0.5), 
                0 8px 16px rgba(255, 59, 48, 0.6),
                inset 0 3px 6px rgba(255, 255, 255, 0.3);
}

QPushButton[class="secondary"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.18), 
        stop:0.3 rgba(255, 255, 255, 0.12), 
        stop:0.7 rgba(200, 200, 200, 0.10),
        stop:1 rgba(180, 180, 180, 0.12));
    border: 3px solid rgba(255, 255, 255, 0.4);
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3), 
                inset 0 2px 4px rgba(255, 255, 255, 0.15);
}

QPushButton[class="secondary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.28), 
        stop:0.3 rgba(255, 255, 255, 0.20), 
        stop:0.7 rgba(220, 220, 220, 0.18),
        stop:1 rgba(200, 200, 200, 0.20));
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4), 
                0 6px 12px rgba(255, 255, 255, 0.2),
                inset 0 3px 6px rgba(255, 255, 255, 0.2);
}

QPushButton[class="ghost"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.12), 
        stop:1 rgba(255, 255, 255, 0.06));
    border: 2px solid rgba(255, 255, 255, 0.5);
    border-radius: 20px;
    padding: 16px 24px;
    font-size: 14px;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2),
                inset 0 1px 2px rgba(255, 255, 255, 0.1);
}

QPushButton[class="ghost"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.22), 
        stop:1 rgba(255, 255, 255, 0.12));
    border: 2px solid rgba(255, 255, 255, 0.7);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3), 
                0 4px 8px rgba(255, 255, 255, 0.15),
                inset 0 2px 4px rgba(255, 255, 255, 0.15);
}

/* 3D Поля ввода с глубиной */
QLineEdit, QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.15), 
        stop:0.3 rgba(255, 255, 255, 0.08), 
        stop:0.7 rgba(255, 255, 255, 0.06),
        stop:1 rgba(255, 255, 255, 0.10));
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-radius: 22px;
    padding: 20px 24px;
    font-size: 16px;
    color: #ffffff;
    font-weight: 600;
    box-shadow: inset 0 4px 8px rgba(0, 0, 0, 0.3),
                0 2px 4px rgba(255, 255, 255, 0.1);
}

QLineEdit:focus, QPlainTextEdit:focus {
    border: 4px solid rgba(0, 122, 255, 0.9);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.22), 
        stop:0.3 rgba(255, 255, 255, 0.15), 
        stop:0.7 rgba(255, 255, 255, 0.12),
        stop:1 rgba(255, 255, 255, 0.18));
    box-shadow: inset 0 4px 8px rgba(0, 0, 0, 0.3), 
                0 0 16px rgba(0, 122, 255, 0.4),
                0 4px 8px rgba(255, 255, 255, 0.15);
}

/* 3D Комбобоксы */
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.15), 
        stop:0.3 rgba(255, 255, 255, 0.08), 
        stop:0.7 rgba(255, 255, 255, 0.06),
        stop:1 rgba(255, 255, 255, 0.10));
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-radius: 22px;
    padding: 20px 24px;
    font-size: 16px;
    color: #ffffff;
    font-weight: 600;
    min-width: 160px;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2),
                inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

QComboBox:hover {
    border: 3px solid rgba(255, 255, 255, 0.5);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.22), 
        stop:0.3 rgba(255, 255, 255, 0.15), 
        stop:0.7 rgba(255, 255, 255, 0.12),
        stop:1 rgba(255, 255, 255, 0.18));
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3),
                inset 0 3px 6px rgba(255, 255, 255, 0.15);
}

QComboBox::drop-down {
    border: none;
    width: 50px;
    border-radius: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 8px solid transparent;
    border-right: 8px solid transparent;
    border-top: 10px solid rgba(255, 255, 255, 0.9);
    margin-right: 18px;
}

QComboBox QAbstractItemView {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(20, 20, 22, 0.98), 
        stop:0.5 rgba(25, 25, 27, 0.95),
        stop:1 rgba(15, 15, 17, 0.98));
    border: 3px solid rgba(255, 255, 255, 0.4);
    border-radius: 22px;
    selection-background-color: rgba(0, 122, 255, 0.5);
    padding: 16px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
}

/* 3D Группы с объемом */
QGroupBox {
    font-weight: 900;
    font-size: 20px;
    color: #ffffff;
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-radius: 28px;
    margin-top: 20px;
    padding-top: 24px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.12), 
        stop:0.3 rgba(255, 255, 255, 0.06), 
        stop:0.7 rgba(255, 255, 255, 0.04),
        stop:1 rgba(255, 255, 255, 0.08));
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3),
                inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 28px;
    padding: 0 16px 0 16px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #0a0a0b, stop:0.5 #1a1a1c, stop:1 #111113);
    border-radius: 12px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
}

/* 3D Чекбоксы */
QCheckBox {
    font-size: 16px;
    color: #ffffff;
    font-weight: 700;
    spacing: 16px;
}

QCheckBox::indicator {
    width: 28px;
    height: 28px;
    border-radius: 10px;
    border: 4px solid rgba(255, 255, 255, 0.5);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.10), 
        stop:0.5 rgba(255, 255, 255, 0.05),
        stop:1 rgba(255, 255, 255, 0.08));
    box-shadow: inset 0 3px 6px rgba(0, 0, 0, 0.3),
                0 2px 4px rgba(255, 255, 255, 0.1);
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(0, 122, 255, 1.0), 
        stop:0.3 rgba(0, 140, 255, 0.9), 
        stop:0.7 rgba(0, 100, 220, 0.9),
        stop:1 rgba(0, 80, 200, 1.0));
    border: 4px solid rgba(0, 122, 255, 0.9);
    box-shadow: 0 0 16px rgba(0, 122, 255, 0.6),
                inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

/* 3D Таблицы */
QTableWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.10), 
        stop:0.3 rgba(255, 255, 255, 0.06), 
        stop:0.7 rgba(255, 255, 255, 0.04),
        stop:1 rgba(255, 255, 255, 0.08));
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-radius: 28px;
    gridline-color: rgba(255, 255, 255, 0.15);
    font-size: 15px;
    font-weight: 600;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3),
                inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

QTableWidget::item {
    padding: 20px 16px;
    border-bottom: 2px solid rgba(255, 255, 255, 0.1);
}

QTableWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(0, 122, 255, 0.4), 
        stop:0.5 rgba(0, 122, 255, 0.25),
        stop:1 rgba(0, 122, 255, 0.3));
    box-shadow: inset 0 2px 4px rgba(0, 122, 255, 0.3);
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.20), 
        stop:0.3 rgba(255, 255, 255, 0.12), 
        stop:0.7 rgba(255, 255, 255, 0.08),
        stop:1 rgba(255, 255, 255, 0.15));
    border: none;
    border-bottom: 4px solid rgba(255, 255, 255, 0.3);
    padding: 20px 16px;
    font-weight: 900;
    font-size: 15px;
    color: rgba(255, 255, 255, 0.95);
    box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

/* 3D Табы */
QTabWidget::pane {
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-radius: 28px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.08), 
        stop:0.5 rgba(255, 255, 255, 0.04),
        stop:1 rgba(255, 255, 255, 0.06));
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.2),
                inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.15), 
        stop:0.3 rgba(255, 255, 255, 0.08), 
        stop:0.7 rgba(255, 255, 255, 0.06),
        stop:1 rgba(255, 255, 255, 0.10));
    border: 3px solid rgba(255, 255, 255, 0.3);
    padding: 20px 40px;
    margin-right: 8px;
    border-top-left-radius: 22px;
    border-top-right-radius: 22px;
    font-weight: 800;
    font-size: 16px;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2),
                inset 0 2px 4px rgba(255, 255, 255, 0.1);
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(0, 122, 255, 0.5), 
        stop:0.3 rgba(0, 122, 255, 0.3), 
        stop:0.7 rgba(0, 122, 255, 0.25),
        stop:1 rgba(0, 122, 255, 0.4));
    border-bottom: 6px solid rgba(0, 122, 255, 1.0);
    box-shadow: 0 0 20px rgba(0, 122, 255, 0.4),
                inset 0 3px 6px rgba(255, 255, 255, 0.15);
}

QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.22), 
        stop:0.3 rgba(255, 255, 255, 0.15), 
        stop:0.7 rgba(255, 255, 255, 0.12),
        stop:1 rgba(255, 255, 255, 0.18));
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3),
                inset 0 3px 6px rgba(255, 255, 255, 0.15);
}

/* Анимированный прогресс-бар БЕЗ процентов */
QProgressBar {
    border: 3px solid rgba(255, 255, 255, 0.4);
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(255, 255, 255, 0.12), 
        stop:0.5 rgba(255, 255, 255, 0.06),
        stop:1 rgba(255, 255, 255, 0.08));
    text-align: center;
    font-weight: 800;
    color: transparent; /* УБИРАЕМ ПРОЦЕНТЫ */
    height: 32px;
    box-shadow: inset 0 4px 8px rgba(0, 0, 0, 0.3),
                0 2px 4px rgba(255, 255, 255, 0.1);
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 rgba(0, 122, 255, 0.95), 
        stop:0.2 rgba(0, 160, 255, 1.0),
        stop:0.4 rgba(0, 140, 255, 1.0),
        stop:0.6 rgba(0, 180, 255, 1.0),
        stop:0.8 rgba(0, 100, 255, 1.0),
        stop:1 rgba(0, 122, 255, 0.95));
    border-radius: 12px;
    margin: 3px;
    box-shadow: 0 0 16px rgba(0, 122, 255, 0.6),
                inset 0 2px 4px rgba(255, 255, 255, 0.3);
}

/* 3D Скроллбары */
QScrollBar:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 rgba(255, 255, 255, 0.10), 
        stop:0.5 rgba(255, 255, 255, 0.06),
        stop:1 rgba(255, 255, 255, 0.08));
    width: 20px;
    border-radius: 10px;
    margin: 0;
    box-shadow: inset 0 0 6px rgba(0, 0, 0, 0.3);
}

QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 rgba(255, 255, 255, 0.4), 
        stop:0.3 rgba(255, 255, 255, 0.3), 
        stop:0.7 rgba(255, 255, 255, 0.25),
        stop:1 rgba(255, 255, 255, 0.35));
    border-radius: 10px;
    min-height: 50px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3),
                inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 rgba(255, 255, 255, 0.5), 
        stop:0.3 rgba(255, 255, 255, 0.4), 
        stop:0.7 rgba(255, 255, 255, 0.35),
        stop:1 rgba(255, 255, 255, 0.45));
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4),
                inset 0 3px 6px rgba(255, 255, 255, 0.3);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* 3D Тултипы */
QToolTip {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(20, 20, 22, 0.98), 
        stop:0.5 rgba(30, 30, 32, 0.95),
        stop:1 rgba(15, 15, 17, 0.98));
    border: 3px solid rgba(255, 255, 255, 0.4);
    border-radius: 16px;
    padding: 16px 20px;
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.5);
}

/* Лейблы */
QLabel {
    color: #ffffff;
    font-size: 15px;
    font-weight: 600;
}
"""

class AnimatedProgressBar:
    """Анимированный прогресс-бар без процентов"""
    def __init__(self, progress_bar):
        self.progress_bar = progress_bar
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.animation_step = 0
        
    def start_animation(self):
        """Запуск анимации"""
        self.timer.start(100)  # Обновление каждые 100мс
        
    def stop_animation(self):
        """Остановка анимации"""
        self.timer.stop()
        
    def animate(self):
        """Анимация прогресса"""
        self.animation_step += 1
        # Создаем эффект "летящего" прогресса
        value = (self.animation_step * 3) % 100
        self.progress_bar.setValue(value)

def apply_theme(app: QApplication) -> None:
    """Применение 3D темы"""
    app.setStyle("Fusion")
    app.setStyleSheet(PREMIUM_3D_QSS)
    
    # Устанавливаем красивый русский шрифт
    font = QFont("Segoe UI", 14, QFont.Weight.Medium)
    app.setFont(font)

def create_animated_progress():
    """Создание анимированного прогресс-бара"""
    from PySide6.QtWidgets import QProgressBar
    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setTextVisible(False)  # Убираем текст с процентами
    return progress, AnimatedProgressBar(progress)