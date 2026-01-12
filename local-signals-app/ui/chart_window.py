"""
Премиальное окно с встроенными графиками TradingView и индикаторами
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from PySide6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtWebEngineWidgets import QWebEngineView

class TradingViewWidget(QWebEngineView):
    """Встроенный TradingView виджет с индикаторами"""
    
    def __init__(self, symbol: str, timeframe: str = "1H"):
        super().__init__()
        self.symbol = symbol
        self.timeframe = timeframe
        self.setup_chart()
        
    def setup_chart(self):
        """Настройка TradingView виджета"""
        # Создаем HTML с TradingView виджетом
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TradingView Chart</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: #0a0a0b;
                    font-family: 'SF Pro Display', system-ui, sans-serif;
                }}
                #tradingview_chart {{
                    width: 100%;
                    height: 100vh;
                }}
                .loading {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    color: #ffffff;
                    font-size: 18px;
                }}
            </style>
        </head>
        <body>
            <div id="tradingview_chart">
                <div class="loading">Loading chart...</div>
            </div>
            
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <script type="text/javascript">
                new TradingView.widget({{
                    "width": "100%",
                    "height": "100%",
                    "symbol": "BYBIT:{self.symbol}",
                    "interval": "{self.timeframe}",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#0a0a0b",
                    "enable_publishing": false,
                    "hide_top_toolbar": false,
                    "hide_legend": false,
                    "save_image": false,
                    "container_id": "tradingview_chart",
                    "studies": [
                        "MAExp@tv-basicstudies",
                        "BB@tv-basicstudies"
                    ],
                    "overrides": {{
                        "paneProperties.background": "#0a0a0b",
                        "paneProperties.vertGridProperties.color": "rgba(255,255,255,0.06)",
                        "paneProperties.horzGridProperties.color": "rgba(255,255,255,0.06)",
                        "symbolWatermarkProperties.transparency": 90,
                        "scalesProperties.textColor": "#ffffff",
                        "mainSeriesProperties.candleStyle.upColor": "#30D158",
                        "mainSeriesProperties.candleStyle.downColor": "#FF3B30",
                        "mainSeriesProperties.candleStyle.borderUpColor": "#30D158",
                        "mainSeriesProperties.candleStyle.borderDownColor": "#FF3B30",
                        "mainSeriesProperties.candleStyle.wickUpColor": "#30D158",
                        "mainSeriesProperties.candleStyle.wickDownColor": "#FF3B30"
                    }},
                    "studies_overrides": {{
                        "volume.volume.color.0": "#FF3B30",
                        "volume.volume.color.1": "#30D158"
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        self.setHtml(html_content)

class IndicatorCard(QFrame):
    """Карточка индикатора с премиальным дизайном"""
    
    def __init__(self, name: str, status: str = "neutral", detail: str = "—"):
        super().__init__()
        self.name = name
        self.status = status
        self.detail = detail
        self.setup_ui()
        
    def setup_ui(self):
        self.setFixedHeight(120)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.08), stop:1 rgba(255, 255, 255, 0.03));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 20px;
                padding: 20px;
            }
            QFrame:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.12), stop:1 rgba(255, 255, 255, 0.06));
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # Заголовок
        header = QHBoxLayout()
        
        name_label = QLabel(self.name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 20px;")
        self.update_status(self.status)
        
        header.addWidget(name_label)
        header.addStretch()
        header.addWidget(self.status_dot)
        
        # Детали
        self.detail_label = QLabel(self.detail)
        self.detail_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        self.detail_label.setWordWrap(True)
        
        # Время обновления
        self.time_label = QLabel("—")
        self.time_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
        
        layout.addLayout(header)
        layout.addWidget(self.detail_label, 1)
        layout.addWidget(self.time_label)
        
    def update_status(self, status: str, detail: str = None, updated: str = None):
        self.status = status
        
        colors = {
            "bull": "#30D158",
            "bear": "#FF3B30",
            "neutral": "rgba(255, 255, 255, 0.4)",
            "na": "rgba(255, 255, 255, 0.2)"
        }
        
        color = colors.get(status, colors["na"])
        self.status_dot.setStyleSheet(f"font-size: 20px; color: {color};")
        
        if detail:
            self.detail = detail
            self.detail_label.setText(detail)
            
        if updated:
            self.time_label.setText(f"Updated: {updated}")
        else:
            self.time_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

class MarketDataWidget(QWidget):
    """Виджет с рыночными данными"""
    
    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        header = QLabel(f"Market Data - {self.symbol}")
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;")
        layout.addWidget(header)
        
        # Данные в сетке
        data_frame = QFrame()
        data_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.06), stop:1 rgba(255, 255, 255, 0.02));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 20px;
            }
        """)
        
        data_layout = QGridLayout(data_frame)
        data_layout.setSpacing(16)
        
        # Примерные данные
        data_items = [
            ("Price", "$43,250.00", "#30D158"),
            ("24h Change", "+2.45%", "#30D158"),
            ("Volume", "1.2B USDT", "#ffffff"),
            ("Market Cap", "850B", "#ffffff"),
            ("High 24h", "$43,890.00", "#ffffff"),
            ("Low 24h", "$42,100.00", "#ffffff"),
        ]
        
        for i, (label, value, color) in enumerate(data_items):
            row = i // 2
            col = (i % 2) * 2
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 0.6); font-weight: 500;")
            
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"font-size: 16px; color: {color}; font-weight: 700;")
            
            data_layout.addWidget(label_widget, row, col)
            data_layout.addWidget(value_widget, row, col + 1)
            
        layout.addWidget(data_frame)
        layout.addStretch()

