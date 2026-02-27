"""
Журнал сделок - полная история торговли с аналитикой
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QComboBox, QFileDialog, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from core.storage import get_journal_file, migrate_if_missing

COLORS = {
    'bg_card': '#1a1a22',
    'border': '#2a2a35',
    'accent': '#6C5CE7',
    'green': '#00D9A5',
    'red': '#FF6B6B',
    'orange': '#FFA500',
    'text': '#ffffff',
    'text_dim': '#888888',
}

# Цвета для разных стратегий
STRATEGY_COLORS = {
    'Manual': '#6C5CE7',           # Фиолетовый
    'Smart AI v1': '#00D9A5',      # Зелёный
    'Smart AI v2': '#00CED1',      # Бирюзовый
    'AutoTrade (Индикаторы)': '#FF6B6B',  # Красный
    'Trend Following': '#FFD700',  # Золотой
    'Breakout': '#FF8C00',         # Оранжевый
    'Mean Reversion': '#9370DB',   # Сиреневый
    'Scalping': '#FF69B4',         # Розовый
    'Swing Trading': '#20B2AA',    # Морской
    'Grid Bot': '#4169E1',         # Синий
    'Unknown': '#888888',          # Серый
}

def get_strategy_color(strategy: str) -> str:
    """Возвращает цвет для стратегии"""
    # Проверяем точное совпадение
    if strategy in STRATEGY_COLORS:
        return STRATEGY_COLORS[strategy]
    # Проверяем частичное совпадение
    for key, color in STRATEGY_COLORS.items():
        if key.lower() in strategy.lower():
            return color
    return STRATEGY_COLORS['Unknown']


def _extract_note_field(notes: str, prefix: str) -> str:
    notes = str(notes or "")
    for part in notes.split("|"):
        chunk = part.strip()
        if chunk.lower().startswith(prefix.lower()):
            return chunk.split(":", 1)[1].strip() if ":" in chunk else chunk
    return ""


def get_trade_open_reason(notes: str) -> str:
    return _extract_note_field(notes, "Причина входа")


def get_trade_premises(notes: str) -> str:
    return _extract_note_field(notes, "Предпосылки/модель")


def get_trade_close_details(notes: str) -> str:
    return _extract_note_field(notes, "Закрытие")

# Путь к файлу журнала (постоянное хранилище вне git-репозитория)
JOURNAL_FILE = str(get_journal_file())
_LEGACY_JOURNAL = Path(os.path.dirname(os.path.dirname(__file__))) / "trade_journal.json"
migrate_if_missing(Path(JOURNAL_FILE), _LEGACY_JOURNAL)


@dataclass
class Trade:
    """Запись о сделке"""
    id: str
    timestamp_open: str      # Дата/время открытия
    timestamp_close: str     # Дата/время закрытия
    symbol: str              # Монета
    side: str                # long/short
    strategy: str            # Название стратегии
    entry_price: float       # Цена входа
    exit_price: float        # Цена выхода
    size: float              # Размер позиции
    leverage: int            # Плечо
    pnl_usd: float          # PnL в долларах
    pnl_pct: float          # PnL в процентах
    fees: float             # Комиссии
    sl_price: float         # Стоп-лосс
    tp_price: float         # Тейк-профит
    close_reason: str       # Причина закрытия (TP/SL/Manual/Signal)
    notes: str              # Заметки


class TradeJournal:
    """Менеджер журнала сделок"""
    
    def __init__(self):
        self.trades: List[Trade] = []
        self.load()
        
    def load(self):
        """Загружает журнал из файла"""
        if os.path.exists(JOURNAL_FILE):
            try:
                with open(JOURNAL_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.trades = [Trade(**t) for t in data]
            except Exception as e:
                print(f"Ошибка загрузки журнала: {e}")
                self.trades = []
        else:
            self.trades = []
            
    def save(self):
        """Сохраняет журнал в файл"""
        try:
            with open(JOURNAL_FILE, 'w', encoding='utf-8') as f:
                json.dump([asdict(t) for t in self.trades], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения журнала: {e}")
            
    def add_trade(self, trade: Trade):
        """Добавляет сделку"""
        self.trades.append(trade)
        self.save()
        
    def get_stats(self, strategy: str = None) -> Dict:
        """Получает статистику по сделкам"""
        trades = self.trades
        if strategy and strategy != "Все":
            trades = [t for t in trades if t.strategy == strategy]
            
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
            }
            
        winning = [t for t in trades if t.pnl_usd > 0]
        losing = [t for t in trades if t.pnl_usd < 0]
        
        total_pnl = sum(t.pnl_usd for t in trades)
        gross_profit = sum(t.pnl_usd for t in winning) if winning else 0
        gross_loss = abs(sum(t.pnl_usd for t in losing)) if losing else 0
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(trades) * 100 if trades else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(trades) if trades else 0,
            'best_trade': max(t.pnl_usd for t in trades) if trades else 0,
            'worst_trade': min(t.pnl_usd for t in trades) if trades else 0,
            'avg_win': gross_profit / len(winning) if winning else 0,
            'avg_loss': -gross_loss / len(losing) if losing else 0,
            'profit_factor': gross_profit / gross_loss if gross_loss > 0 else 0,
        }
        
    def get_strategies(self) -> List[str]:
        """Получает список уникальных стратегий"""
        return list(set(t.strategy for t in self.trades))
        
    def get_close_reason_breakdown(self, strategy: str = None) -> Dict[str, Dict[str, float]]:
        """Возвращает статистику по причинам закрытия: количество и суммарный PnL."""
        trades = self.trades
        if strategy and strategy != "Все":
            trades = [t for t in trades if t.strategy == strategy]
        breakdown: Dict[str, Dict[str, float]] = {}
        for t in trades:
            reason = str(t.close_reason or "Unknown")
            if reason not in breakdown:
                breakdown[reason] = {"count": 0, "pnl": 0.0}
            breakdown[reason]["count"] += 1
            breakdown[reason]["pnl"] += float(t.pnl_usd or 0.0)
        return breakdown

    def export_csv(self, filepath: str):
        """Экспортирует в CSV"""
        import csv
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Заголовки
            writer.writerow([
                'ID', 'Открытие', 'Закрытие', 'Монета', 'Направление', 
                'Стратегия', 'Цена входа', 'Цена выхода', 'Размер', 
                'Плечо', 'PnL ($)', 'PnL (%)', 'Комиссии', 
                'SL', 'TP', 'Причина закрытия', 'Заметки'
            ])
            # Данные
            for t in self.trades:
                writer.writerow([
                    t.id, t.timestamp_open, t.timestamp_close, t.symbol,
                    t.side, t.strategy, t.entry_price, t.exit_price,
                    t.size, t.leverage, t.pnl_usd, t.pnl_pct,
                    t.fees, t.sl_price, t.tp_price, t.close_reason, t.notes
                ])
                
    def export_json(self, filepath: str):
        """Экспортирует в JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([asdict(t) for t in self.trades], f, ensure_ascii=False, indent=2)


