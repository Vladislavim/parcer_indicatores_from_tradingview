"""
Упрощенное окно графика без WebEngine
Красивый 3D дизайн с русским интерфейсом
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import random

from PySide6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit
)

class IndicatorCard(QFrame):
    """Карточка индикатора с премиальным 3D дизайном"""
    
    def __init__(self, name: str, status: str = "neutral", detail: str = "—"):
        super().__init__()
        self.name = name
        self.status = status
        self.detail = detail
        self.setup_ui()
        
    def setup_ui(self):
        self.setFixedHeight(140)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.12), 
                    stop:0.3 rgba(255, 255, 255, 0.06), 
                    stop:0.7 rgba(255, 255, 255, 0.04),
                    stop:1 rgba(255, 255, 255, 0.08));
                border: 3px solid rgba(255, 255, 255, 0.3);
                border-radius: 24px;
                padding: 24px;
                box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3),
                            inset 0 2px 4px rgba(255, 255, 255, 0.1);
            }
            QFrame:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.18), 
                    stop:0.3 rgba(255, 255, 255, 0.10), 
                    stop:0.7 rgba(255, 255, 255, 0.08),
                    stop:1 rgba(255, 255, 255, 0.12));
                border: 3px solid rgba(255, 255, 255, 0.5);
                box-shadow: 0 16px 32px rgba(0, 0, 0, 0.4),
                            inset 0 3px 6px rgba(255, 255, 255, 0.15);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        
        # Заголовок
        header = QHBoxLayout()
        
        name_label = QLabel(self.name)
        name_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 24px;")
        self.update_status(self.status)
        
        header.addWidget(name_label)
        header.addStretch()
        header.addWidget(self.status_dot)
        
        # Детали
        self.detail_label = QLabel(self.detail)
        self.detail_label.setStyleSheet("font-size: 16px; color: rgba(255, 255, 255, 0.8); font-weight: 600;")
        self.detail_label.setWordWrap(True)
        
        # Время обновления
        self.time_label = QLabel("—")
        self.time_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.6); font-weight: 500;")
        
        layout.addLayout(header)
        layout.addWidget(self.detail_label, 1)
        layout.addWidget(self.time_label)
        
    def update_status(self, status: str, detail: str = None, updated: str = None):
        self.status = status
        
        colors = {
            "bull": "#30D158",
            "bear": "#FF3B30",
            "neutral": "rgba(255, 255, 255, 0.5)",
            "na": "rgba(255, 255, 255, 0.3)"
        }
        
        color = colors.get(status, colors["na"])
        self.status_dot.setStyleSheet(f"font-size: 24px; color: {color}; text-shadow: 0 0 8px {color};")
        
        if detail:
            self.detail = detail
            self.detail_label.setText(detail)
            
        if updated:
            self.time_label.setText(f"Обновлено: {updated}")
        else:
            self.time_label.setText(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")

class MarketDataWidget(QWidget):
    """Виджет с рыночными данными"""
    
    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        header = QLabel(f"Рыночные Данные - {self.symbol}")
        header.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; margin-bottom: 12px;")
        layout.addWidget(header)
        
        # Данные в сетке
        data_frame = QFrame()
        data_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.10), 
                    stop:0.3 rgba(255, 255, 255, 0.06), 
                    stop:0.7 rgba(255, 255, 255, 0.04),
                    stop:1 rgba(255, 255, 255, 0.08));
                border: 3px solid rgba(255, 255, 255, 0.2);
                border-radius: 20px;
                padding: 24px;
                box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2),
                            inset 0 2px 4px rgba(255, 255, 255, 0.1);
            }
        """)
        
        data_layout = QGridLayout(data_frame)
        data_layout.setSpacing(20)
        
        # Примерные данные
        data_items = [
            ("Цена", "$43,250.00", "#30D158"),
            ("Изменение 24ч", "+2.45%", "#30D158"),
            ("Объем", "1.2B USDT", "#ffffff"),
            ("Рын. Кап.", "850B", "#ffffff"),
            ("Макс 24ч", "$43,890.00", "#ffffff"),
            ("Мин 24ч", "$42,100.00", "#ffffff"),
        ]
        
        for i, (label, value, color) in enumerate(data_items):
            row = i // 2
            col = (i % 2) * 2
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7); font-weight: 600;")
            
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"font-size: 18px; color: {color}; font-weight: 800;")
            
            data_layout.addWidget(label_widget, row, col)
            data_layout.addWidget(value_widget, row, col + 1)
            
        layout.addWidget(data_frame)
        layout.addStretch()

