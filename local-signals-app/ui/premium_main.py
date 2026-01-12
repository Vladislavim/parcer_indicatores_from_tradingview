"""
Рабочее главное окно с полным функционалом
Русский интерфейс, 3D дизайн, полноэкранный режим
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSettings, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QColor, QFont, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QComboBox, QLineEdit, QPlainTextEdit, QPushButton,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, 
    QFrame, QScrollArea, QProgressBar, QTabWidget, QApplication
)

from core.worker import Worker
from ui.theme import create_animated_progress

THREAD_ID_DEV = 5
DEFAULT_CHAT_ID = "-1003065825691"

class ConfirmCloseDialog(QMessageBox):
    """Диалог подтверждения закрытия с опцией 'больше не показывать'"""
    
    def __init__(self, parent=None, title="Подтверждение", message="Вы уверены, что хотите закрыть?"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(QMessageBox.Question)
        
        # Кнопки
        self.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.setDefaultButton(QMessageBox.No)
        
        # Переводим кнопки на русский
        self.button(QMessageBox.Yes).setText("Да")
        self.button(QMessageBox.No).setText("Отмена")
        
        # Добавляем чекбокс "больше не показывать"
        self.dont_show_again = QCheckBox("Больше не показывать это предупреждение")
        self.dont_show_again.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #ffffff;
                font-weight: 600;
                margin: 10px;
            }
        """)
        self.setCheckBox(self.dont_show_again)
        
        # Применяем 3D стиль к диалогу
        self.setStyleSheet("""
            QMessageBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(20, 20, 22, 0.98), 
                    stop:0.5 rgba(30, 30, 32, 0.95),
                    stop:1 rgba(15, 15, 17, 0.98));
                border: 3px solid rgba(255, 255, 255, 0.4);
                border-radius: 20px;
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
            }
            QMessageBox QPushButton {
                min-width: 100px;
                min-height: 35px;
                margin: 5px;
            }
        """)
    
    def is_dont_show_again_checked(self):
        """Проверяет, отмечена ли галочка 'больше не показывать'"""
        return self.dont_show_again.isChecked()

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

STATUS_COLOR = {
    "bull": QColor("#30D158"),
    "bear": QColor("#FF3B30"),
    "neutral": QColor("rgba(255, 255, 255, 0.4)"),
    "na": QColor("rgba(255, 255, 255, 0.2)"),
}

class PremiumStatusCard(QFrame):
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
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 16, 20, 16)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; font-weight: 600; text-transform: uppercase;")
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

class CoinSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Заголовок с кнопками управления
        header = QHBoxLayout()
        title = QLabel("Выбор монет для уведомлений")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        
        # Кнопки быстрого выбора
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        select_top = QPushButton("Топ 5")
        select_top.setProperty("class", "ghost")
        select_top.clicked.connect(self.select_top)
        
        select_all = QPushButton("Все")
        select_all.setProperty("class", "ghost")
        select_all.clicked.connect(self.select_all)
        
        select_none = QPushButton("Очистить")
        select_none.setProperty("class", "ghost")
        select_none.clicked.connect(self.select_none)
        
        button_layout.addWidget(select_top)
        button_layout.addWidget(select_all)
        button_layout.addWidget(select_none)
        
        header.addWidget(title)
        header.addStretch()
        header.addLayout(button_layout)
        
        layout.addLayout(header)
        
        # Скроллируемая область с монетами
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(240)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.02);
            }
        """)
        
        coins_widget = QWidget()
        coins_layout = QGridLayout(coins_widget)
        coins_layout.setSpacing(12)
        coins_layout.setContentsMargins(16, 16, 16, 16)
        
        # Создаем чекбоксы для монет в 4 колонки
        for i, symbol in enumerate(MONITOR_SYMBOLS):
            clean_symbol = symbol.replace("USDT.P", "").replace("1000", "")
            cb = QCheckBox(f"{clean_symbol}")
            cb.setStyleSheet("font-weight: 600; font-size: 14px;")
            self.checkboxes[symbol] = cb
            
            row = i // 4
            col = i % 4
            coins_layout.addWidget(cb, row, col)
            
        scroll.setWidget(coins_widget)
        layout.addWidget(scroll)
        
        # Информация
        info = QLabel("Все монеты отслеживаются, уведомления только по выбранным")
        info.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-style: italic; font-size: 13px;")
        layout.addWidget(info)
        
    def select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)
            
    def select_none(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)
            
    def select_top(self):
        top_coins = ["BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "XRPUSDT.P", "DOGEUSDT.P"]
        for symbol, cb in self.checkboxes.items():
            cb.setChecked(symbol in top_coins)
            
    def get_selected(self) -> List[str]:
        return [symbol for symbol, cb in self.checkboxes.items() if cb.isChecked()]
        
    def set_selected(self, symbols: List[str]):
        for symbol, cb in self.checkboxes.items():
            cb.setChecked(symbol in symbols)

class IndicatorSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.indicators = [
            IndicatorSpec("ema_ms", "EMA Структура Рынка", "Анализ тренда EMA с определением BOS"),
            IndicatorSpec("smart_money", "Умные Деньги", "Продвинутое распознавание паттернов BOS/CHoCH"),
            IndicatorSpec("trend_targets", "Цели Тренда", "Направленный анализ на основе Supertrend"),
        ]
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        title = QLabel("Технические Индикаторы")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)
        
        for indicator in self.indicators:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 rgba(255, 255, 255, 0.06), stop:1 rgba(255, 255, 255, 0.02));
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 16px;
                    padding: 20px;
                }
                QFrame:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 rgba(255, 255, 255, 0.08), stop:1 rgba(255, 255, 255, 0.04));
                    border: 1px solid rgba(255, 255, 255, 0.12);
                }
            """)
            
            card_layout = QHBoxLayout(card)
            card_layout.setSpacing(16)
            
            # Чекбокс
            cb = QCheckBox()
            cb.setChecked(True)  # По умолчанию все включены
            self.checkboxes[indicator.key] = cb
            
            # Информация
            info_layout = QVBoxLayout()
            info_layout.setSpacing(6)
            
            name_label = QLabel(indicator.title)
            name_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
            
            desc_label = QLabel(indicator.description)
            desc_label.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 0.7);")
            desc_label.setWordWrap(True)
            
            info_layout.addWidget(name_label)
            info_layout.addWidget(desc_label)
            
            card_layout.addWidget(cb)
            card_layout.addLayout(info_layout, 1)
            
            layout.addWidget(card)
            
    def get_enabled(self) -> List[str]:
        return [key for key, cb in self.checkboxes.items() if cb.isChecked()]
        
    def set_enabled(self, keys: List[str]):
        for key, cb in self.checkboxes.items():
            cb.setChecked(key in keys)