# Глобальный экземпляр журнала
_journal: Optional[TradeJournal] = None

def get_journal() -> TradeJournal:
    """Получает глобальный журнал"""
    global _journal
    if _journal is None:
        _journal = TradeJournal()
    return _journal


class StatCard(QFrame):
    """Карточка статистики"""
    
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"font-size: 10px; color: {COLORS['text_dim']};")
        layout.addWidget(self.title_lbl)
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(self.value_lbl)
        
    def set_value(self, value: str, color: str = None):
        self.value_lbl.setText(value)
        if color:
            self.value_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {color};")


class TradeJournalWidget(QWidget):
    """Виджет журнала сделок"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.journal = get_journal()
        self._setup_ui()
        self._refresh()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # === HEADER ===
        header = QHBoxLayout()
        
        title = QLabel("📊 Журнал сделок")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLORS['text']};")
        header.addWidget(title)
        
        header.addStretch()
        
        # Фильтр по стратегии
        header.addWidget(QLabel("Стратегия:"))
        self.strategy_filter = QComboBox()
        self.strategy_filter.addItem("Все")
        self.strategy_filter.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                color: {COLORS['text']};
                min-width: 120px;
            }}
        """)
        self.strategy_filter.currentTextChanged.connect(self._refresh)
        header.addWidget(self.strategy_filter)
        
        # Кнопки экспорта
        self.export_csv_btn = QPushButton("📥 CSV")
        self.export_csv_btn.setCursor(Qt.PointingHandCursor)
        self.export_csv_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none; border-radius: 6px;
                color: white; font-size: 11px; padding: 8px 12px;
            }}
            QPushButton:hover {{ background: #8B7CF7; }}
        """)
        self.export_csv_btn.clicked.connect(self._export_csv)
        header.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QPushButton("📥 JSON")
        self.export_json_btn.setCursor(Qt.PointingHandCursor)
        self.export_json_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text']}; font-size: 11px; padding: 8px 12px;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; }}
        """)
        self.export_json_btn.clicked.connect(self._export_json)
        header.addWidget(self.export_json_btn)
        
        layout.addLayout(header)
        
        # === ЛЕГЕНДА ЦВЕТОВ СТРАТЕГИЙ ===
        legend_frame = QFrame()
        legend_frame.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 6px; padding: 4px;")
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(8, 4, 8, 4)
        legend_layout.setSpacing(12)
        
        legend_title = QLabel("Стратегии:")
        legend_title.setStyleSheet(f"font-size: 10px; color: {COLORS['text_dim']};")
        legend_layout.addWidget(legend_title)
        
        # Основные стратегии для легенды
        legend_items = [
            ("Manual", "Manual"),
            ("AI v1", "Smart AI v1"),
            ("AI v2", "Smart AI v2"),
            ("Auto", "AutoTrade (Индикаторы)"),
            ("Trend", "Trend Following"),
            ("Grid", "Grid Bot"),
        ]
        
        for label, strategy_key in legend_items:
            color = STRATEGY_COLORS.get(strategy_key, COLORS['text_dim'])
            item = QLabel(f"● {label}")
            item.setStyleSheet(f"font-size: 10px; color: {color}; font-weight: 600;")
            legend_layout.addWidget(item)
        
        legend_layout.addStretch()
        layout.addWidget(legend_frame)
        
        # === СТАТИСТИКА ===
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        
        self.stat_total = StatCard("Всего сделок")
        stats_layout.addWidget(self.stat_total)
        
        self.stat_winrate = StatCard("Win Rate")
        stats_layout.addWidget(self.stat_winrate)
        
        self.stat_pnl = StatCard("Общий PnL")
        stats_layout.addWidget(self.stat_pnl)
        
        self.stat_avg = StatCard("Средний PnL")
        stats_layout.addWidget(self.stat_avg)
        
        self.stat_best = StatCard("Лучшая")
        stats_layout.addWidget(self.stat_best)
        
        self.stat_worst = StatCard("Худшая")
        stats_layout.addWidget(self.stat_worst)
        
        self.stat_pf = StatCard("Profit Factor")
        stats_layout.addWidget(self.stat_pf)
        
        layout.addLayout(stats_layout)

        self.reason_summary = QLabel("Причины закрытия: —")
        self.reason_summary.setWordWrap(True)
        self.reason_summary.setStyleSheet(
            f"font-size: 11px; color: {COLORS['text_dim']}; "
            f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: 8px; padding: 8px 10px;"
        )
        layout.addWidget(self.reason_summary)
        
        # === ТАБЛИЦА СДЕЛОК ===
        self.table = QTableWidget()
        self.table.setColumnCount(14)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Монета", "Напр.", "Стратегия", "Вход", "Выход",
            "Размер", "Плечо", "PnL $", "PnL %", "Причина", "Длит."
        ])
        self.table.setHorizontalHeaderLabels([
            "Дата", "Монета", "Напр.", "Стратегия", "Вход", "Выход",
            "Размер", "Плечо", "PnL $", "PnL %", "Причина закрытия", "Причина входа", "Предпосылки", "Длит."
        ])
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                gridline-color: {COLORS['border']};
                color: {COLORS['text']};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QTableWidget::item:selected {{
                background: {COLORS['accent']};
            }}
            QHeaderView::section {{
                background: {COLORS['border']};
                color: {COLORS['text']};
                padding: 8px;
                border: none;
                font-weight: 600;
                font-size: 11px;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for idx in [0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 13]:
            self.table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(11, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(12, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
    def _refresh(self):
        """Обновляет данные"""
        strategy = self.strategy_filter.currentText()
        
        # Обновляем список стратегий
        current = self.strategy_filter.currentText()
        self.strategy_filter.blockSignals(True)
        self.strategy_filter.clear()
        self.strategy_filter.addItem("Все")
        for s in self.journal.get_strategies():
            self.strategy_filter.addItem(s)
        idx = self.strategy_filter.findText(current)
        if idx >= 0:
            self.strategy_filter.setCurrentIndex(idx)
        self.strategy_filter.blockSignals(False)
        
        # Статистика
        stats = self.journal.get_stats(strategy if strategy != "Все" else None)
        
        self.stat_total.set_value(str(stats['total_trades']))
        
        wr = stats['win_rate']
        wr_color = COLORS['green'] if wr >= 50 else COLORS['red']
        self.stat_winrate.set_value(f"{wr:.1f}%", wr_color)
        
        pnl = stats['total_pnl']
        pnl_color = COLORS['green'] if pnl >= 0 else COLORS['red']
        pnl_sign = "+" if pnl >= 0 else ""
        self.stat_pnl.set_value(f"{pnl_sign}${pnl:.2f}", pnl_color)
        
        avg = stats['avg_pnl']
        avg_color = COLORS['green'] if avg >= 0 else COLORS['red']
        avg_sign = "+" if avg >= 0 else ""
        self.stat_avg.set_value(f"{avg_sign}${avg:.2f}", avg_color)
        
        best = stats['best_trade']
        self.stat_best.set_value(f"+${best:.2f}", COLORS['green'])
        
        worst = stats['worst_trade']
        self.stat_worst.set_value(f"${worst:.2f}", COLORS['red'])
        
        pf = stats['profit_factor']
        pf_color = COLORS['green'] if pf >= 1 else COLORS['red']
        self.stat_pf.set_value(f"{pf:.2f}", pf_color)

        breakdown = self.journal.get_close_reason_breakdown(strategy if strategy != "Р’СЃРµ" else None)
        if breakdown:
            parts = []
            for reason, item in sorted(breakdown.items(), key=lambda kv: kv[1]["count"], reverse=True):
                pnl_val = float(item.get("pnl") or 0.0)
                pnl_sign = "+" if pnl_val >= 0 else ""
                parts.append(f"{reason}: {int(item.get('count', 0))} ({pnl_sign}${pnl_val:.2f})")
            self.reason_summary.setText("Причины закрытия: " + " | ".join(parts))
        else:
            self.reason_summary.setText("Причины закрытия: —")
        
        # Таблица
        trades = self.journal.trades
        if strategy and strategy != "Все":
            trades = [t for t in trades if t.strategy == strategy]
            
        # Сортируем по дате (новые сверху)
        trades = sorted(trades, key=lambda t: t.timestamp_close, reverse=True)
        
        self.table.setRowCount(len(trades))
        for row, trade in enumerate(trades):
            # Получаем цвет стратегии
            strategy_color = get_strategy_color(trade.strategy)
            row_bg = QColor(strategy_color)
            row_bg.setAlpha(40)  # Полупрозрачный фон
            
            # Дата
            date_item = QTableWidgetItem(trade.timestamp_close[:16])
            date_item.setBackground(row_bg)
            self.table.setItem(row, 0, date_item)
            
            # Монета
            coin = trade.symbol.split('/')[0] if '/' in trade.symbol else trade.symbol
            coin_item = QTableWidgetItem(coin)
            coin_item.setBackground(row_bg)
            self.table.setItem(row, 1, coin_item)
            
            # Направление
            side_item = QTableWidgetItem("ЛОНГ" if trade.side == "long" else "ШОРТ")
            side_item.setForeground(QColor(COLORS['green'] if trade.side == "long" else COLORS['red']))
            side_item.setBackground(row_bg)
            self.table.setItem(row, 2, side_item)
            
            # Стратегия - с ярким цветом
            strategy_item = QTableWidgetItem(trade.strategy)
            strategy_item.setForeground(QColor(strategy_color))
            strategy_item.setBackground(row_bg)
            self.table.setItem(row, 3, strategy_item)
            
            # Вход
            entry_item = QTableWidgetItem(f"${trade.entry_price:,.2f}")
            entry_item.setBackground(row_bg)
            self.table.setItem(row, 4, entry_item)
            
            # Выход
            exit_item = QTableWidgetItem(f"${trade.exit_price:,.2f}")
            exit_item.setBackground(row_bg)
            self.table.setItem(row, 5, exit_item)
            
            # Размер
            size_item = QTableWidgetItem(f"{trade.size:.4f}")
            size_item.setBackground(row_bg)
            self.table.setItem(row, 6, size_item)
            
            # Плечо
            lev_item = QTableWidgetItem(f"{trade.leverage}x")
            lev_item.setBackground(row_bg)
            self.table.setItem(row, 7, lev_item)
            
            # PnL $
            pnl_item = QTableWidgetItem(f"{'+'if trade.pnl_usd>=0 else ''}${trade.pnl_usd:.2f}")
            pnl_item.setForeground(QColor(COLORS['green'] if trade.pnl_usd >= 0 else COLORS['red']))
            pnl_item.setBackground(row_bg)
            self.table.setItem(row, 8, pnl_item)
            
            # PnL %
            pct_item = QTableWidgetItem(f"{'+'if trade.pnl_pct>=0 else ''}{trade.pnl_pct:.2f}%")
            pct_item.setForeground(QColor(COLORS['green'] if trade.pnl_pct >= 0 else COLORS['red']))
            pct_item.setBackground(row_bg)
            self.table.setItem(row, 9, pct_item)
            
            # Причина
            reason_item = QTableWidgetItem(trade.close_reason)
            reason_item.setBackground(row_bg)
            self.table.setItem(row, 10, reason_item)

            open_reason = get_trade_open_reason(trade.notes) or "—"
            open_reason_item = QTableWidgetItem(open_reason if len(open_reason) <= 90 else open_reason[:87] + "...")
            open_reason_item.setBackground(row_bg)
            open_reason_item.setToolTip(open_reason)
            self.table.setItem(row, 11, open_reason_item)

            premises = get_trade_premises(trade.notes) or get_trade_close_details(trade.notes) or (trade.notes or "—")
            premises_item = QTableWidgetItem(premises if len(premises) <= 120 else premises[:117] + "...")
            premises_item.setBackground(row_bg)
            premises_item.setToolTip(trade.notes or premises)
            self.table.setItem(row, 12, premises_item)
            
            # Длительность
            try:
                t_open = datetime.fromisoformat(trade.timestamp_open)
                t_close = datetime.fromisoformat(trade.timestamp_close)
                duration = t_close - t_open
                hours = duration.total_seconds() / 3600
                if hours < 1:
                    dur_str = f"{int(duration.total_seconds() / 60)}м"
                elif hours < 24:
                    dur_str = f"{hours:.1f}ч"
                else:
                    dur_str = f"{hours/24:.1f}д"
                dur_item = QTableWidgetItem(dur_str)
            except:
                dur_item = QTableWidgetItem("-")
            dur_item.setBackground(row_bg)
            self.table.setItem(row, 13, dur_item)
                
    def _export_csv(self):
        """Экспорт в CSV"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", 
            f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if filepath:
            self.journal.export_csv(filepath)
            QMessageBox.information(self, "Экспорт", f"Сохранено: {filepath}")
            
    def _export_json(self):
        """Экспорт в JSON"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в JSON",
            f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        if filepath:
            self.journal.export_json(filepath)
            QMessageBox.information(self, "Экспорт", f"Сохранено: {filepath}")
            
    def add_trade(self, trade: Trade):
        """Добавляет сделку и обновляет UI"""
        self.journal.add_trade(trade)
        self._refresh()