class ChartWindow(QMainWindow):
    """Премиальное окно с графиком и индикаторами"""
    
    # Сигнал для обновления статуса индикатора
    indicator_updated = pyqtSignal(str, str, str, str)  # indicator_key, status, detail, time
    
    def __init__(self, symbol: str, timeframe: str = "1H"):
        super().__init__()
        self.symbol = symbol.replace(".P", "")  # Убираем .P для отображения
        self.original_symbol = symbol  # Сохраняем оригинальный символ
        self.timeframe = timeframe
        self.indicators: Dict[str, IndicatorCard] = {}
        
        self.setWindowTitle(f"{self.symbol} - Premium Chart Analysis")
        self.setMinimumSize(1400, 900)
        
        # Применяем премиальный стиль
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0a0a0b, stop:0.3 #111113, stop:1 #0a0a0b);
            }
        """)
        
        self.setup_ui()
        self.setup_update_timer()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)
        
        # Левая панель с графиком
        chart_container = self.create_chart_container()
        
        # Правая панель с индикаторами и данными
        sidebar = self.create_sidebar()
        
        # Добавляем в основной layout
        main_layout.addWidget(chart_container, 3)  # 75% ширины
        main_layout.addWidget(sidebar, 1)          # 25% ширины
        
    def create_chart_container(self):
        """Создание контейнера с графиком"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.08), stop:1 rgba(255, 255, 255, 0.03));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 24px;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок графика
        header = self.create_chart_header()
        layout.addWidget(header)
        
        # TradingView виджет
        self.chart_widget = TradingViewWidget(self.symbol, self.timeframe)
        self.chart_widget.setStyleSheet("border-radius: 20px;")
        layout.addWidget(self.chart_widget, 1)
        
        return container
        
    def create_chart_header(self):
        """Создание заголовка графика"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.1), stop:1 rgba(255, 255, 255, 0.05));
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                border-top-left-radius: 24px;
                border-top-right-radius: 24px;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(32, 16, 32, 16)
        
        # Название символа
        symbol_label = QLabel(f"{self.symbol}")
        symbol_label.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        
        # Таймфрейм
        tf_label = QLabel(f"{self.timeframe}")
        tf_label.setStyleSheet("font-size: 16px; font-weight: 600; color: rgba(255, 255, 255, 0.7);")
        
        # Кнопки управления
        controls = QHBoxLayout()
        
        # Селектор таймфрейма
        tf_combo = QComboBox()
        tf_combo.addItems(["1m", "5m", "15m", "1H", "4H", "1D"])
        tf_combo.setCurrentText(self.timeframe)
        tf_combo.currentTextChanged.connect(self.change_timeframe)
        tf_combo.setStyleSheet("min-width: 80px;")
        
        # Кнопка обновления
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.refresh_chart)
        
        controls.addWidget(tf_combo)
        controls.addWidget(refresh_btn)
        
        layout.addWidget(symbol_label)
        layout.addWidget(tf_label)
        layout.addStretch()
        layout.addLayout(controls)
        
        return header
        
    def create_sidebar(self):
        """Создание боковой панели"""
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.06), stop:1 rgba(255, 255, 255, 0.02));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 24px;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # Заголовок
        title = QLabel("Live Analysis")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; margin-bottom: 8px;")
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
        indicators_layout.setSpacing(16)
        
        # Создаем карточки индикаторов
        indicator_specs = [
            ("ema_ms", "EMA Market Structure", "EMA тренд анализ"),
            ("smart_money", "Smart Money", "BOS/CHoCH сигналы"),
            ("trend_targets", "Trend Targets", "Supertrend анализ"),
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
        """Обновление индикаторов (заглушка)"""
        # Здесь будет реальная логика получения данных индикаторов
        # Пока используем случайные данные для демонстрации
        import random
        
        statuses = ["bull", "bear", "neutral"]
        details = {
            "ema_ms": ["EMA trend up", "EMA trend down", "EMA sideways"],
            "smart_money": ["BOS breakout up", "BOS breakout down", "Waiting for signal"],
            "trend_targets": ["Uptrend active", "Downtrend active", "Sideways movement"]
        }
        
        for key, card in self.indicators.items():
            status = random.choice(statuses)
            detail = random.choice(details[key])
            card.update_status(status, detail)
            
            # Отправляем сигнал об обновлении
            self.indicator_updated.emit(key, status, detail, datetime.now().strftime("%H:%M:%S"))
            
    def change_timeframe(self, new_tf: str):
        """Изменение таймфрейма"""
        self.timeframe = new_tf
        self.refresh_chart()
        
    def refresh_chart(self):
        """Обновление графика"""
        # Пересоздаем TradingView виджет с новыми параметрами
        old_widget = self.chart_widget
        self.chart_widget = TradingViewWidget(self.symbol, self.timeframe)
        
        # Заменяем виджет в layout
        layout = old_widget.parent().layout()
        layout.replaceWidget(old_widget, self.chart_widget)
        old_widget.deleteLater()
        
    def update_indicator_status(self, indicator_key: str, status: str, detail: str):
        """Обновление статуса индикатора извне"""
        if indicator_key in self.indicators:
            self.indicators[indicator_key].update_status(status, detail)
            
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.update_timer.stop()
        super().closeEvent(event)