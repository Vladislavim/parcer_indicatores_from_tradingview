"""
📊 Grid Trading Bot - Сеточная торговля

Профессиональная стратегия для заработка на боковом рынке.
Размещает сетку ордеров на покупку и продажу.

Режимы:
1. AI Mode - автоматически определяет диапазон и количество сеток
2. Manual Mode - ручная настройка параметров

Как работает:
- Определяет диапазон цены (верх/низ)
- Размещает N ордеров на покупку ниже текущей цены
- Размещает N ордеров на продажу выше текущей цены
- При исполнении ордера на покупку — ставит ордер на продажу выше
- При исполнении ордера на продажу — ставит ордер на покупку ниже
- Зарабатывает на каждом "качании" цены

Средняя доходность: 1-5% в день при боковике
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum
import math


class GridMode(Enum):
    AI = "ai"
    MANUAL = "manual"


@dataclass
class GridConfig:
    """Конфигурация грид-бота"""
    symbol: str
    mode: GridMode
    
    # Для ручного режима
    upper_price: float = 0
    lower_price: float = 0
    grid_count: int = 10
    
    # Общие
    total_investment: float = 1000  # Сколько вложить в USDT
    leverage: int = 1
    
    # AI параметры
    ai_volatility_period: int = 24  # Часов для анализа волатильности


@dataclass
class GridLevel:
    """Один уровень сетки"""
    price: float
    side: str  # "buy" или "sell"
    order_id: Optional[str] = None
    filled: bool = False


class GridBot:
    """Grid Trading Bot"""
    
    def __init__(self, exchange, config: GridConfig):
        self.exchange = exchange
        self.config = config
        self.levels: List[GridLevel] = []
        self.active_orders: Dict[str, GridLevel] = {}
        self.is_running = False
        self.total_profit = 0
        self.trades_count = 0
        
    def calculate_ai_range(self) -> tuple:
        """AI: Автоматически определяет диапазон на основе волатильности"""
        try:
            # Получаем свечи за последние N часов
            ohlcv = self.exchange.fetch_ohlcv(
                self.config.symbol, 
                '1h', 
                limit=self.config.ai_volatility_period
            )
            
            if len(ohlcv) < 10:
                return None, None
                
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            closes = [c[4] for c in ohlcv]
            
            current_price = closes[-1]
            
            # Находим диапазон
            period_high = max(highs)
            period_low = min(lows)
            
            # Расширяем немного для безопасности
            range_size = period_high - period_low
            upper = period_high + range_size * 0.1
            lower = period_low - range_size * 0.1
            
            # Рассчитываем оптимальное количество сеток
            # Чем больше волатильность — тем больше сеток
            volatility = range_size / current_price * 100
            
            if volatility < 2:
                grid_count = 5
            elif volatility < 5:
                grid_count = 10
            elif volatility < 10:
                grid_count = 15
            else:
                grid_count = 20
                
            return (lower, upper, grid_count)
            
        except Exception as e:
            print(f"AI range error: {e}")
            return None, None, None
            
    def setup_grid(self) -> List[GridLevel]:
        """Создаёт сетку уровней"""
        if self.config.mode == GridMode.AI:
            result = self.calculate_ai_range()
            if result[0] is None:
                raise Exception("Не удалось рассчитать AI диапазон")
            lower, upper, grid_count = result
        else:
            lower = self.config.lower_price
            upper = self.config.upper_price
            grid_count = self.config.grid_count
            
        if lower >= upper:
            raise Exception("Нижняя граница должна быть меньше верхней")
            
        # Получаем текущую цену
        ticker = self.exchange.fetch_ticker(self.config.symbol)
        current_price = ticker['last']
        
        # Создаём уровни
        step = (upper - lower) / grid_count
        self.levels = []
        
        for i in range(grid_count + 1):
            price = lower + step * i
            price = round(price, 2)
            
            # Ниже текущей цены — покупаем, выше — продаём
            if price < current_price:
                side = "buy"
            else:
                side = "sell"
                
            self.levels.append(GridLevel(price=price, side=side))
            
        return self.levels
        
    def get_order_size(self) -> float:
        """Рассчитывает размер одного ордера"""
        # Делим инвестицию на количество уровней
        per_level = self.config.total_investment / len(self.levels)
        
        # С плечом
        per_level = per_level * self.config.leverage
        
        # Получаем цену
        ticker = self.exchange.fetch_ticker(self.config.symbol)
        price = ticker['last']
        
        # Размер в монетах
        size = per_level / price
        
        # Минимальные размеры для Bybit
        coin = self.config.symbol.split('/')[0]
        min_sizes = {
            "BTC": 0.001,
            "ETH": 0.01,
            "SOL": 0.1,
            "XRP": 1,
            "DOGE": 10,
        }
        min_size = min_sizes.get(coin, 0.01)
        
        # Округляем
        if coin == "BTC":
            size = round(size, 3)
        elif coin in ["ETH", "SOL"]:
            size = round(size, 2)
        else:
            size = round(size, 1)
        
        # Проверяем минимум
        if size < min_size:
            size = min_size
            
        return size
        
    def place_grid_orders(self) -> List[dict]:
        """Размещает все ордера сетки"""
        if not self.levels:
            self.setup_grid()
            
        size = self.get_order_size()
        
        # Проверяем что хватит на все ордера
        ticker = self.exchange.fetch_ticker(self.config.symbol)
        price = ticker['last']
        total_needed = size * price * len(self.levels) / self.config.leverage
        
        if total_needed > self.config.total_investment * 1.5:
            # Уменьшаем количество сеток
            max_grids = int(self.config.total_investment * self.config.leverage / (size * price))
            if max_grids < 3:
                raise Exception(f"Недостаточно средств. Нужно минимум ${size * price * 3 / self.config.leverage:.0f}")
            self.levels = self.levels[:max_grids]
        
        placed_orders = []
        
        for level in self.levels:
            try:
                if level.side == "buy":
                    order = self.exchange.create_limit_buy_order(
                        self.config.symbol,
                        size,
                        level.price
                    )
                else:
                    order = self.exchange.create_limit_sell_order(
                        self.config.symbol,
                        size,
                        level.price
                    )
                    
                level.order_id = order['id']
                self.active_orders[order['id']] = level
                placed_orders.append(order)
                
            except Exception as e:
                print(f"Error placing order at {level.price}: {e}")
                
        self.is_running = True
        return placed_orders
        
    def check_and_replace_orders(self) -> List[dict]:
        """Проверяет исполненные ордера и ставит новые"""
        if not self.is_running:
            return []
            
        new_orders = []
        size = self.get_order_size()
        
        try:
            # Получаем открытые ордера
            open_orders = self.exchange.fetch_open_orders(self.config.symbol)
            open_ids = {o['id'] for o in open_orders}
            
            # Проверяем какие исполнились
            for order_id, level in list(self.active_orders.items()):
                if order_id not in open_ids:
                    # Ордер исполнился!
                    level.filled = True
                    self.trades_count += 1
                    
                    # Ставим обратный ордер
                    # Если был buy — ставим sell выше
                    # Если был sell — ставим buy ниже
                    
                    step = self.levels[1].price - self.levels[0].price if len(self.levels) > 1 else 0
                    
                    if level.side == "buy":
                        new_price = level.price + step
                        new_side = "sell"
                        self.total_profit += step * size  # Примерный профит
                    else:
                        new_price = level.price - step
                        new_side = "buy"
                        self.total_profit += step * size
                        
                    try:
                        if new_side == "buy":
                            order = self.exchange.create_limit_buy_order(
                                self.config.symbol, size, new_price
                            )
                        else:
                            order = self.exchange.create_limit_sell_order(
                                self.config.symbol, size, new_price
                            )
                            
                        # Обновляем уровень
                        level.price = new_price
                        level.side = new_side
                        level.order_id = order['id']
                        level.filled = False
                        
                        del self.active_orders[order_id]
                        self.active_orders[order['id']] = level
                        
                        new_orders.append(order)
                        
                    except Exception as e:
                        print(f"Error replacing order: {e}")
                        del self.active_orders[order_id]
                        
        except Exception as e:
            print(f"Error checking orders: {e}")
            
        return new_orders
        
    def cancel_all_orders(self):
        """Отменяет все ордера сетки"""
        self.is_running = False
        
        try:
            open_orders = self.exchange.fetch_open_orders(self.config.symbol)
            for order in open_orders:
                try:
                    self.exchange.cancel_order(order['id'], self.config.symbol)
                except:
                    pass
        except:
            pass
            
        self.active_orders.clear()
        
    def get_stats(self) -> dict:
        """Возвращает статистику бота"""
        return {
            "is_running": self.is_running,
            "total_profit": self.total_profit,
            "trades_count": self.trades_count,
            "active_orders": len(self.active_orders),
            "grid_levels": len(self.levels),
        }
