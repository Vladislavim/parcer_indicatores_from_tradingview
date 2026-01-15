"""
Панель управления Smart AI ботом
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QWidget, QGridLayout,
    QProgressBar, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread

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

# Доступные монеты для сканирования
SCAN_COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "SUI", "WIF"]


class ABTestWorker(QThread):
    """Воркер для A/B тестирования v1 vs v2 в отдельном потоке"""
    log_signal = Signal(str)
    result_signal = Signal(object)  # лучший сигнал
    complete_signal = Signal()
    
    def __init__(self, exchange, coins: list, settings: dict):
        super().__init__()
        self.exchange = exchange
        self.coins = coins
        self.settings = settings
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def run(self):
        try:
            from strategies.smart_ai_bot import SmartAIBot
            from strategies.smart_ai_v2 import SmartAIBotV2
            
            bot_v1 = SmartAIBot(self.exchange)
            bot_v2 = SmartAIBotV2(self.exchange)
            
            self.log_signal.emit("🔬 A/B тест: v1 vs v2")
            self.log_signal.emit("=" * 40)
            
            v1_signals = []
            v2_signals = []
            
            for coin in self.coins:
                if self._stop:
                    return
                    
                symbol = f"{coin}/USDT:USDT"
                
                # v1
                try:
                    sig_v1 = bot_v1.get_signal(symbol, self.settings['risk_pct'])
                    if sig_v1 and sig_v1.action != "wait":
                        v1_signals.append((coin, sig_v1))
                except Exception as e:
                    self.log_signal.emit(f"⚠️ v1 {coin}: {str(e)[:20]}")
                
                # v2
                try:
                    sig_v2 = bot_v2.get_signal(symbol, self.settings['risk_pct'])
                    if sig_v2 and sig_v2.action != "wait":
                        v2_signals.append((coin, sig_v2))
                except Exception as e:
                    self.log_signal.emit(f"⚠️ v2 {coin}: {str(e)[:20]}")
            
            if self._stop:
                return
            
            # Выводим результаты
            self.log_signal.emit("")
            self.log_signal.emit("📊 v1 (базовый):")
            if v1_signals:
                for coin, sig in sorted(v1_signals, key=lambda x: x[1].confidence, reverse=True):
                    action = "📈" if sig.action == "buy" else "📉"
                    self.log_signal.emit(f"  {action} {coin}: {sig.confidence}%")
            else:
                self.log_signal.emit("  Нет сигналов")
            
            self.log_signal.emit("")
            self.log_signal.emit("🚀 v2 (улучшенный):")
            if v2_signals:
                for coin, sig in sorted(v2_signals, key=lambda x: x[1].confidence, reverse=True):
                    action = "📈" if sig.action == "buy" else "📉"
                    conf_count = getattr(sig.analysis, 'confluence_count', '?')
                    self.log_signal.emit(f"  {action} {coin}: {sig.confidence}% (conf:{conf_count})")
            else:
                self.log_signal.emit("  Нет сигналов")
            
            self.log_signal.emit("")
            self.log_signal.emit("=" * 40)
            
            # Сравнение
            v1_best = max(v1_signals, key=lambda x: x[1].confidence) if v1_signals else None
            v2_best = max(v2_signals, key=lambda x: x[1].confidence) if v2_signals else None
            
            best_signal = None
            if v1_best and v2_best:
                if v2_best[1].confidence > v1_best[1].confidence:
                    self.log_signal.emit(f"🏆 v2 лучше: {v2_best[0]} ({v2_best[1].confidence}% vs {v1_best[1].confidence}%)")
                    best_signal = v2_best[1]
                else:
                    self.log_signal.emit(f"🏆 v1 лучше: {v1_best[0]} ({v1_best[1].confidence}% vs {v2_best[1].confidence}%)")
                    best_signal = v1_best[1]
            elif v2_best:
                self.log_signal.emit(f"🏆 Только v2: {v2_best[0]} ({v2_best[1].confidence}%)")
                best_signal = v2_best[1]
            elif v1_best:
                self.log_signal.emit(f"🏆 Только v1: {v1_best[0]} ({v1_best[1].confidence}%)")
                best_signal = v1_best[1]
            else:
                self.log_signal.emit("📊 Обе версии: нет сигналов")
            
            if best_signal:
                self.result_signal.emit(best_signal)
                
        except Exception as e:
            self.log_signal.emit(f"❌ Ошибка A/B теста: {e}")
        finally:
            self.complete_signal.emit()


class AutoScanWorker(QThread):
    """Воркер для автоматического сканирования и торговли"""
    log_signal = Signal(str)
    scan_result = Signal(str, object)  # symbol, signal
    trade_executed = Signal(str, str, float)  # symbol, side, size
    scan_complete = Signal()
    
    def __init__(self, bot, exchange, coins: list, settings: dict):
        super().__init__()
        self.bot = bot
        self.exchange = exchange
        self.coins = coins
        self.settings = settings
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def run(self):
        """Сканирует монеты и торгует лучший сигнал"""
        try:
            best_signal = None
            best_symbol = None
            best_confidence = 0
            
            self.log_signal.emit(f"🔍 Сканирую {len(self.coins)} монет...")
            
            for coin in self.coins:
                if self._stop:
                    return
                    
                symbol = f"{coin}/USDT:USDT"
                try:
                    signal = self.bot.get_signal(symbol, self.settings['risk_pct'])
                    
                    if signal and signal.action != "wait":
                        self.scan_result.emit(symbol, signal)
                        
                        # Ищем лучший сигнал
                        if signal.confidence > best_confidence:
                            best_confidence = signal.confidence
                            best_signal = signal
                            best_symbol = symbol
                            
                except Exception as e:
                    self.log_signal.emit(f"⚠️ {coin}: {str(e)[:30]}")
                    
            if self._stop:
                return
                
            # Торгуем лучший сигнал если confidence >= порога
            min_conf = self.settings.get('min_confidence', 40)
            
            if best_signal and best_confidence >= min_conf:
                self.log_signal.emit(f"🎯 Лучший: {best_symbol.split('/')[0]} ({best_confidence}%)")
                
                if self.settings.get('auto_trade', False):
                    self._execute_trade(best_symbol, best_signal)
            else:
                self.log_signal.emit(f"📊 Нет сигналов с уверенностью >= {min_conf}%")
        except Exception as e:
            self.log_signal.emit(f"❌ Ошибка сканирования: {e}")
        finally:
            self.scan_complete.emit()
        
    def _execute_trade(self, symbol: str, signal):
        """Выполняет сделку"""
        try:
            # Получаем баланс
            balance = self.exchange.fetch_balance()
            available = float(balance.get('USDT', {}).get('free', 0))
            
            if available < 10:
                self.log_signal.emit("❌ Недостаточно баланса")
                return
                
            # Проверяем открытые позиции
            positions = self.exchange.fetch_positions()
            open_pos = [p for p in positions if float(p.get('contracts', 0)) > 0]
            
            # Максимум 2 позиции
            if len(open_pos) >= 2:
                self.log_signal.emit("⚠️ Уже 2 позиции открыты")
                return
                
            # Проверяем нет ли уже позиции по этой монете
            for pos in open_pos:
                if symbol in pos.get('symbol', ''):
                    self.log_signal.emit(f"⚠️ Уже есть позиция по {symbol.split('/')[0]}")
                    return
            
            # Рассчитываем размер
            leverage = self.settings['leverage']
            risk_pct = signal.position_size_pct
            position_usdt = available * (risk_pct / 100)
            
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            size = (position_usdt * leverage) / price
            
            # Округляем
            coin = symbol.split('/')[0]
            if coin == "BTC":
                size = round(size, 3)
            elif coin in ["ETH", "SOL"]:
                size = round(size, 2)
            else:
                size = round(size, 1)
                
            if size < 0.001:
                self.log_signal.emit("❌ Слишком маленький размер")
                return
                
            # Устанавливаем плечо
            try:
                self.exchange.set_leverage(leverage, symbol)
            except:
                pass
                
            # Открываем позицию
            side_text = "ЛОНГ 📈" if signal.action == "buy" else "ШОРТ 📉"
            self.log_signal.emit(f"🚀 Открываю {side_text} {coin}")
            
            if signal.action == "buy":
                order = self.exchange.create_market_buy_order(symbol, size)
            else:
                order = self.exchange.create_market_sell_order(symbol, size)
                
            # Ставим SL/TP
            try:
                params = {
                    'stopLoss': {'triggerPrice': signal.stop_loss},
                    'takeProfit': {'triggerPrice': signal.take_profit_1},
                }
                self.exchange.set_trading_stop(symbol, params)
            except:
                pass
                
            self.log_signal.emit(f"✅ {coin} {side_text} | Размер: {size} | SL: ${signal.stop_loss:,.2f}")
            self.trade_executed.emit(symbol, signal.action, size)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Ошибка: {e}")


class SmartAIPanel(QFrame):
    """Панель Smart AI бота"""
    analyze_clicked = Signal(str)  # symbol
    trade_clicked = Signal(dict)   # signal config
    stop_clicked = Signal()
    log_signal = Signal(str)  # для логов
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame#SmartAIPanel {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("SmartAIPanel")
        
        self.bot = None
        self.exchange = None
        self.auto_worker = None
        self.auto_timer = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("🧠 Smart AI Bot")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.status_lbl = QLabel("⚪ Готов")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888;")
        header.addWidget(self.status_lbl)
        layout.addLayout(header)
        
        # Description
        desc = QLabel("Глубокий анализ: MTF + Structure + Order Blocks + Sentiment")
        desc.setStyleSheet("font-size: 10px; color: #666;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # === ВЕРСИЯ БОТА ===
        version_row = QHBoxLayout()
        version_row.addWidget(self._label("Версия:"))
        self.version_combo = QComboBox()
        self.version_combo.addItem("v1 (базовый)", "v1")
        self.version_combo.addItem("v2 (улучшенный)", "v2")
        self.version_combo.setStyleSheet(self._combo_style())
        self.version_combo.setToolTip(
            "v1: MTF + Structure + Order Blocks\n"
            "v2: + Liquidations + OI + Volume Profile + BTC корреляция"
        )
        version_row.addWidget(self.version_combo)
        version_row.addStretch()
        layout.addLayout(version_row)
        
        # === РЕЖИМ ===
        mode_row = QHBoxLayout()
        mode_row.addWidget(self._label("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ручной", "Авто (одна монета)", "Авто (сканер)", "A/B тест (v1 vs v2)"])
        self.mode_combo.setStyleSheet(self._combo_style())
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)
        
        # Symbol selection (для ручного и авто-одна)
        sym_row = QHBoxLayout()
        sym_row.addWidget(self._label("Монета:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
        self.symbol_combo.setStyleSheet(self._combo_style())
        sym_row.addWidget(self.symbol_combo)
        sym_row.addStretch()
        layout.addLayout(sym_row)
        
        # === ВЫБОР МОНЕТ ДЛЯ СКАНЕРА ===
        self.coins_frame = QFrame()
        self.coins_frame.setStyleSheet("background: #12121a; border-radius: 8px; padding: 4px;")
        coins_layout = QVBoxLayout(self.coins_frame)
        coins_layout.setContentsMargins(8, 6, 8, 6)
        coins_layout.setSpacing(4)
        
        coins_header = QLabel("Монеты для сканирования:")
        coins_header.setStyleSheet("font-size: 10px; color: #888;")
        coins_layout.addWidget(coins_header)
        
        coins_grid = QGridLayout()
        coins_grid.setSpacing(4)
        self.coin_checks = {}
        for i, coin in enumerate(SCAN_COINS):
            cb = QCheckBox(coin)
            cb.setChecked(coin in ["BTC", "ETH", "SOL"])  # По умолчанию топ-3
            cb.setStyleSheet("color: white; font-size: 10px;")
            self.coin_checks[coin] = cb
            coins_grid.addWidget(cb, i // 5, i % 5)
        coins_layout.addLayout(coins_grid)
        
        self.coins_frame.hide()  # Скрыто по умолчанию
        layout.addWidget(self.coins_frame)
        
        # Risk settings
        risk_row = QHBoxLayout()
        risk_row.addWidget(self._label("Риск:"))
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.5, 10)
        self.risk_spin.setValue(2)
        self.risk_spin.setSuffix("%")
        self.risk_spin.setStyleSheet(self._spin_style())
        risk_row.addWidget(self.risk_spin)
        
        risk_row.addWidget(self._label("Плечо:"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 50)
        self.leverage_spin.setValue(10)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setStyleSheet(self._spin_style())
        risk_row.addWidget(self.leverage_spin)
        risk_row.addStretch()
        layout.addLayout(risk_row)
        
        # === НАСТРОЙКИ АВТО-РЕЖИМА ===
        self.auto_frame = QFrame()
        self.auto_frame.setStyleSheet("background: #12121a; border-radius: 8px;")
        auto_layout = QVBoxLayout(self.auto_frame)
        auto_layout.setContentsMargins(10, 8, 10, 8)
        auto_layout.setSpacing(6)
        
        # Мин. уверенность
        conf_row = QHBoxLayout()
        conf_row.addWidget(self._label("Мин. уверенность:"))
        self.min_conf_spin = QSpinBox()
        self.min_conf_spin.setRange(20, 80)
        self.min_conf_spin.setValue(40)
        self.min_conf_spin.setSuffix("%")
        self.min_conf_spin.setStyleSheet(self._spin_style())
        conf_row.addWidget(self.min_conf_spin)
        conf_row.addStretch()
        auto_layout.addLayout(conf_row)
        
        # Интервал сканирования
        interval_row = QHBoxLayout()
        interval_row.addWidget(self._label("Интервал:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 60)
        self.interval_spin.setValue(15)
        self.interval_spin.setSuffix(" мин")
        self.interval_spin.setStyleSheet(self._spin_style())
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        auto_layout.addLayout(interval_row)
        
        # Авто-торговля
        self.auto_trade_cb = QCheckBox("Автоматически открывать сделки")
        self.auto_trade_cb.setStyleSheet(f"""
            QCheckBox {{
                color: #FFA500; 
                font-size: 11px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #FFA500;
                background: transparent;
            }}
            QCheckBox::indicator:checked {{
                background: #FFA500;
                border: 2px solid #FFA500;
            }}
            QCheckBox::indicator:checked::after {{
                content: "✓";
            }}
        """)
        auto_layout.addWidget(self.auto_trade_cb)
        
        self.auto_frame.hide()
        layout.addWidget(self.auto_frame)
        
        # Analyze button
        self.analyze_btn = QPushButton("🔍 Анализировать рынок")
        self.analyze_btn.setFixedHeight(38)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none; border-radius: 8px;
                color: white; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #8B7CF7; }}
        """)
        self.analyze_btn.clicked.connect(self._on_analyze)
        layout.addWidget(self.analyze_btn)
        
        # Start/Stop Auto button
        self.auto_btn = QPushButton("🚀 Запустить авто-режим")
        self.auto_btn.setFixedHeight(38)
        self.auto_btn.setCursor(Qt.PointingHandCursor)
        self.auto_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                border: none; border-radius: 8px;
                color: white; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #00EEB5; }}
        """)
        self.auto_btn.clicked.connect(self._toggle_auto)
        self.auto_btn.hide()
        layout.addWidget(self.auto_btn)
        
        # Analysis results
        self.results_frame = QFrame()
        self.results_frame.setStyleSheet("background: #12121a; border-radius: 8px;")
        results_layout = QVBoxLayout(self.results_frame)
        results_layout.setContentsMargins(12, 10, 12, 10)
        results_layout.setSpacing(6)
        
        # Confidence bar
        conf_row = QHBoxLayout()
        conf_row.addWidget(self._label("Уверенность:"))
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setFixedHeight(16)
        self.confidence_bar.setStyleSheet("""
            QProgressBar {
                background: #2a2a35; border-radius: 8px; text-align: center;
                color: white; font-size: 10px;
            }
            QProgressBar::chunk { background: #6C5CE7; border-radius: 8px; }
        """)
        conf_row.addWidget(self.confidence_bar)
        results_layout.addLayout(conf_row)
        
        # Scores
        scores_row = QHBoxLayout()
        self.bull_lbl = QLabel("🟢 Bull: 0")
        self.bull_lbl.setStyleSheet(f"color: {COLORS['green']}; font-size: 11px;")
        scores_row.addWidget(self.bull_lbl)
        self.bear_lbl = QLabel("🔴 Bear: 0")
        self.bear_lbl.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px;")
        scores_row.addWidget(self.bear_lbl)
        scores_row.addStretch()
        results_layout.addLayout(scores_row)
        
        # MTF
        self.mtf_lbl = QLabel("MTF: —")
        self.mtf_lbl.setStyleSheet("color: #888; font-size: 11px;")
        results_layout.addWidget(self.mtf_lbl)
        
        # Structure
        self.structure_lbl = QLabel("Structure: —")
        self.structure_lbl.setStyleSheet("color: #888; font-size: 11px;")
        results_layout.addWidget(self.structure_lbl)
        
        # Signal
        self.signal_lbl = QLabel("📊 Сигнал: Ожидание анализа...")
        self.signal_lbl.setStyleSheet("color: white; font-size: 12px; font-weight: 600;")
        self.signal_lbl.setWordWrap(True)
        results_layout.addWidget(self.signal_lbl)
        
        # Levels
        self.levels_lbl = QLabel("")
        self.levels_lbl.setStyleSheet("color: #888; font-size: 10px;")
        self.levels_lbl.setWordWrap(True)
        results_layout.addWidget(self.levels_lbl)
        
        # Reason
        self.reason_lbl = QLabel("")
        self.reason_lbl.setStyleSheet("color: #666; font-size: 10px;")
        self.reason_lbl.setWordWrap(True)
        results_layout.addWidget(self.reason_lbl)
        
        layout.addWidget(self.results_frame)
        
        # Trade buttons
        self.btn_frame = QFrame()
        btn_layout = QHBoxLayout(self.btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        
        self.long_btn = QPushButton("📈 ЛОНГ")
        self.long_btn.setFixedHeight(40)
        self.long_btn.setCursor(Qt.PointingHandCursor)
        self.long_btn.setEnabled(False)
        self.long_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                border: none; border-radius: 8px;
                color: white; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #00EEB5; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.long_btn.clicked.connect(lambda: self._on_trade("buy"))
        btn_layout.addWidget(self.long_btn)
        
        self.short_btn = QPushButton("📉 ШОРТ")
        self.short_btn.setFixedHeight(40)
        self.short_btn.setCursor(Qt.PointingHandCursor)
        self.short_btn.setEnabled(False)
        self.short_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['red']};
                border: none; border-radius: 8px;
                color: white; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #FF8888; }}
            QPushButton:disabled {{ background: #2a2a35; color: #555; }}
        """)
        self.short_btn.clicked.connect(lambda: self._on_trade("sell"))
        btn_layout.addWidget(self.short_btn)
        
        layout.addWidget(self.btn_frame)
        
        # Current signal storage
        self.current_signal = None
        self.is_auto_running = False
        self.ab_worker = None  # Воркер для A/B теста
        
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 11px; color: #888;")
        return lbl
        
    def _combo_style(self) -> str:
        return """
            QComboBox {
                background: #2a2a35; border: 1px solid #444;
                border-radius: 6px; padding: 6px; color: white; font-size: 11px;
            }
        """
        
    def _spin_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background: #2a2a35; border: 1px solid #444;
                border-radius: 6px; padding: 6px; color: white; font-size: 11px;
                min-width: 70px;
            }
        """
    
    def _on_mode_changed(self, index: int):
        """Переключение режима"""
        # 0 = Ручной, 1 = Авто (одна монета), 2 = Авто (сканер), 3 = A/B тест
        is_manual = index == 0
        is_scanner = index == 2
        is_ab_test = index == 3
        
        # Показываем/скрываем элементы
        self.symbol_combo.setVisible(not is_scanner and not is_ab_test)
        self.coins_frame.setVisible(is_scanner or is_ab_test)
        self.auto_frame.setVisible(not is_manual)
        self.analyze_btn.setVisible(is_manual)
        self.auto_btn.setVisible(not is_manual)
        self.btn_frame.setVisible(is_manual)
        self.version_combo.setVisible(not is_ab_test)  # В A/B тесте обе версии
        
        # Обновляем текст кнопки
        if is_ab_test:
            self.auto_btn.setText("🔬 Запустить A/B тест")
        elif is_scanner:
            self.auto_btn.setText("🚀 Запустить сканер")
        else:
            self.auto_btn.setText("🚀 Запустить авто-режим")
        
    def _on_analyze(self):
        self.analyze_btn.setText("⏳ Анализирую...")
        self.analyze_btn.setEnabled(False)
        self.analyze_clicked.emit(self.symbol_combo.currentText())
        
    def _on_trade(self, side: str):
        if self.current_signal:
            config = {
                "symbol": self.symbol_combo.currentText(),
                "side": side,
                "signal": self.current_signal,
                "leverage": self.leverage_spin.value(),
                "risk_pct": self.risk_spin.value(),
            }
            self.trade_clicked.emit(config)
    
    def _toggle_auto(self):
        """Запуск/остановка авто-режима"""
        if self.is_auto_running:
            self._stop_auto()
        else:
            self._start_auto()
            
    def _start_auto(self):
        """Запускает авто-режим"""
        if not self.bot or not self.exchange:
            self.log_signal.emit("❌ Сначала подключитесь к бирже")
            return
            
        self.is_auto_running = True
        self.auto_btn.setText("⏹️ Остановить")
        self.auto_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['red']};
                border: none; border-radius: 8px;
                color: white; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #FF8888; }}
        """)
        self.status_lbl.setText("🟢 Авто")
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['green']};")
        
        # Запускаем первое сканирование
        self._run_scan()
        
        # Запускаем таймер
        interval_ms = self.interval_spin.value() * 60 * 1000
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self._run_scan)
        self.auto_timer.start(interval_ms)
        
        self.log_signal.emit(f"🚀 Авто-режим запущен (интервал: {self.interval_spin.value()} мин)")
        
    def _stop_auto(self):
        """Останавливает авто-режим"""
        self.is_auto_running = False
        
        if self.auto_timer:
            self.auto_timer.stop()
            self.auto_timer = None
            
        if self.auto_worker and self.auto_worker.isRunning():
            self.auto_worker.stop()
            self.auto_worker.wait(1000)  # Ждём макс 1 сек
            
        if self.ab_worker and self.ab_worker.isRunning():
            self.ab_worker.stop()
            self.ab_worker.wait(1000)  # Ждём макс 1 сек
            
        self.auto_btn.setText("🚀 Запустить авто-режим")
        self.auto_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                border: none; border-radius: 8px;
                color: white; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #00EEB5; }}
        """)
        self.status_lbl.setText("⚪ Готов")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #888;")
        
        self.log_signal.emit("⏹️ Авто-режим остановлен")
        
    def _run_scan(self):
        """Запускает сканирование"""
        # Защита от повторного запуска
        if self.auto_worker and self.auto_worker.isRunning():
            self.log_signal.emit("⚠️ Сканирование уже запущено")
            return
            
        if hasattr(self, 'ab_worker') and self.ab_worker and self.ab_worker.isRunning():
            self.log_signal.emit("⚠️ A/B тест уже запущен")
            return
            
        mode = self.mode_combo.currentIndex()
        is_ab_test = mode == 3
        
        # Определяем монеты для сканирования
        if mode >= 2:  # Сканер или A/B тест
            coins = [coin for coin, cb in self.coin_checks.items() if cb.isChecked()]
        else:  # Одна монета
            symbol = self.symbol_combo.currentText()
            coins = [symbol.split('/')[0]]
            
        if not coins:
            self.log_signal.emit("⚠️ Выберите монеты для сканирования")
            return
            
        settings = {
            'risk_pct': self.risk_spin.value(),
            'leverage': self.leverage_spin.value(),
            'min_confidence': self.min_conf_spin.value(),
            'auto_trade': self.auto_trade_cb.isChecked(),
        }
        
        if is_ab_test:
            # A/B тест — запускаем оба бота параллельно
            self._run_ab_test(coins, settings)
        else:
            # Обычный режим — используем выбранную версию
            bot = self._get_bot_by_version()
            self.auto_worker = AutoScanWorker(bot, self.exchange, coins, settings)
            self.auto_worker.log_signal.connect(self.log_signal.emit)
            self.auto_worker.scan_result.connect(self._on_scan_result)
            self.auto_worker.scan_complete.connect(self._on_scan_complete)
            self.auto_worker.start()
        
        self.status_lbl.setText("🔍 Сканирую...")
    
    def _get_bot_by_version(self):
        """Возвращает бота нужной версии"""
        version = self.version_combo.currentData()
        if version == "v2":
            from strategies.smart_ai_v2 import SmartAIBotV2
            return SmartAIBotV2(self.exchange)
        else:
            from strategies.smart_ai_bot import SmartAIBot
            return SmartAIBot(self.exchange)
    
    def _run_ab_test(self, coins: list, settings: dict):
        """Запускает A/B тест v1 vs v2 в отдельном потоке"""
        # Проверяем, не запущен ли уже воркер
        if hasattr(self, 'ab_worker') and self.ab_worker and self.ab_worker.isRunning():
            self.log_signal.emit("⚠️ A/B тест уже запущен")
            return
            
        self.ab_worker = ABTestWorker(self.exchange, coins, settings)
        self.ab_worker.log_signal.connect(self.log_signal.emit)
        self.ab_worker.result_signal.connect(self._on_ab_result)
        self.ab_worker.complete_signal.connect(self._on_scan_complete)
        self.ab_worker.start()
        
    def _on_ab_result(self, signal):
        """Обработка результата A/B теста"""
        if signal:
            self.update_analysis(signal)
        
    def _on_scan_result(self, symbol: str, signal):
        """Обработка результата сканирования"""
        # Обновляем UI с лучшим сигналом
        self.update_analysis(signal)
        
    def _on_scan_complete(self):
        """Сканирование завершено"""
        if self.is_auto_running:
            self.status_lbl.setText("🟢 Авто")
        else:
            self.status_lbl.setText("⚪ Готов")
    
    def set_bot(self, bot, exchange):
        """Устанавливает бота и биржу"""
        self.bot = bot
        self.exchange = exchange
        # Для v2 создаём отдельный экземпляр при необходимости
        self.bot_v1 = bot
        try:
            from strategies.smart_ai_v2 import SmartAIBotV2
            self.bot_v2 = SmartAIBotV2(exchange)
        except:
            self.bot_v2 = bot

    def update_analysis(self, signal):
        """Обновляет результаты анализа"""
        self.current_signal = signal
        self.analyze_btn.setText("🔍 Анализировать рынок")
        self.analyze_btn.setEnabled(True)
        
        if not signal:
            self.signal_lbl.setText("❌ Ошибка анализа")
            return
            
        analysis = signal.analysis
        
        # Confidence
        self.confidence_bar.setValue(signal.confidence)
        if signal.confidence >= 50:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { background: #2a2a35; border-radius: 8px; text-align: center; color: white; }
                QProgressBar::chunk { background: #00D9A5; border-radius: 8px; }
            """)
        elif signal.confidence >= 25:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { background: #2a2a35; border-radius: 8px; text-align: center; color: white; }
                QProgressBar::chunk { background: #FFA500; border-radius: 8px; }
            """)
        else:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { background: #2a2a35; border-radius: 8px; text-align: center; color: white; }
                QProgressBar::chunk { background: #FF6B6B; border-radius: 8px; }
            """)
        
        # Scores
        self.bull_lbl.setText(f"🟢 Bull: {analysis.bull_score}")
        self.bear_lbl.setText(f"🔴 Bear: {analysis.bear_score}")
        
        # MTF
        align_icon = "✅" if analysis.mtf_alignment else "⚠️"
        self.mtf_lbl.setText(f"MTF: {align_icon} HTF:{analysis.htf_trend} | MTF:{analysis.mtf_trend} | LTF:{analysis.ltf_trend}")
        
        # Structure
        bos_str = f"BOS:{analysis.last_bos}" if analysis.last_bos else ""
        choch_str = f"CHoCH:{analysis.last_choch}" if analysis.last_choch else ""
        self.structure_lbl.setText(f"Structure: {bos_str} {choch_str} | RSI:{analysis.rsi:.0f}")
        
        # Signal
        if signal.action == "buy":
            self.signal_lbl.setText(f"📈 ЛОНГ рекомендован ({signal.confidence}%)")
            self.signal_lbl.setStyleSheet(f"color: {COLORS['green']}; font-size: 12px; font-weight: 600;")
            self.long_btn.setEnabled(True)
            self.short_btn.setEnabled(False)
        elif signal.action == "sell":
            self.signal_lbl.setText(f"📉 ШОРТ рекомендован ({signal.confidence}%)")
            self.signal_lbl.setStyleSheet(f"color: {COLORS['red']}; font-size: 12px; font-weight: 600;")
            self.long_btn.setEnabled(False)
            self.short_btn.setEnabled(True)
        else:
            self.signal_lbl.setText(f"⏸️ Ожидание ({signal.confidence}%)")
            self.signal_lbl.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
            self.long_btn.setEnabled(False)
            self.short_btn.setEnabled(False)
            
        # Levels
        if signal.action != "wait":
            self.levels_lbl.setText(
                f"Entry: ${signal.entry_price:,.2f} | SL: ${signal.stop_loss:,.2f}\n"
                f"TP1: ${signal.take_profit_1:,.2f} | TP2: ${signal.take_profit_2:,.2f} | TP3: ${signal.take_profit_3:,.2f}"
            )
        else:
            self.levels_lbl.setText("")
            
        # Reason
        self.reason_lbl.setText(signal.reason)
        
    def set_enabled(self, enabled: bool):
        self.analyze_btn.setEnabled(enabled)
    
    def stop_all_workers(self):
        """Останавливает все воркеры панели"""
        if self.auto_timer:
            self.auto_timer.stop()
            self.auto_timer = None
        
        if self.auto_worker and self.auto_worker.isRunning():
            self.auto_worker.stop()
            self.auto_worker.wait(1000)
        
        if self.ab_worker and self.ab_worker.isRunning():
            self.ab_worker.stop()
            self.ab_worker.wait(1000)
        
        self.is_auto_running = False