class SimpleChartWindow(QMainWindow):
    """Упрощенное окно графика с 3D дизайном"""
    
    def __init__(self, symbol: str, timeframe: str = "1H"):
        super().__init__()
        self.symbol = symbol.replace(".P", "")  # Убираем .P для отображения
        self.original_symbol = symbol  # Сохраняем оригинальный символ
        self.timeframe = timeframe
        self.indicators: Dict[str, IndicatorCard] = {}
        
        self.setWindowTitle(f"{self.symbol} - Премиальный Анализ Графика")
        
        # Применяем премиальный 3D стиль
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0a0a0b, stop:0.2 #1a1a1c, stop:0.5 #111113, stop:0.8 #1a1a1c, stop:1 #0a0a0b);
            }
        """)
        
        self.setup_ui()
        self.setup_update_timer()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(32)
        
        # Левая панель с "графиком"
        chart_container = self.create_chart_container()
        
        # Правая панель с индикаторами и данными
        sidebar = self.create_sidebar()
        
        # Добавляем в основной layout
        main_layout.addWidget(chart_container, 3)  # 75% ширины
        main_layout.addWidget(sidebar, 1)          # 25% ширины
        
    def create_chart_container(self):
        """Создание контейнера с 'графиком'"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.12), 
                    stop:0.3 rgba(255, 255, 255, 0.06), 
                    stop:0.7 rgba(255, 255, 255, 0.04),
                    stop:1 rgba(255, 255, 255, 0.08));
                border: 3px solid rgba(255, 255, 255, 0.3);
                border-radius: 28px;
                box-shadow: 0 16px 32px rgba(0, 0, 0, 0.3),
                            inset 0 2px 4px rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок графика
        header = self.create_chart_header()
        layout.addWidget(header)
        
        # Область "графика"
        chart_area = self.create_chart_area()
        layout.addWidget(chart_area, 1)
        
        return container
        
    def create_chart_header(self):
        """Создание заголовка графика"""
        header = QFrame()
        header.setFixedHeight(100)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.15), 
                    stop:0.5 rgba(255, 255, 255, 0.08),
                    stop:1 rgba(255, 255, 255, 0.10));
                border-bottom: 3px solid rgba(255, 255, 255, 0.2);
                border-top-left-radius: 28px;
                border-top-right-radius: 28px;
                box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(40, 20, 40, 20)
        
        # Название символа
        symbol_label = QLabel(f"{self.symbol}")
        symbol_label.setStyleSheet("font-size: 28px; font-weight: 900; color: #ffffff;")
        
        # Таймфрейм
        tf_label = QLabel(f"{self.timeframe}")
        tf_label.setStyleSheet("font-size: 18px; font-weight: 700; color: rgba(255, 255, 255, 0.8);")
        
        # Кнопки управления
        controls = QHBoxLayout()
        
        # Селектор таймфрейма
        tf_combo = QComboBox()
        tf_combo.addItems(["1m", "5m", "15m", "1H", "4H", "1D"])
        tf_combo.setCurrentText(self.timeframe)
        tf_combo.currentTextChanged.connect(self.change_timeframe)
        tf_combo.setStyleSheet("min-width: 100px;")
        
        # Кнопка TradingView
        tv_btn = QPushButton("Открыть в TradingView")
        tv_btn.setProperty("class", "secondary")
        tv_btn.clicked.connect(self.open_tradingview)
        
        controls.addWidget(tf_combo)
        controls.addWidget(tv_btn)
        
        layout.addWidget(symbol_label)
        layout.addWidget(tf_label)
        layout.addStretch()
        layout.addLayout(controls)
        
        return header
        
    def create_chart_area(self):
        """Создание области графика"""
        chart_area = QFrame()
        chart_area.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(10, 10, 11, 0.95), 
                    stop:0.3 rgba(15, 15, 17, 0.90), 
                    stop:0.7 rgba(20, 20, 22, 0.90),
                    stop:1 rgba(10, 10, 11, 0.95));
                border-bottom-left-radius: 24px;
                border-bottom-right-radius: 24px;
                margin: 4px;
            }
        """)
        
        layout = QVBoxLayout(chart_area)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Заглушка для графика
        chart_placeholder = QTextEdit()
        chart_placeholder.setReadOnly(True)
        chart_placeholder.setStyleSheet("""
            QTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.05), 
                    stop:0.5 rgba(255, 255, 255, 0.02),
                    stop:1 rgba(255, 255, 255, 0.03));
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 16px;
                font-weight: 600;
                padding: 20px;
            }
        """)
        
        chart_text = f"""
