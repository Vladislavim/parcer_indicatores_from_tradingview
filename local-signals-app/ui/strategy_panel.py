"""
Strategy selection panel for standalone and combo systems.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import FocusSafeDoubleSpinBox, FocusSafeSpinBox


COLORS = {
    "bg": "#0f0f14",
    "bg_card": "#1a1a22",
    "border": "#2a2a35",
    "accent": "#6C5CE7",
    "accent_light": "#8B7CF7",
    "green": "#00D9A5",
    "red": "#FF6B6B",
    "text": "#ffffff",
    "text_dim": "#888888",
}

TOP_COINS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "ADA", "AVAX", "LINK", "DOT", "LTC",
    "BCH", "TRX", "UNI", "APT", "ARB",
    "OP", "SUI", "TON", "NEAR", "PEPE",
]

GROUP_META = {
    "Стратегии по ТЗ": "Главные сценарии из твоего ТЗ: order block и liquidity return.",
    "Одиночные стратегии": "Можно запускать отдельно как самостоятельные торговые системы.",
    "Комбо-стратегии": "Связки из нескольких индикаторов для более строгого отбора входов.",
}

RISK_COLORS = {
    "Низкий": COLORS["green"],
    "Средний": "#FFA500",
    "Высокий": COLORS["red"],
    "Очень высокий": "#FF0000",
    "Low": COLORS["green"],
    "Medium": "#FFA500",
    "High": COLORS["red"],
    "Very High": "#FF0000",
}


class StrategyCard(QFrame):
    toggled = Signal(str, bool)

    def __init__(self, strategy_info: dict, parent=None):
        super().__init__(parent)
        self.strategy_id = strategy_info["id"]
        self.info = strategy_info
        self._enabled = False

        self.setObjectName("StrategyCard")
        self.setProperty("selected", "false")
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(
            f"""
            QFrame#StrategyCard {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QFrame#StrategyCard[selected="true"] {{
                border: 2px solid {COLORS['accent']};
            }}
            QLabel {{
                background: transparent;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()

        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.setStyleSheet(
            """
            QCheckBox { background: transparent; }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 4px;
                border: 2px solid #555;
                background: #1a1a22;
            }
            QCheckBox::indicator:hover {
                border-color: #6C5CE7;
            }
            QCheckBox::indicator:checked {
                background: #6C5CE7;
                border-color: #6C5CE7;
            }
            """
        )
        self.checkbox.toggled.connect(self._on_toggle)
        header.addWidget(self.checkbox)

        name_lbl = QLabel(strategy_info["name"])
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: white;")
        header.addWidget(name_lbl)
        header.addStretch()

        risk_color = RISK_COLORS.get(strategy_info["risk_level"], COLORS["text_dim"])
        risk_lbl = QLabel(strategy_info["risk_level"])
        risk_lbl.setStyleSheet(f"font-size: 11px; color: {risk_color};")
        header.addWidget(risk_lbl)
        layout.addLayout(header)

        desc = QLabel(strategy_info["description"])
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(desc)

        stats = QGridLayout()
        stats.setSpacing(6)
        stats.addWidget(self._stat_label("Доходность"), 0, 0)
        stats.addWidget(self._stat_value(strategy_info["avg_monthly_return"], COLORS["green"]), 0, 1)
        stats.addWidget(self._stat_label("Винрейт"), 0, 2)
        stats.addWidget(self._stat_value(strategy_info["win_rate"]), 0, 3)

        stats.addWidget(self._stat_label("R:R"), 1, 0)
        stats.addWidget(self._stat_value(strategy_info["risk_reward"]), 1, 1)
        stats.addWidget(self._stat_label("Сделок/мес"), 1, 2)
        stats.addWidget(self._stat_value(strategy_info["trades_per_month"]), 1, 3)

        stats.addWidget(self._stat_label("ТФ"), 2, 0)
        stats.addWidget(self._stat_value(strategy_info["timeframe"]), 2, 1)
        stats.addWidget(self._stat_label("SL/TP"), 2, 2)
        stats.addWidget(self._stat_value(f"{strategy_info['sl_pct']}%/{strategy_info['tp_pct']}%"), 2, 3)
        layout.addLayout(stats)

    def _stat_label(self, text: str) -> QLabel:
        lbl = QLabel(text + ":")
        lbl.setStyleSheet("font-size: 10px; color: #666;")
        return lbl

    def _stat_value(self, text: str, color: str = "#fff") -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: 500;")
        return lbl

    def _on_toggle(self, checked: bool):
        self._enabled = checked
        self.setProperty("selected", "true" if checked else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.toggled.emit(self.strategy_id, checked)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        self.checkbox.setChecked(enabled)


class StrategyPanel(QFrame):
    start_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StrategyPanel")
        self.setStyleSheet(
            f"""
            QFrame#StrategyPanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Мульти-стратегии")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white;")
        header.addWidget(title)
        header.addStretch()

        self.status_lbl = QLabel("Выкл")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888;")
        header.addWidget(self.status_lbl)
        layout.addLayout(header)

        info = QLabel(
            "Здесь только реальные стратегии: отдельные, комбо и сценарии по order block.\n"
            "Рекомендуемый риск: 1-2% на стратегию."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            """
            font-size: 11px;
            color: #888;
            background: #1a1a22;
            padding: 10px;
            border-radius: 6px;
            """
        )
        layout.addWidget(info)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)

        risk_group = QWidget()
        risk_group.setStyleSheet("background: transparent;")
        risk_layout = QVBoxLayout(risk_group)
        risk_layout.setContentsMargins(0, 0, 0, 0)
        risk_layout.setSpacing(4)
        risk_lbl = QLabel("% на стратегию")
        risk_lbl.setStyleSheet("font-size: 11px; color: #888;")
        risk_layout.addWidget(risk_lbl)

        self.risk_spin = FocusSafeDoubleSpinBox()
        self.risk_spin.setRange(0.25, 1.5)
        self.risk_spin.setValue(0.5)
        self.risk_spin.setDecimals(2)
        self.risk_spin.setSingleStep(0.25)
        self.risk_spin.setSuffix("%")
        self.risk_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.risk_spin.setToolTip("Колесо мыши отключено. Значение меняется только после фокуса.")
        self.risk_spin.setFixedHeight(36)
        self.risk_spin.setStyleSheet(
            """
            QDoubleSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 12px;
            }
            """
        )
        risk_layout.addWidget(self.risk_spin)
        settings_row.addWidget(risk_group)

        lev_group = QWidget()
        lev_group.setStyleSheet("background: transparent;")
        lev_layout = QVBoxLayout(lev_group)
        lev_layout.setContentsMargins(0, 0, 0, 0)
        lev_layout.setSpacing(4)
        lev_lbl = QLabel("Плечо")
        lev_lbl.setStyleSheet("font-size: 11px; color: #888;")
        lev_layout.addWidget(lev_lbl)

        self.leverage_spin = FocusSafeSpinBox()
        self.leverage_spin.setRange(3, 5)
        self.leverage_spin.setValue(5)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setToolTip("Колесо мыши отключено. Значение меняется только после фокуса.")
        self.leverage_spin.setFixedHeight(36)
        self.leverage_spin.setStyleSheet(
            """
            QSpinBox {
                background: #2a2a35;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 12px;
            }
            """
        )
        lev_layout.addWidget(self.leverage_spin)
        settings_row.addWidget(lev_group)

        settings_row.addStretch()
        layout.addLayout(settings_row)

        coins_lbl = QLabel("Монеты:")
        coins_lbl.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(coins_lbl)

        coins_grid = QGridLayout()
        coins_grid.setSpacing(8)
        self.coin_checks = {}
        for idx, coin in enumerate(TOP_COINS):
            cb = QCheckBox(coin)
            cb.setChecked(coin in ["BTC", "ETH", "SOL", "XRP", "DOGE"])
            cb.setStyleSheet(
                """
                QCheckBox { color: white; font-size: 11px; background: transparent; }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                    border: 2px solid #444;
                    background: #1a1a22;
                }
                QCheckBox::indicator:checked {
                    background: #6C5CE7;
                    border-color: #6C5CE7;
                }
                """
            )
            self.coin_checks[coin] = cb
            coins_grid.addWidget(cb, idx // 5, idx % 5)
        layout.addLayout(coins_grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(420)
        scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            """
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_btn = QPushButton("Запустить")
        self.start_btn.setFixedHeight(42)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
            """
        )
        self.start_btn.clicked.connect(self.start_clicked.emit)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setFixedHeight(42)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            f"""
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
            """
        )
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        self.strategy_cards = {}

    def _create_group_header(self, title: str, hint: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background: {COLORS['bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: white;")
        layout.addWidget(title_lbl)

        hint_lbl = QLabel(hint)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(hint_lbl)
        return card

    def load_strategies(self, strategies: list):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.strategy_cards.clear()

        groups_in_order = ["Стратегии по ТЗ", "Одиночные стратегии", "Комбо-стратегии"]
        for group_name in groups_in_order:
            bucket = [item for item in strategies if item.get("group") == group_name]
            if not bucket:
                continue

            self.cards_layout.addWidget(self._create_group_header(group_name, GROUP_META.get(group_name, "")))
            for strat in bucket:
                card = StrategyCard(strat)
                self.strategy_cards[strat["id"]] = card
                self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def get_selected_strategies(self) -> list:
        return [sid for sid, card in self.strategy_cards.items() if card.is_enabled()]

    def get_selected_coins(self) -> list:
        return [coin for coin, cb in self.coin_checks.items() if cb.isChecked()]

    def get_risk_pct(self) -> float:
        return self.risk_spin.value()

    def get_leverage(self) -> int:
        return self.leverage_spin.value()

    def set_running(self, running: bool):
        if running:
            self.status_lbl.setText("Работает")
            self.status_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['green']};")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_lbl.setText("Выкл")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #888;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def set_enabled(self, enabled: bool):
        self.start_btn.setEnabled(enabled)
        for card in self.strategy_cards.values():
            card.checkbox.setEnabled(enabled)
