import sys
from PySide6.QtWidgets import QApplication

from ui.theme import apply_theme
from ui.premium_main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("LocalSignals")
    app.setApplicationName("LocalSignals Pro")

    apply_theme(app)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()