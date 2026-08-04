import sys
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox

from src import APP_NAME, VERSION
from src.main_window import FinanceFugueWindow
from src.theme import MESSAGEBOX_STYLESHEET, create_dark_palette
from src.ui.icon_loader import load_app_icon
from src.logger import get_logger
from src.utils.crash_handler import write_crash, install as install_crash_handler


def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger("CrashReporter")
    logger.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))

    # Записываем crash-файл независимо от UI-состояния.
    crash_path = write_crash(exc_type, exc_value, exc_traceback)

    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    try:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Критическая ошибка")
        msg_box.setText("Произошла непредвиденная ошибка. Приложение может работать нестабильно.")
        msg_box.setInformativeText(
            f"{exc_type.__name__}: {exc_value}\n\n"
            f"Лог: {crash_path or 'logs/'}."
        )
        msg_box.setDetailedText(error_msg)
        msg_box.setStyleSheet(MESSAGEBOX_STYLESHEET)
        msg_box.exec()
    except Exception:
        # Если даже QMessageBox не открывается — отдаём в stderr.
        sys.stderr.write(f"CRITICAL ERROR:\n{error_msg}\n")


def main():
    install_crash_handler()  # устанавливает Qt-message handler
    sys.excepthook = global_exception_handler
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
