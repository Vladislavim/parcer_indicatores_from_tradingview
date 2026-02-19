"""
Управление конфигурацией приложения
"""
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path


class Config:
    """Класс для работы с конфигурацией"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.data: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> bool:
        """Загрузить конфигурацию из файла"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                return True
            else:
                # Создаём дефолтную конфигурацию
                self.data = self.get_default_config()
                self.save()
                return False
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            self.data = self.get_default_config()
            return False
    
    def save(self) -> bool:
        """Сохранить конфигурацию в файл"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение из конфига"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Установить значение в конфиге"""
        self.data[key] = value
    
    def get_exchange_type(self) -> str:
        """Получить тип биржи"""
        return self.get("exchange", "BYBIT_DEMO")
    
    def get_api_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Получить API ключи"""
        api_key = self.get("api_key")
        api_secret = self.get("api_secret")
        
        # Проверяем что ключи не дефолтные
        if api_key and "YOUR_" not in api_key:
            return api_key, api_secret
        return None, None
    
    def is_demo_mode(self) -> bool:
        """Проверить используется ли demo режим"""
        return self.get("demo_mode", True)
    
    def get_default_leverage(self) -> int:
        """Получить дефолтное плечо"""
        return self.get("default_leverage", 10)
    
    def get_risk_per_trade(self) -> float:
        """Получить риск на сделку в %"""
        return self.get("risk_per_trade", 2.0)
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Получить дефолтную конфигурацию"""
        return {
            "exchange": "BYBIT_DEMO",
            "api_key": "YOUR_BYBIT_DEMO_API_KEY",
            "api_secret": "YOUR_BYBIT_DEMO_SECRET_KEY",
            "demo_mode": True,
            "default_leverage": 10,
            "risk_per_trade": 2.0
        }


# Глобальный экземпляр конфига
config = Config()
