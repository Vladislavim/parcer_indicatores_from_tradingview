from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
)


@dataclass(frozen=True)
class IndicatorSpec:
    key: str
    title: str
    description: str
    emoji: str


STATUS_COLOR = {
    "bull": QColor("#10b981"),
    "bear": QColor("#ef4444"),
    "neutral": QColor("#94a3b8"),
    "na": QColor("#64748b"),
}


def _now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


class DashboardWindow(QMainWindow):
    """
    Современное окно дашборда с красивым дизайном
    Таблица: Symbol | TF | EMA MS | Smart Money | Trend Targets | Updated
    """
    def __init__(self, indicators: List[IndicatorSpec]):
        super().__init__()
        self.setWindowTitle("📊 Live Dashboard - Trading Signals")
        self.setMinimumSize(1200, 700)

        self.indicators = indicators
        self.col_symbol = 0
        self.col_tf = 1
        self.col_first_ind = 2
        self.col_updated = self.col_first_ind + len(indicators)

        self._row_by_symbol: Dict[str, int] = {}

        self.setup_ui()

    def setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Заголовок с современным дизайном
        header = QHBoxLayout()
        title = QLabel("📊 Live Trading Signals")
        title.setStyleSheet("font-size: 24pt; font-weight: 700; color: #60a5fa;")
        
        self.status_label = QLabel("🔄 Ожидание данных...")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12pt;")
        
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Таблица с эмодзи в заголовках
        cols = ["💰 Symbol", "⏰ TF"] + [f"{i.emoji} {i.title}" for i in self.indicators] + ["🕐 Updated"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        # Настройка размеров колонок
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(self.col_symbol, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(self.col_tf, QHeaderView.ResizeToContents)
        for c in range(self.col_first_ind, self.col_updated):
            h.setSectionResizeMode(c, QHeaderView.Stretch)
        h.setSectionResizeMode(self.col_updated, QHeaderView.ResizeToContents)

        layout.addWidget(self.table, 1)

        # Кнопки управления с современным дизайном
        controls = QHBoxLayout()
        
        self.btn_clear = QPushButton("🗑️ Очистить статусы")
        self.btn_clear.setProperty("class", "secondary")
        self.btn_clear.clicked.connect(self.clear_statuses)
        
        self.btn_refresh = QPushButton("🔄 Обновить данные")
        self.btn_refresh.clicked.connect(self.refresh_data)
        
        controls.addWidget(self.btn_clear)
        controls.addStretch(1)
        controls.addWidget(self.btn_refresh)
        layout.addLayout(controls)

    def set_symbols(self, symbols: List[str], tf: str):
        """Пересобрать таблицу под список монет."""
        self.table.setRowCount(0)
        self._row_by_symbol.clear()

        for symbol in symbols:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_by_symbol[symbol] = row

            # Symbol с моноширинным шрифтом
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setFont(QFont("monospace", 11, QFont.Bold))
            self.table.setItem(row, self.col_symbol, symbol_item)
            
            # Timeframe
            tf_item = QTableWidgetItem(tf)
            tf_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.col_tf, tf_item)

            # Индикаторы с ожиданием
            for i, _spec in enumerate(self.indicators):
                item = QTableWidgetItem("⏳")
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(STATUS_COLOR["na"])
                self.table.setItem(row, self.col_first_ind + i, item)

            # Время обновления
            upd = QTableWidgetItem("—")
            upd.setTextAlignment(Qt.AlignCenter)
            upd.setForeground(STATUS_COLOR["na"])
            self.table.setItem(row, self.col_updated, upd)
            
        self.status_label.setText(f"📈 Мониторинг {len(symbols)} монет")

    def clear_statuses(self):
        """Очистить все статусы индикаторов"""
        for row in range(self.table.rowCount()):
            for col in range(self.col_first_ind, self.col_updated):
                item = self.table.item(row, col)
                if item:
                    item.setText("⏳")
                    item.setForeground(STATUS_COLOR["na"])
            upd = self.table.item(row, self.col_updated)
            if upd:
                upd.setText("—")
                upd.setForeground(STATUS_COLOR["na"])
                
        self.status_label.setText("🗑️ Статусы очищены")

    def refresh_data(self):
        """Обновить данные (пока просто меняем статус)"""
        self.status_label.setText("🔄 Обновление данных...")

    def update_status(self, symbol: str, indicator_key: str, status: str, detail: str = ""):
        """
        Обновить статус индикатора для монеты
        status: bull | bear | neutral | na
        detail: текст для отображения в ячейке
        """
        row = self._row_by_symbol.get(symbol)
        if row is None:
            return

        # Найти колонку индикатора
        col = None
        for i, spec in enumerate(self.indicators):
            if spec.key == indicator_key:
                col = self.col_first_ind + i
                break
        if col is None:
            return

        # Обновить ячейку индикатора
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, col, item)

        # Эмодзи для статусов
        status_emoji = {
            "bull": "🟢",
            "bear": "🔴", 
            "neutral": "⚪",
            "na": "⏳"
        }
        
        # Формируем текст для отображения
        display_text = f"{status_emoji.get(status, '⏳')} {detail}" if detail else status_emoji.get(status, '⏳')
        
        item.setText(display_text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(STATUS_COLOR.get(status, STATUS_COLOR["na"]))

        # Обновить время
        upd = self.table.item(row, self.col_updated)
        if upd:
            upd.setText(_now_hms())
            upd.setForeground(STATUS_COLOR["neutral"])
            
        # Обновить статус в заголовке
        active_count = sum(1 for r in range(self.table.rowCount()) 
                          for c in range(self.col_first_ind, self.col_updated)
                          if self.table.item(r, c) and "🟢" in self.table.item(r, c).text())
        
        self.status_label.setText(f"📊 Активных сигналов: {active_count}")
