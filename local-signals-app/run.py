"""Запуск только терминала Bybit."""
import os
import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.terminal_window import BybitTerminal


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)

    icon_path = os.path.join(os.path.dirname(__file__), "content", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setFont(QFont("Segoe UI", 10))

    window = BybitTerminal()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