📈 ГРАФИК {self.symbol} ({self.timeframe})

🔥 Здесь будет отображаться интерактивный график TradingView
   с живыми данными и индикаторами в реальном времени.

💡 Для просмотра полного графика нажмите кнопку 
   "Открыть в TradingView" выше.

⚡ Индикаторы обновляются автоматически каждые 5 секунд
   и отображаются в правой панели.

🎯 Поддерживаемые индикаторы:
   • EMA Market Structure
   • Smart Money Breakout  
   • Trend Targets

📊 Текущий статус: Мониторинг активен
"""
        
        chart_placeholder.setPlainText(chart_text)
        layout.addWidget(chart_placeholder)
        
        return chart_area
        
    def create_sidebar(self):
        """Создание боковой панели"""
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.08), 
                    stop:0.3 rgba(255, 255, 255, 0.04), 
                    stop:0.7 rgba(255, 255, 255, 0.02),
                    stop:1 rgba(255, 255, 255, 0.06));
                border: 3px solid rgba(255, 255, 255, 0.2);
                border-radius: 28px;
                box-shadow: 0 12px 24px rgba(0, 0, 0, 0.2),
                            inset 0 2px 4px rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(28)
        
        # Заголовок
        title = QLabel("Живой Анализ")
        title.setStyleSheet("font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 12px;")
        layout.addWidget(title)
        
        # Скроллируемая область для индикаторов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        indicators_widget = QWidget()
        indicators_layout = QVBoxLayout(indicators_widget)
        indicators_layout.setSpacing(20)
        
        # Создаем карточки индикаторов
        indicator_specs = [
            ("ema_ms", "EMA Структура Рынка", "Анализ тренда EMA"),
            ("smart_money", "Умные Деньги", "Сигналы BOS/CHoCH"),
            ("trend_targets", "Цели Тренда", "Анализ Supertrend"),
        ]
        
        for key, name, description in indicator_specs:
            card = IndicatorCard(name, "na", description)
            self.indicators[key] = card
            indicators_layout.addWidget(card)
            
        indicators_layout.addStretch()
        scroll.setWidget(indicators_widget)
        layout.addWidget(scroll, 1)
        
        # Рыночные данные
        market_data = MarketDataWidget(self.symbol)
        layout.addWidget(market_data)
        
        return sidebar
        
    def setup_update_timer(self):
        """Настройка таймера обновления"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_indicators)
        self.update_timer.start(5000)  # Обновляем каждые 5 секунд
        
    def update_indicators(self):
        """Обновление индикаторов (демо данные)"""
        statuses = ["bull", "bear", "neutral"]
        details = {
            "ema_ms": ["Тренд EMA вверх", "Тренд EMA вниз", "EMA боковое движение"],
            "smart_money": ["BOS пробой вверх", "BOS пробой вниз", "Ожидание сигнала"],
            "trend_targets": ["Восходящий тренд", "Нисходящий тренд", "Боковое движение"]
        }
        
        for key, card in self.indicators.items():
            status = random.choice(statuses)
            detail = random.choice(details[key])
            card.update_status(status, detail)
            
    def change_timeframe(self, new_tf: str):
        """Изменение таймфрейма"""
        self.timeframe = new_tf
        self.setWindowTitle(f"{self.symbol} - Премиальный Анализ Графика ({new_tf})")
        
    def open_tradingview(self):
        """Открытие TradingView в браузере"""
        try:
            src = "BYBIT"  # По умолчанию
            tv_symbol = self.symbol.replace(".P", "")
            url = f"https://www.tradingview.com/chart/?symbol={src}:{tv_symbol}"
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            print(f"Ошибка открытия TradingView: {e}")
            
    def update_indicator_status(self, indicator_key: str, status: str, detail: str):
        """Обновление статуса индикатора извне"""
        if indicator_key in self.indicators:
            self.indicators[indicator_key].update_status(status, detail)
            
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.update_timer.stop()
        super().closeEvent(event)