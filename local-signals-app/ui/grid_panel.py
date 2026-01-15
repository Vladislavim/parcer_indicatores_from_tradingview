"""
Панель управления Grid Trading ботом
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QWidget, QGridLayout,
    QRadioButton, QButtonGroup, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer

# Цвета
COLORS = {
    'bg': '#0f0f14',
    'bg_card': '#1a1a22',
    'border': '#2a2a35',
    'accent': '#6C5CE7',
    'accent_light': '#8B7CF7',
    'green': '#00D9A5',
    'red': '#FF6B6B',
    'orange': '#FFA500',
    'text': '#ffffff',
    'text_dim': '#888888',
}


class GridPanel(QFrame):
    """Панель Grid Trading бота"""
    start_clicked = Signal(dict)  # config
    stop_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame#GridPanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("GridPanel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("📊 Grid Bot")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        
        self.status_lbl = QLabel("⚪ Выкл")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        header.addWidget(self.status_lbl)
        layout.addLayout(header)
        
        # Info
        info = QLabel("Сеточная торговля — зарабатывает на колебаниях цены в диапазоне")
        info.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Mode selection
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Режим:")
        mode_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        mode_row.addWidget(mode_lbl)
        
        self.mode_group = QButtonGroup()
        
        self.ai_radio = QRadioButton("🤖 AI")
        self.ai_radio.setChecked(True)
        self.ai_radio.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        self.ai_radio.toggled.connect(self._on_mode_changed)
        self.mode_group.addButton(self.ai_radio)
        mode_row.addWidget(self.ai_radio)
        
        self.manual_radio = QRadioButton("✋ Ручной")
        self.manual_radio.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        self.mode_group.addButton(self.manual_radio)
        mode_row.addWidget(self.manual_radio)
        
        mode_row.addStretch()
        layout.addLayout(mode_row)
        
        # Symbol
        symbol_row = QHBoxLayout()
        symbol_lbl = QLabel("Монета:")
        symbol_lbl.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        symbol_row.addWidget(symbol_lbl)
        
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
        self.symbol_combo.setFixedWidth(140)
        self.symbol_combo.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 11px;
            }}
        """)
        symbol_row.addWidget(self.symbol_combo)
        symbol_row.addStretch()
        layout.addLayout(symbol_row)
        
        # Manual settings (скрыты по умолчанию)
        self.manual_settings = QWidget()
        self.manual_settings.setStyleSheet("background: transparent;")
        manual_layout = QGridLayout(self.manual_settings)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)
        
        # Upper price
        manual_layout.addWidget(self._label("Верхняя цена:"), 0, 0)
        self.upper_price = QDoubleSpinBox()
        self.upper_price.setRange(0, 1000000)
        self.upper_price.setValue(100000)
        self.upper_price.setPrefix("$")
        self.upper_price.setStyleSheet(self._spin_style())
        manual_layout.addWidget(self.upper_price, 0, 1)
        
        # Lower price
        manual_layout.addWidget(self._label("Нижняя цена:"), 1, 0)
        self.lower_price = QDoubleSpinBox()
        self.lower_price.setRange(0, 1000000)
        self.lower_price.setValue(90000)
        self.lower_price.setPrefix("$")
        self.lower_price.setStyleSheet(self._spin_style())
        manual_layout.addWidget(self.lower_price, 1, 1)
        
        # Grid count
        manual_layout.addWidget(self._label("Кол-во сеток:"), 2, 0)
        self.grid_count = QSpinBox()
        self.grid_count.setRange(3, 50)
        self.grid_count.setValue(10)
        self.grid_count.setStyleSheet(self._spin_style())
        manual_layout.addWidget(self.grid_count, 2, 1)
        
        self.manual_settings.setVisible(False)
        layout.addWidget(self.manual_settings)
        
        # AI info
        self.ai_info = QLabel("🤖 AI автоматически определит:\n• Диапазон цены по волатильности\n• Оптимальное количество сеток")
        self.ai_info.setStyleSheet("font-size: 10px; color: #6C5CE7; background: #1a1a22; padding: 8px; border-radius: 6px;")
        self.ai_info.setWordWrap(True)
        layout.addWidget(self.ai_info)
        
        # Investment
        inv_row = QHBoxLayout()
        inv_row.addWidget(self._label("Инвестиция:"))
        self.investment = QDoubleSpinBox()
        self.investment.setRange(10, 100000)
        self.investment.setValue(500)
        self.investment.setPrefix("$")
        self.investment.setStyleSheet(self._spin_style())
        inv_row.addWidget(self.investment)
        
        inv_row.addWidget(self._label("Плечо:"))
        self.leverage = QSpinBox()
        self.leverage.setRange(1, 20)
        self.leverage.setValue(1)
        self.leverage.setSuffix("x")
        self.leverage.setStyleSheet(self._spin_style())
        inv_row.addWidget(self.leverage)
        inv_row.addStretch()
        layout.addLayout(inv_row)
        
        # Stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #1a1a22; border-radius: 6px;")
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        stats_layout.setSpacing(6)
        
        stats_layout.addWidget(self._label("Профит:"), 0, 0)
        self.profit_lbl = QLabel("$0.00")
        self.profit_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['green']}; background: transparent;")
        stats_layout.addWidget(self.profit_lbl, 0, 1)
        
        stats_layout.addWidget(self._label("Сделок:"), 0, 2)
        self.trades_lbl = QLabel("0")
        self.trades_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: white; background: transparent;")
        stats_layout.addWidget(self.trades_lbl, 0, 3)
        
        stats_layout.addWidget(self._label("Ордеров:"), 1, 0)
        self.orders_lbl = QLabel("0")
        self.orders_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        stats_layout.addWidget(self.orders_lbl, 1, 1)
        
        stats_layout.addWidget(self._label("Сеток:"), 1, 2)
        self.grids_lbl = QLabel("0")
        self.grids_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        stats_layout.addWidget(self.grids_lbl, 1, 3)
        
        layout.addWidget(stats_frame)
        
        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        
        self.start_btn = QPushButton("▶ Запустить Grid")
        self.start_btn.setFixedHeight(42)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #00EEB5; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.setFixedHeight(42)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['red']};
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #FF8888; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)
        
        layout.addLayout(btn_row)
        
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 11px; color: #888; background: transparent;")
        return lbl
        
    def _spin_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 11px;
                min-width: 80px;
            }
        """
        
    def _on_mode_changed(self, checked: bool):
        """Переключение режима AI/Manual"""
        is_ai = self.ai_radio.isChecked()
        self.manual_settings.setVisible(not is_ai)
        self.ai_info.setVisible(is_ai)
        
    def _on_start(self):
        """Запуск бота"""
        config = {
            "symbol": self.symbol_combo.currentText(),
            "mode": "ai" if self.ai_radio.isChecked() else "manual",
            "upper_price": self.upper_price.value(),
            "lower_price": self.lower_price.value(),
            "grid_count": self.grid_count.value(),
            "investment": self.investment.value(),
            "leverage": self.leverage.value(),
        }
        self.start_clicked.emit(config)
        
    def _on_stop(self):
        """Остановка бота"""
        self.stop_clicked.emit()
        
    def set_running(self, running: bool):
        """Установить статус работы"""
        if running:
            self.status_lbl.setText("🟢 Работает")
            self.status_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['green']}; background: transparent;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_lbl.setText("⚪ Выкл")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
    def update_stats(self, profit: float, trades: int, orders: int, grids: int):
        """Обновить статистику"""
        color = COLORS['green'] if profit >= 0 else COLORS['red']
        self.profit_lbl.setText(f"${profit:,.2f}")
        self.profit_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color}; background: transparent;")
        self.trades_lbl.setText(str(trades))
        self.orders_lbl.setText(str(orders))
        self.grids_lbl.setText(str(grids))
        
    def set_enabled(self, enabled: bool):
        """Включить/выключить панель"""
        self.start_btn.setEnabled(enabled)
