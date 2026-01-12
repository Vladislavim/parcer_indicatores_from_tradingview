from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSettings, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QComboBox, QLineEdit, QPlainTextEdit, QPushButton,
    QMessageBox, QSplitter, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QFrame, QScrollArea, QProgressBar, QTabWidget
)

from core.worker import Worker
from ui.chart_window import ChartWindow

THREAD_ID_DEV = 5
DEFAULT_CHAT_ID = "-1003065825691"

# Все монеты, которые мониторим всегда (Bybit perp)
MONITOR_SYMBOLS: List[str] = [
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "FARTCOINUSDT.P", "ZECUSDT.P",
    "XRPUSDT.P", "1000PEPEUSDT.P", "RIVERUSDT.P", "HYPEUSDT.P", "SUIUSDT.P",
    "WIFUSDT.P", "DOGEUSDT.P", "ADAUSDT.P", "PIPPINUSDT.P", "LTCUSDT.P",
    "LINKUSDT.P", "ENAUSDT.P", "ZKPUSDT.P", "AVAXUSDT.P", "AAVEUSDT.P",
]

@dataclass(frozen=True)
class IndicatorSpec:
    key: str
    title: str
    description: str
    emoji: str

STATUS_COLOR = {
    "bull": QColor("#30D158"),
    "bear": QColor("#FF3B30"),
    "neutral": QColor("rgba(255, 255, 255, 0.4)"),
    "na": QColor("rgba(255, 255, 255, 0.2)"),
}

class PremiumStatusCard(QFrame):
    """Премиальная карточка статуса"""
    def __init__(self, title: str, value: str = "—", status: str = "na"):
        super().__init__()
        self.setFixedSize(160, 100)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.08), stop:1 rgba(255, 255, 255, 0.03));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 20px;
            }
            QFrame:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.12), stop:1 rgba(255, 255, 255, 0.06));
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 16, 20, 16)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 24px; font-weight: 800;")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.update_status(status)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label, 1)
        
    def update_status(self, status: str, value: str = None):
        if value:
            self.value_label.setText(value)
        color = STATUS_COLOR.get(status, STATUS_COLOR["na"])
        self.value_label.setStyleSheet(f"color: {color.name()}; font-size: 24px; font-weight: 800;")

class PremiumCoinSelector(QWidget):
    """Премиальный селектор монет"""
    def __init__(self):
        super().__init__()
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Заголовок с кнопками управления
        header = QHBoxLayout()
        title = QLabel("💰 Alert Coins Selection")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        
        # Кнопки быстрого выбора
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        select_top = QPushButton("Top 5")
        select_top.setProperty("class", "ghost")
        select_top.clicked.connect(self.select_top)
        
        select_all = QPushButton("All")
        select_all.setProperty("class", "ghost")
        select_all.clicked.connect(self.select_all)
        
        select_none = QPushButton("None")
        select_none.setProperty("class", "ghost")
        select_none.clicked.connect(self.select_none)
        
        button_layout.addWidget(select_top)
        button_layout.addWidget(select_all)
        button_layout.addWidget(select_none)
        
        header.addWidget(title)
        header.addStretch()
        header.addLayout(button_layout)
        
        layout.addLayout(header)