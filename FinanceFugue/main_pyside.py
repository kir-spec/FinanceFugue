import sys
from PySide6.QtWidgets import QApplication

from src import APP_NAME, VERSION
from src.main_window import FinanceFugueWindow
from src.theme import MESSAGEBOX_STYLESHEET, create_dark_palette
from src.ui.icon_loader import load_app_icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    app.setPalette(create_dark_palette())
    app.setStyleSheet(MESSAGEBOX_STYLESHEET)
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = FinanceFugueWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
