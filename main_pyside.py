import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QIcon
 
from src.main_window import FinanceFugue

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
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()