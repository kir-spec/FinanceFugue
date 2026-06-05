import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QIcon

from src.main_window import FinanceFugue
from src.logger import get_logger

logger = get_logger("main")

def create_desktop_shortcut(app_name, exe_path, icon_path):
    """
    Создает ярлык программы на рабочем столе.
    Поддерживает Windows. Для других ОС требуется дополнительная логика.
    """
    try:
        import platform
        if platform.system() == "Windows":
            import winshell
            from win32com.client import Dispatch
            
            desktop = winshell.desktop()
            link_filepath = os.path.join(desktop, f"{app_name}.lnk")
            
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(link_filepath)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = os.path.dirname(exe_path)
            shortcut.IconLocation = icon_path
            shortcut.save()
            logger.info(f"Ярлык '{app_name}' создан на рабочем столе.")
            return True
        else:
            logger.warning("Создание ярлыков на рабочем столе поддерживается только для Windows.")
            return False
    except ImportError:
        logger.error("Для создания ярлыков на Windows необходимы 'winshell' и 'pywin32'. Установите их: pip install winshell pypiwin32.")
        return False
    except Exception as e:
        logger.error(f"Ошибка при создании ярлыка на рабочем столе: {e}", exc_info=True)
        return False

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)
    
    app.setStyleSheet("""
        QMessageBox {
            background-color: #1E1E1E;
        }
        QMessageBox QLabel {
            color: #FFFFFF;
        }
        QMessageBox QPushButton {
            background-color: #2D2D2D;
            color: #FFFFFF;
            border: 1px solid #3D3D3D;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3D3D3D;
        }
    """)
    
    app.setWindowIcon(QIcon("images/FinanceFugue.ico"))
    
    window = FinanceFugue()
    window.show()

    # Проверяем и создаем ярлык, если установлено в настройках первого запуска
    if window.app_settings.get('create_shortcut', False):
        app_name = "FinanceFugue"
        # exe_path: Предполагаем, что это py-файл или собранный exe.
        # Для .py файла запускаем python с этим файлом.
        # Для .exe - сам exe.
        # Проще всего определить текущий исполняемый файл.
        exe_path = sys.executable # Используем текущий интерпретатор
        if getattr(sys, 'frozen', False): # Если это скомпилированный exe
            exe_path = sys.executable
        else: # Если это Python скрипт
            exe_path = os.path.abspath(sys.argv[0])

        icon_path = os.path.abspath("images/FinanceFugue.ico")
        
        if create_desktop_shortcut(app_name, exe_path, icon_path):
            # После успешного создания ярлыка, снимаем флаг в настройках
            # чтобы не пытаться создать его снова при каждом запуске
            window.app_settings['create_shortcut'] = False
            window.save_settings()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()