class DashboardWindow(QMainWindow):
    def __init__(self, indicators: List[IndicatorSpec]):
        super().__init__()
        self.setWindowTitle("Торговая Панель")
        self.setMinimumSize(1400, 800)
        
        self.indicators = indicators
        self._row_by_symbol: Dict[str, int] = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # Заголовок
        header = QHBoxLayout()
        title = QLabel("Живая Торговая Панель")
        title.setStyleSheet("font-size: 32px; font-weight: 900; color: #ffffff;")
        
        self.status_label = QLabel("Инициализация...")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 16px; font-weight: 500;")
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status_label)
        
        layout.addLayout(header)
        
        # Таблица
        cols = ["Символ", "ТФ"] + [i.title for i in self.indicators] + ["График", "Обновлено"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # Настройка колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # TF
        for i in range(2, 2 + len(self.indicators)):  # Indicators
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        header.setSectionResizeMode(len(cols) - 2, QHeaderView.ResizeToContents)  # Chart button
        header.setSectionResizeMode(len(cols) - 1, QHeaderView.ResizeToContents)  # Updated
        
        layout.addWidget(self.table, 1)
        
        # Кнопки управления
        controls = QHBoxLayout()
        
        self.btn_clear = QPushButton("Очистить Все")
        self.btn_clear.setProperty("class", "secondary")
        self.btn_clear.clicked.connect(self.clear_statuses)
        
        self.btn_refresh = QPushButton("Обновить Данные")
        self.btn_refresh.clicked.connect(self.refresh_data)
        
        controls.addWidget(self.btn_clear)
        controls.addStretch()
        controls.addWidget(self.btn_refresh)
        
        layout.addLayout(controls)
        
    def set_symbols(self, symbols: List[str], tf: str = "1h"):
        self.table.setRowCount(0)
        self._row_by_symbol.clear()
        
        for symbol in symbols:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_by_symbol[symbol] = row
            
            # Symbol
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setFont(QFont("monospace", 12, QFont.Bold))
            self.table.setItem(row, 0, symbol_item)
            
            # Timeframe
            tf_item = QTableWidgetItem(tf.upper())
            tf_item.setTextAlignment(Qt.AlignCenter)
            tf_item.setFont(QFont("monospace", 11))
            self.table.setItem(row, 1, tf_item)
            
            # Indicators
            for i in range(len(self.indicators)):
                item = QTableWidgetItem("Loading...")
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(STATUS_COLOR["na"])
                self.table.setItem(row, 2 + i, item)
                
            # Chart button
            chart_btn = QPushButton("Открыть График")
            chart_btn.setProperty("class", "secondary")
            chart_btn.clicked.connect(lambda checked, s=symbol: self.open_chart(s, tf))
            self.table.setCellWidget(row, 2 + len(self.indicators), chart_btn)
                
            # Updated
            updated_item = QTableWidgetItem("—")
            updated_item.setTextAlignment(Qt.AlignCenter)
            updated_item.setForeground(STATUS_COLOR["na"])
            self.table.setItem(row, 2 + len(self.indicators) + 1, updated_item)
            
        self.status_label.setText(f"Мониторинг {len(symbols)} активов")
        
    def open_chart(self, symbol: str, timeframe: str):
        """Открытие окна с графиком"""
        try:
            # Создаем упрощенное окно графика без WebEngine
            from ui.simple_chart_window import SimpleChartWindow
            
            # Создаем новое окно графика
            chart_window = SimpleChartWindow(symbol, timeframe)
            
            # Показываем окно в полноэкранном режиме
            chart_window.showMaximized()
            chart_window.raise_()
            chart_window.activateWindow()
            
            self.status_label.setText(f"График открыт для {symbol}")
            
        except Exception as e:
            # Если не удается открыть график, открываем TradingView в браузере
            try:
                src = "BYBIT"  # По умолчанию
                tv_symbol = symbol.replace(".P", "")
                url = f"https://www.tradingview.com/chart/?symbol={src}:{tv_symbol}"
                QDesktopServices.openUrl(QUrl(url))
                self.status_label.setText(f"TradingView открыт в браузере для {symbol}")
            except Exception as browser_error:
                QMessageBox.warning(
                    self, 
                    "Ошибка Графика", 
                    f"Не удалось открыть график для {symbol}:\n{str(e)}\n\n"
                    f"Также не удалось открыть браузер:\n{str(browser_error)}"
                )
        
    def clear_statuses(self):
        for row in range(self.table.rowCount()):
            for col in range(2, 2 + len(self.indicators)):
                item = self.table.item(row, col)
                if item:
                    item.setText("Loading...")
                    item.setForeground(STATUS_COLOR["na"])
            
            updated_item = self.table.item(row, 2 + len(self.indicators) + 1)
            if updated_item:
                updated_item.setText("—")
                updated_item.setForeground(STATUS_COLOR["na"])
                
        self.status_label.setText("All statuses cleared")
                
    def refresh_data(self):
        self.status_label.setText("Refreshing market data...")
        
    def update_status(self, symbol: str, indicator_key: str, status: str, detail: str = ""):
        row = self._row_by_symbol.get(symbol)
        if row is None:
            return
            
        # Найти колонку индикатора
        col = None
        for i, spec in enumerate(self.indicators):
            if spec.key == indicator_key:
                col = 2 + i
                break
        if col is None:
            return
            
        # Обновить статус
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, col, item)
            
        # Статусы без эмодзи
        status_text = {
            "bull": "BULL",
            "bear": "BEAR", 
            "neutral": "NEUTRAL",
            "na": "LOADING"
        }
        
        display_text = f"{status_text.get(status, 'LOADING')} {detail}" if detail else status_text.get(status, 'LOADING')
        item.setText(display_text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(STATUS_COLOR.get(status, STATUS_COLOR["na"]))
        
        # Обновить время
        from datetime import datetime
        updated_item = self.table.item(row, 2 + len(self.indicators) + 1)
        if updated_item:
            updated_item.setText(datetime.now().strftime("%H:%M:%S"))
            updated_item.setForeground(STATUS_COLOR["neutral"])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local Signals Pro - Премиальный Торговый Комплекс")
        
        # Полноэкранный режим
        self.showMaximized()
        
        self.settings = QSettings()
        self.worker: Optional[Worker] = None
        self.dashboard: Optional[DashboardWindow] = None
        
        # Анимированный прогресс-бар
        self.progress, self.progress_animator = create_animated_progress()
        
        # Статус таймер
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(1000)
        
        self.setup_ui()
        self.load_state()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(32)
        
        # Заголовок приложения
        self.setup_header(main_layout)
        
        # Основной контент в табах
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabWidget::pane { margin-top: 16px; }")
        
        # Вкладка настроек
        settings_tab = self.create_settings_tab()
        tabs.addTab(settings_tab, "Конфигурация")
        
        # Вкладка мониторинга
        monitor_tab = self.create_monitor_tab()
        tabs.addTab(monitor_tab, "Мониторинг")
        
        main_layout.addWidget(tabs, 1)
        
        # Панель управления
        self.setup_control_panel(main_layout)
        
    def setup_header(self, layout):
        header = QHBoxLayout()
        
        # Логотип и название
        title_layout = QVBoxLayout()
        title = QLabel("Local Signals Pro")
        title.setStyleSheet("font-size: 36px; font-weight: 900; color: #ffffff;")
        
        subtitle = QLabel("Премиальный Алгоритмический Анализ Торговых Сигналов")
        subtitle.setStyleSheet("font-size: 16px; color: rgba(255, 255, 255, 0.7); font-weight: 500;")
        
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        
        # Статус карточки
        status_layout = QHBoxLayout()
        status_layout.setSpacing(20)
        
        self.status_card = PremiumStatusCard("Статус", "Остановлен", "na")
        self.coins_card = PremiumStatusCard("Активы", str(len(MONITOR_SYMBOLS)), "neutral")
        self.alerts_card = PremiumStatusCard("Уведомления", "0", "na")
        
        status_layout.addWidget(self.status_card)
        status_layout.addWidget(self.coins_card)
        status_layout.addWidget(self.alerts_card)
        
        header.addLayout(title_layout)
        header.addStretch()
        header.addLayout(status_layout)
        
        layout.addLayout(header)
        
    def create_settings_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setSpacing(32)
        
        # Левая колонка
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(24)
        
        # Настройки данных
        data_group = QGroupBox("Источник Рыночных Данных")
        data_layout = QGridLayout(data_group)
        data_layout.setSpacing(16)
        
        self.source = QComboBox()
        self.source.addItem("Bybit Бессрочные Фьючерсы", "BYBIT_PERP")
        self.source.addItem("Binance Спотовая Торговля", "BINANCE_SPOT")
        
        self.tf = QComboBox()
        timeframes = {
            "1m": "1 минута (быстрые сигналы)",
            "5m": "5 минут (средние сигналы)", 
            "15m": "15 минут (стабильные сигналы)",
            "1h": "1 час (надежные сигналы)",
            "4h": "4 часа (сильные сигналы)",
            "1d": "1 день (долгосрочные сигналы)"
        }
        
        for tf_key, tf_label in timeframes.items():
            self.tf.addItem(tf_label, tf_key)
        self.tf.setCurrentIndex(3)  # По умолчанию 1h
        
        self.btn_open_tv = QPushButton("Открыть TradingView")
        self.btn_open_tv.setProperty("class", "secondary")
        self.btn_open_tv.clicked.connect(self.open_tradingview_all)
        
        data_layout.addWidget(QLabel("Биржа:"), 0, 0)
        data_layout.addWidget(self.source, 0, 1)
        data_layout.addWidget(QLabel("Таймфрейм:"), 1, 0)
        data_layout.addWidget(self.tf, 1, 1)
        data_layout.addWidget(self.btn_open_tv, 2, 0, 1, 2)
        
        # Информация о времени сигналов
        signal_info = QLabel("💡 Минутные свечи: сигналы каждые 15-30 сек\n"
                            "⏰ Часовые свечи: сигналы каждые 2-5 мин\n"
                            "📊 Дневные свечи: сигналы каждые 10-30 мин")
        signal_info.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7); 
            font-style: italic; 
            font-size: 12px;
            background: rgba(0, 122, 255, 0.1);
            border: 1px solid rgba(0, 122, 255, 0.3);
            border-radius: 8px;
            padding: 8px;
            margin-top: 8px;
        """)
        data_layout.addWidget(signal_info, 3, 0, 1, 2)
        
        # Telegram настройки
        tg_group = QGroupBox("Уведомления Telegram")
        tg_layout = QGridLayout(tg_group)
        tg_layout.setSpacing(16)
        
        self.tg_token = QLineEdit()
        self.tg_token.setPlaceholderText("Токен бота от @BotFather")
        self.tg_token.setEchoMode(QLineEdit.Password)
        
        self.tg_chat = QLineEdit()
        self.tg_chat.setPlaceholderText("ID группового чата")
        self.tg_chat.setText(DEFAULT_CHAT_ID)
        
        self.tg_mention = QLineEdit()
        self.tg_mention.setPlaceholderText("@имя_пользователя для упоминания (опционально)")
        
        self.btn_test = QPushButton("Тестовое Сообщение")
        self.btn_test.clicked.connect(self.test_telegram)
        
        info_label = QLabel("Сообщения отправляются в тред 'dev & testing bot'")
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-style: italic; font-size: 13px;")
        
        tg_layout.addWidget(QLabel("Токен Бота:"), 0, 0)
        tg_layout.addWidget(self.tg_token, 0, 1)
        tg_layout.addWidget(QLabel("ID Чата:"), 1, 0)
        tg_layout.addWidget(self.tg_chat, 1, 1)
        tg_layout.addWidget(QLabel("Упоминание:"), 2, 0)
        tg_layout.addWidget(self.tg_mention, 2, 1)
        tg_layout.addWidget(info_label, 3, 0, 1, 2)
        tg_layout.addWidget(self.btn_test, 4, 0, 1, 2)
        
        left_layout.addWidget(data_group)
        left_layout.addWidget(tg_group)
        left_layout.addStretch()
        
        left_scroll.setWidget(left_widget)
        
        # Правая колонка
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(24)
        
        # Селектор монет
        self.coin_selector = CoinSelector()
        right_layout.addWidget(self.coin_selector)
        
        # Селектор индикаторов
        self.indicator_selector = IndicatorSelector()
        right_layout.addWidget(self.indicator_selector)
        
        right_layout.addStretch()
        right_scroll.setWidget(right_widget)
        
        layout.addWidget(left_scroll, 1)
        layout.addWidget(right_scroll, 1)
        
        return tab
        
    def create_monitor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(24)
        
        # Лог с фильтрацией
        log_group = QGroupBox("Журнал Системных Событий")
        log_layout = QVBoxLayout(log_group)
        
        # Фильтры лога
        log_controls = QHBoxLayout()
        log_controls.addWidget(QLabel("Фильтр:"))
        
        self.log_filter = QComboBox()
        self.log_filter.addItems(["Все События", "Только Ошибки", "Только Сигналы", "Только Telegram"])
        
        self.btn_clear_log = QPushButton("Очистить Журнал")
        self.btn_clear_log.setProperty("class", "secondary")
        self.btn_clear_log.clicked.connect(self.clear_log)
        
        log_controls.addWidget(self.log_filter)
        log_controls.addStretch()
        log_controls.addWidget(self.btn_clear_log)
        
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13px;")
        
        log_layout.addLayout(log_controls)
        log_layout.addWidget(self.log, 1)
        
        layout.addWidget(log_group, 1)
        
        return tab
        
    def setup_control_panel(self, layout):
        controls = QFrame()
        controls.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(255, 255, 255, 0.08), stop:1 rgba(255, 255, 255, 0.03));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 24px;
                padding: 24px;
            }
        """)
        
        controls_layout = QHBoxLayout(controls)
        controls_layout.setSpacing(20)
        
        # Анимированный прогресс бар БЕЗ процентов
        self.progress.setVisible(False)
        self.progress.setFixedHeight(12)
        
        # Кнопки управления
        self.btn_start = QPushButton("Запустить Премиум Анализ")
        self.btn_start.setProperty("class", "success")
        self.btn_start.clicked.connect(self.start)
        
        self.btn_stop = QPushButton("Остановить Анализ")
        self.btn_stop.setProperty("class", "danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        
        self.btn_dashboard = QPushButton("Открыть Панель")
        self.btn_dashboard.clicked.connect(self.open_dashboard)
        
        controls_layout.addWidget(self.progress)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_dashboard)
        
        layout.addWidget(controls)
        
    def update_status_display(self):
        """Обновляет отображение статуса"""
        if self.worker and self.worker.isRunning():
            self.status_card.update_status("bull", "Активен")
        else:
            self.status_card.update_status("na", "Остановлен")
            
        # Обновляем счетчики
        selected_coins = len(self.coin_selector.get_selected())
        
        self.coins_card.update_status("neutral", str(len(MONITOR_SYMBOLS)))
        self.alerts_card.update_status("neutral", str(selected_coins))
        
    def append_log(self, msg: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {msg}"
        self.log.appendPlainText(formatted_msg)
        
        # Автоскролл
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_log(self):
        self.log.clear()
        
    def load_state(self):
        # Загружаем настройки Telegram
        self.tg_token.setText(self.settings.value("tg/token", "", type=str))
        self.tg_chat.setText(self.settings.value("tg/chat", DEFAULT_CHAT_ID, type=str))
        self.tg_mention.setText(self.settings.value("tg/mention", "", type=str))
        
        # Загружаем настройки источника
        src = self.settings.value("cfg/source", "BYBIT_PERP", type=str)
        tf = self.settings.value("cfg/tf", "1h", type=str)
        self.source.setCurrentIndex(max(0, self.source.findData(src)))
        
        # Находим индекс по данным, а не по тексту
        tf_index = -1
        for i in range(self.tf.count()):
            if self.tf.itemData(i) == tf:
                tf_index = i
                break
        if tf_index >= 0:
            self.tf.setCurrentIndex(tf_index)
        
        # Загружаем выбранные монеты
        selected_coins_json = self.settings.value("coins/selected", "", type=str)
        if selected_coins_json:
            try:
                selected_coins = json.loads(selected_coins_json)
                self.coin_selector.set_selected(selected_coins)
            except:
                pass
                
        # Загружаем включенные индикаторы
        enabled_indicators_json = self.settings.value("indicators/enabled", "", type=str)
        if enabled_indicators_json:
            try:
                enabled_indicators = json.loads(enabled_indicators_json)
                self.indicator_selector.set_enabled(enabled_indicators)
            except:
                pass
                
    def save_state(self):
        # Сохраняем настройки Telegram
        self.settings.setValue("tg/token", self.tg_token.text().strip())
        self.settings.setValue("tg/chat", self.tg_chat.text().strip())
        self.settings.setValue("tg/mention", self.tg_mention.text().strip())
        
        # Сохраняем настройки источника
        self.settings.setValue("cfg/source", self.source.currentData())
        self.settings.setValue("cfg/tf", self.tf.currentData())  # Используем currentData() вместо currentText()
        
        # Сохраняем выбранные монеты
        selected_coins = self.coin_selector.get_selected()
        self.settings.setValue("coins/selected", json.dumps(selected_coins))
        
        # Сохраняем включенные индикаторы
        enabled_indicators = self.indicator_selector.get_enabled()
        self.settings.setValue("indicators/enabled", json.dumps(enabled_indicators))
        
    def open_tradingview_all(self):
        symbols = MONITOR_SYMBOLS[:12]  # Ограничиваем 12 вкладками
        src = self.source.currentData()
        exchange = "BYBIT" if src == "BYBIT_PERP" else "BINANCE"
        
        for symbol in symbols:
            tv_symbol = symbol.replace(".P", "")
            url = f"https://www.tradingview.com/chart/?symbol={exchange}:{tv_symbol}"
            QDesktopServices.openUrl(QUrl(url))
            
        self.append_log(f"Открыто {len(symbols)} вкладок TradingView")
        
    def test_telegram(self):
        token = self.tg_token.text().strip()
        chat = self.tg_chat.text().strip()
        
        if not token or not chat:
            QMessageBox.warning(self, "Ошибка Конфигурации", "Пожалуйста, заполните Токен Бота и ID Чата")
            return
            
        try:
            from core.worker import send_telegram_message
            test_message = "Тестовое сообщение от Local Signals Pro\n\nИнтеграция с Telegram работает корректно!"
            send_telegram_message(token, chat, test_message, THREAD_ID_DEV)
            self.append_log("Тестовое сообщение успешно отправлено в Telegram")
            QMessageBox.information(self, "Успех", "Тестовое сообщение отправлено успешно!")
            self.save_state()
        except Exception as e:
            self.append_log(f"Ошибка Telegram: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось отправить сообщение:\n{e}")
            
    def open_dashboard(self):
        if self.dashboard is None:
            indicators = [
                IndicatorSpec("ema_ms", "EMA Структура", "EMA Market Structure"),
                IndicatorSpec("smart_money", "Умные Деньги", "Smart Money Breakout"),
                IndicatorSpec("trend_targets", "Цели Тренда", "Trend Targets"),
            ]
            self.dashboard = DashboardWindow(indicators)
            
        symbols = [s.replace(".P", "") for s in MONITOR_SYMBOLS]
        self.dashboard.set_symbols(symbols, self.tf.currentData())
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()
        
    def start(self):
        if self.worker and self.worker.isRunning():
            return
            
        selected_coins = self.coin_selector.get_selected()
        enabled_indicators = self.indicator_selector.get_enabled()
        
        if not enabled_indicators:
            QMessageBox.warning(self, "Ошибка Конфигурации", "Пожалуйста, выберите хотя бы один индикатор")
            return
            
        # Конфигурация воркера
        config = {
            "source": self.source.currentData(),
            "timeframe": self.tf.currentData(),  # Используем currentData()
            "symbols": MONITOR_SYMBOLS,  # Мониторим все
            "alert_symbols": selected_coins,  # Алерты только по выбранным
            "indicators": enabled_indicators,
            "tg_token": self.tg_token.text().strip(),
            "tg_chat": self.tg_chat.text().strip(),
            "tg_thread": THREAD_ID_DEV,
            "tg_mention": self.tg_mention.text().strip(),
        }
        
        self.save_state()
        
        # Запускаем воркер
        self.worker = Worker(config)
        self.worker.log.connect(self.append_log)
        self.worker.status.connect(self.on_status_update)
        self.worker.finished.connect(self.on_worker_finished)
        
        # Подключаем новые сигналы
        if hasattr(self.worker, 'progress'):
            self.worker.progress.connect(self.on_progress_update)
        if hasattr(self.worker, 'error'):
            self.worker.error.connect(self.on_error)
        if hasattr(self.worker, 'notification'):
            self.worker.notification.connect(self.show_notification)
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setVisible(True)
        self.progress_animator.start_animation()  # Запускаем анимацию
        
        self.append_log(f"Запуск анализа: {len(MONITOR_SYMBOLS)} активов, {len(enabled_indicators)} индикаторов, {len(selected_coins)} уведомлений")
        self.worker.start()
        
        # Обновляем дашборд если открыт
        if self.dashboard:
            symbols = [s.replace(".P", "") for s in MONITOR_SYMBOLS]
            self.dashboard.set_symbols(symbols, self.tf.currentData())
            
    def stop(self):
        if not self.worker:
            return
            
        self.append_log("Остановка анализа...")
        self.worker.stop()
        self.btn_stop.setEnabled(False)
        
    def on_worker_finished(self):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_animator.stop_animation()  # Останавливаем анимацию
        self.append_log("Анализ успешно остановлен")
        
    def on_status_update(self, symbol: str, indicator_key: str, status: str, detail: str, updated: str):
        if self.dashboard:
            self.dashboard.update_status(symbol, indicator_key, status, detail)
            
    def on_progress_update(self, value: int):
        """Обновление прогресса обработки - НЕ ИСПОЛЬЗУЕТСЯ для анимированного бара"""
        pass  # Анимация идет независимо от реального прогресса
        
    def on_error(self, error_msg: str):
        """Обработка критических ошибок"""
        self.append_log(f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")
        QMessageBox.critical(self, "Критическая Ошибка", error_msg)
        
    def show_notification(self, message: str, notification_type: str):
        """Показать всплывающее уведомление"""
        self.append_log(f"{notification_type.upper()}: {message}")
            
    def closeEvent(self, event: QCloseEvent):
        """Обработка закрытия окна с предупреждением"""
        # Проверяем настройку "больше не показывать"
        dont_show = self.settings.value("ui/dont_show_close_warning", False, type=bool)
        
        if not dont_show:
            dialog = ConfirmCloseDialog(
                self, 
                "Подтверждение Закрытия", 
                "Вы уверены, что хотите закрыть Local Signals Pro?\n\nВсе активные процессы мониторинга будут остановлены."
            )
            
            result = dialog.exec()
            
            if result == QMessageBox.Yes:
                # Сохраняем настройку "больше не показывать"
                if dialog.is_dont_show_again_checked():
                    self.settings.setValue("ui/dont_show_close_warning", True)
                
                # Закрываем приложение
                try:
                    self.save_state()
                except:
                    pass
                    
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                    
                event.accept()
            else:
                event.ignore()
        else:
            # Закрываем без предупреждения
            try:
                self.save_state()
            except:
                pass
                
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                
            event.accept()