import sys
from PySide6.QtWidgets import QApplication

from ui.theme import apply_theme
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("LocalSignals")
    app.setApplicationName("LocalSignals")

    apply_theme(app)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
