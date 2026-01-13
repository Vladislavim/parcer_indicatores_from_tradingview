"""Local Signals Pro - Запуск"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Стандартный режим: отдельные окна
from ui.modern_app import run

# Альтернатива: единое окно (сигналы + терминал вместе)
# from ui.unified_app import run

if __name__ == "__main__":
    run()