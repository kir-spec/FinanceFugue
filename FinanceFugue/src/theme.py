"""Единый источник стилей FinanceFugue.

Централизация: все QSS-строки живут здесь. Виджеты и диалоги только
вызывают setStyleSheet(CONSTANT) или setObjectName() для вариантов кнопок.
"""
from PySide6.QtGui import QPalette, QColor

# --- Палитра ---
COLOR_BG = "#1E1E1E"
COLOR_BG_PANEL = "#252525"
COLOR_BG_INPUT = "#333333"
COLOR_BORDER = "#3D3D3D"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_MUTED = "#DDDDDD"
COLOR_TEXT_DIM = "#AAAAAA"
COLOR_ACCENT = "#00D1FF"
COLOR_SUCCESS = "#28A745"
COLOR_DANGER = "#DC3545"
COLOR_DANGER_HOVER = "#C82333"
COLOR_PRIMARY = "#0078D7"

# --- Базовые блоки (собираются в полные таблицы стилей) ---
_BTN_BASE = """
    QPushButton {
        background-color: #2D2D2D; color: #FFFFFF;
        border: 1px solid #3D3D3D; border-radius: 4px;
    }
    QPushButton:hover { background-color: #3D3D3D; }
    QPushButton:pressed { background-color: #4D4D4D; }
"""
_BTN_COMPACT = """
    QPushButton {
        background-color: #2D2D2D; color: #FFFFFF;
        border: 1px solid #3D3D3D; padding: 4px;
        border-radius: 3px; font-size: 10pt;
    }
    QPushButton:hover { background-color: #3D3D3D; }
"""
_BTN_DANGER_COMPACT = """
    QPushButton {
        background-color: #DC3545; color: white;
        border: 1px solid #DC3545; padding: 4px;
        border-radius: 3px; font-size: 10pt;
    }
    QPushButton:hover { background-color: #C82333; }
    QPushButton#archiveButton {
        background-color: #17A2B8; color: white;
    }
    QPushButton#archiveButton:hover {
        background-color: #138496;
    }
"""
_INPUT_BASE = """
    QLineEdit, QTextEdit, QComboBox {
        background-color: #333333; color: #FFFFFF;
        border: 1px solid #444444; padding: 6px; border-radius: 3px; font-size: 11pt;
    }
"""
_CHECKBOX = """
    QCheckBox { color: #DDDDDD; font-size: 11pt; padding: 3px; }
    QCheckBox::indicator {
        width: 16px; height: 16px;
        border: 2px solid #555555; background: #222222; border-radius: 3px;
    }
    QCheckBox::indicator:checked { border: 2px solid #00D1FF; background: #00D1FF; }
"""
_GROUPBOX = """
    QGroupBox {
        color: #FFFFFF; border: 1px solid #3D3D3D; border-radius: 5px;
        margin-top: 10px; font-size: 13pt; font-weight: bold; padding-top: 15px;
    }
    QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top center;
        padding: 0 5px; color: #00D1FF;
    }
    QGroupBox#DatabaseGroup { background-color: #1F2630; border-color: #30363D; }
    QGroupBox#SettingsGroup { background-color: #2A2A2A; border-color: #3D3D3D; }
"""
_LISTWIDGET = """
    QListWidget {
        background-color: #252525; color: #FFFFFF;
        border: 1px solid #3D3D3D; font-size: 11pt;
    }
"""

DIALOG_STYLESHEET = f"""
    QDialog {{ background-color: {COLOR_BG}; }}
    QLabel {{ color: {COLOR_TEXT_MUTED}; font-size: 11pt; }}
    QTextEdit {{
        background-color: {COLOR_BG_PANEL}; color: {COLOR_TEXT_MUTED};
        border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-size: 11pt;
    }}
    QPushButton {{
        background-color: #2D2D2D; color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER}; padding: 8px 16px; border-radius: 4px;
    }}
    QPushButton:hover {{ background-color: #3D3D3D; }}
    QCheckBox {{ color: {COLOR_TEXT}; font-size: 11pt; }}
    {_INPUT_BASE}
    {_CHECKBOX}
    {_GROUPBOX}
    {_LISTWIDGET}
    QPushButton#accentButton {{
        background-color: {COLOR_ACCENT}; color: #000000; font-weight: bold;
    }}
    QPushButton#successButton {{
        background-color: {COLOR_SUCCESS}; color: white; font-weight: bold;
    }}
    QPushButton#dangerButton {{
        background-color: {COLOR_DANGER}; color: white; font-weight: bold;
    }}
    QPushButton#primaryButton {{
        background-color: {COLOR_PRIMARY}; color: white; font-weight: bold;
    }}
"""

SETTINGS_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QLabel { color: #FFFFFF; font-size: 13pt; padding: 5px; }
    QPushButton { padding: 10px; font-size: 13pt; }
"""

FOLDER_IMPORT_DIALOG_STYLESHEET = DIALOG_STYLESHEET

FIRST_RUN_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QGroupBox { border: 2px solid #444444; }
    QGroupBox::title { subcontrol-position: top left; left: 10px; padding: 0 10px; }
    QRadioButton { color: #FFFFFF; font-size: 11pt; padding: 5px; }
    QPushButton { padding: 10px 20px; font-size: 13pt; }
"""

FILE_MANAGER_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QTreeWidget {
        background-color: #252525; color: #FFFFFF;
        border: 1px solid #3D3D3D; font-size: 11pt;
    }
"""

ABOUT_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QTabWidget::pane { border: 1px solid #3D3D3D; background: #252525; }
    QTabBar::tab {
        background: #2D2D2D; color: #DDDDDD; padding: 8px 14px;
        border: 1px solid #3D3D3D; margin-right: 2px;
    }
    QTabBar::tab:selected { background: #3D3D3D; color: #00D1FF; }
"""

EULA_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QPushButton#acceptBtn { background-color: #28A745; font-weight: bold; }
"""

CLIENT_SETTINGS_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QGroupBox#exportGroup {
        border: 1px solid #3D3D3D; border-radius: 5px;
        margin-top: 10px; font-weight: bold; padding-top: 10px;
    }
    QGroupBox#exportGroup::title { color: #00D1FF; }
"""

ORDERS_EXPORT_DIALOG_STYLESHEET = DIALOG_STYLESHEET

PAYMENTS_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QDialog { font-size: 11pt; }
"""

MESSAGEBOX_STYLESHEET = """
    QMessageBox { background-color: #1E1E1E; }
    QMessageBox QLabel { color: #FFFFFF; }
    QMessageBox QPushButton {
        background-color: #2D2D2D; color: #FFFFFF;
        border: 1px solid #3D3D3D; padding: 8px 12px; border-radius: 4px; font-size: 11pt;
    }
    QMessageBox QPushButton:hover { background-color: #3D3D3D; }
    QToolTip {
        background-color: #2D2D2D;
        color: #FFFFFF;
        border: 1px solid #555555;
        padding: 4px;
        font-size: 11pt;
    }
"""

MAIN_WINDOW_STYLESHEET = f"""
    QMainWindow {{ background-color: {COLOR_BG}; }}
    QLabel {{ color: {COLOR_TEXT}; border: none; }}
    QPushButton {{
        background-color: #2D2D2D; color: {COLOR_TEXT};
        padding: 5px 10px; border-radius: 4px;
        border: 1px solid {COLOR_BORDER}; font-size: 11pt;
    }}
    QPushButton:hover {{ background-color: #3D3D3D; }}
    QPushButton:pressed {{ background-color: #4D4D4D; }}
    QPushButton#primaryButton {{
        background-color: {COLOR_PRIMARY}; color: white; font-weight: bold;
    }}
    QListWidget {{
        background-color: #252525; color: #FFFFFF;
        border: 1px solid #3D3D3D; outline: none; font-size: 11pt;
    }}
    QListWidget::item {{ padding: 4px 8px; border-bottom: 1px solid #333333; }}
    QListWidget::item:hover {{ background-color: #333333; }}
    QListWidget::item:selected {{ background-color: #0078D7; color: white; }}
    {_INPUT_BASE}
    QComboBox::drop-down {{
        border-left: 1px solid #444444; background: #3D3D3D;
        width: 25px; border-top-right-radius: 3px; border-bottom-right-radius: 3px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 6px solid transparent; border-right: 6px solid transparent;
        border-top: 6px solid #00D1FF;
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background-color: #252525; width: 12px; }}
    QScrollBar::handle:vertical {{ background-color: #444444; border-radius: 6px; }}
    QScrollBar::handle:vertical:hover {{ background-color: #555555; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ background: none; }}
    {_CHECKBOX}
    QTextEdit {{
        background-color: #252525; color: #FFFFFF;
        border: 1px solid #444444; padding: 6px; border-radius: 3px; font-size: 11pt;
    }}
"""

# --- Order / file widgets ---
ORDER_FRAME_STYLE = """
    QFrame#OrderCard {
        background-color: #2A2A2A; border-radius: 8px;
        border: 1px solid #3D3D3D; margin-bottom: 5px;
    }
"""

SEPARATOR_LINE_STYLE = (
    "background-color: #3D3D3D; min-height: 1px; max-height: 1px; "
    "border: none; margin: 3px 0;"
)

ORDER_TITLE_STYLE = "font-weight: bold; color: #00D1FF; font-size: 16pt;"
FIELD_LABEL_STYLE = "color: #DDDDDD; font-size: 11pt; font-weight: bold;"
DEADLINE_LABEL_STYLE = "color: #FFFFFF; font-size: 13pt; font-weight: bold;"
START_DATE_LABEL_STYLE = "color: #28A745; font-size: 13pt; font-weight: bold;"

TRANSPARENT_FRAME_STYLE = "QFrame { background-color: transparent; border: none; }"
SCROLL_AREA_TRANSPARENT_STYLE = "border: none; background-color: transparent;"

ORDER_TOGGLE_BTN_STYLE = """
    QPushButton {
        background-color: #3D3D3D; color: #00D1FF;
        border: 1px solid #555555; border-radius: 12px;
        font-size: 13pt; font-weight: bold; padding: 0px;
    }
    QPushButton:hover {
        background-color: #4D4D4D; color: #FFFFFF; border-color: #00D1FF;
    }
"""

ORDER_DELETE_BTN_STYLE = """
    QPushButton {
        background-color: #6C757D; color: white; border: none;
        padding: 4px 8px; border-radius: 4px; font-size: 10pt;
    }
    QPushButton:hover { background-color: #5A6268; }
"""

ORDER_ARCHIVE_BTN_STYLE = """
    QPushButton {
        background-color: #17A2B8; color: white; border: none;
        padding: 4px 8px; border-radius: 4px; font-size: 10pt;
    }
    QPushButton:hover { background-color: #138496; }
"""

ORDER_ARCHIVE_BTN_STYLE = """
    QPushButton {
        background-color: #17A2B8; color: white; border: none;
        padding: 4px 8px; border-radius: 4px; font-size: 10pt;
    }
    QPushButton:hover { background-color: #138496; }
"""

ORDER_STATUS_CHECKBOX_STYLE = """
    QCheckBox { color: #DDDDDD; font-size: 11pt; padding-left: 5px; }
    QCheckBox::indicator { width: 16px; height: 16px; }
    QCheckBox::indicator:unchecked { border: 2px solid #555555; background: #222222; }
    QCheckBox::indicator:checked { border: 2px solid #28A745; background: #28A745; }
"""

PAYMENTS_FRAME_STYLE = """
    QFrame {
        border: 1px solid #3D3D3D; border-radius: 6px; background-color: #2D2D2D;
    }
    QLabel { border: none; background: transparent; }
    QPushButton { border-radius: 4px; }
"""

PAYMENT_ADD_BTN_STYLE = """
    QPushButton {
        background-color: #28A745; color: white; font-weight: bold;
        padding: 6px 10px; font-size: 11pt;
    }
    QPushButton:hover { background-color: #218838; }
"""

PAYMENT_HISTORY_BTN_STYLE = """
    QPushButton {
        background-color: #0078D7; color: white; font-weight: bold;
        padding: 6px 10px; border-radius: 4px; font-size: 11pt;
    }
    QPushButton:hover { background-color: #0056B3; }
"""

CLIENT_ARCHIVE_BTN_STYLE = """
    QPushButton {
        background-color: #17A2B8; color: white; border: none;
        padding: 6px 14px; border-radius: 4px; font-weight: bold;
    }
    QPushButton:hover { background-color: #138496; }
"""

VERTICAL_SEPARATOR_STYLE = (
    "background-color: #3D3D3D; min-width: 1px; max-width: 1px; border: none; margin: 0 5px;"
)

FILES_SECTION_LABEL_STYLE = "font-weight: bold; color: #DDDDDD; font-size: 12pt;"
FOLDER_ACCESS_LABEL_STYLE = "color: #DDDDDD; font-size: 11pt;"

NEW_ORDER_DIALOG_STYLESHEET = DIALOG_STYLESHEET + """
    QLabel { color: #FFFFFF; font-size: 11pt; }
    QFormLayout { spacing: 10px; }
    QGroupBox {
        color: #FFFFFF; border: 1px solid #444444; border-radius: 5px;
        margin-top: 10px; font-size: 12pt; font-weight: bold; padding-top: 10px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
"""

ADD_PAYMENT_DIALOG_STYLESHEET = PAYMENTS_DIALOG_STYLESHEET

SUCCESS_DIALOG_BUTTON_STYLE = """
    QPushButton {
        background-color: #28A745; color: white; font-weight: bold;
        padding: 8px 15px; border-radius: 4px;
    }
    QPushButton:hover { background-color: #218838; }
"""

CANCEL_DIALOG_BUTTON_STYLE = """
    QPushButton {
        background-color: #6C757D; color: white;
        padding: 8px 15px; border-radius: 4px;
    }
    QPushButton:hover { background-color: #5A6268; }
"""

NOTES_SAVE_BUTTON_STYLE = """
    QPushButton {
        background-color: #28A745; color: white;
        padding: 5px 12px; border-radius: 4px; font-weight: bold;
    }
    QPushButton:hover { background-color: #218838; }
    QPushButton:pressed { background-color: #1E7E34; }
"""

NOTES_CANCEL_BUTTON_STYLE = """
    QPushButton {
        background-color: #DC3545; color: white;
        padding: 5px 12px; border-radius: 4px; font-weight: bold;
    }
    QPushButton:hover { background-color: #C82333; }
    QPushButton:pressed { background-color: #BD2130; }
"""

CREATE_ORDER_BUTTON_STYLE = """
    QPushButton {
        background-color: #28A745; color: white;
        padding: 6px 14px; font-weight: bold; border-radius: 4px;
    }
    QPushButton:hover { background-color: #218838; }
    QPushButton:pressed { background-color: #1E7E34; }
"""

NOTES_EDIT_STYLE = f"""
    QTextEdit {{
        background-color: {COLOR_BG_PANEL}; color: {COLOR_TEXT};
        border: 2px solid #444444; padding: 8px; border-radius: 4px; font-size: 11pt;
    }}
    QTextEdit:focus {{ border-color: {COLOR_PRIMARY}; }}
"""

ORDERS_SECTION_STYLE = f"""
    font-size: 14pt; font-weight: bold; color: {COLOR_TEXT_MUTED};
    margin-top: 10px; padding: 5px 0; border-bottom: 2px solid {COLOR_BORDER};
"""

NO_ORDERS_STYLE = (
    f"color: {COLOR_TEXT_MUTED}; font-style: italic; padding: 20px; "
    f"background-color: {COLOR_BG_PANEL}; border-radius: 8px;"
)

_DEADLINE_DATE_DROPDOWN = """
    QDateEdit::drop-down {
        subcontrol-origin: padding; subcontrol-position: top right;
        width: 20px; border-left: 1px solid #555555; background-color: #444444;
    }
    QDateEdit::down-arrow {
        image: none;
        border-left: 5px solid transparent; border-right: 5px solid transparent;
        border-top: 5px solid white; width: 0; height: 0; margin-top: 2px;
    }
"""

_DEADLINE_DATE_DROPDOWN_TINTED = """
    QDateEdit::drop-down {
        subcontrol-origin: padding; subcontrol-position: top right;
        width: 20px; border-left: 1px solid #555555; background-color: rgba(0,0,0,0.2);
    }
    QDateEdit::down-arrow {
        image: none;
        border-left: 5px solid transparent; border-right: 5px solid transparent;
        border-top: 5px solid white; width: 0; height: 0; margin-top: 2px;
    }
"""

BUTTON_COMPACT_STYLE = _BTN_COMPACT.strip()
BUTTON_DANGER_COMPACT_STYLE = _BTN_DANGER_COMPACT.strip()

FILE_NAME_FOLDER_STYLE = "color: #00D1FF; font-size: 12pt; font-weight: bold;"
FILE_NAME_FILE_STYLE = "color: #DDDDDD; font-size: 11pt;"

MENU_STYLE = """
    QMenu { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #3D3D3D; }
    QMenu::item { padding: 5px 20px; }
    QMenu::item:selected { background-color: #3D3D3D; }
"""

DATE_EDIT_STYLE = """
    QDateEdit {
        background-color: #333333; color: #FFFFFF;
        border: 1px solid #444444; font-size: 13pt; font-weight: bold;
        padding: 4px 6px; border-radius: 3px;
    }
    QDateEdit::drop-down {
        subcontrol-origin: padding; subcontrol-position: top right;
        width: 20px; border-left: 1px solid #555555; background-color: #444444;
    }
    QDateEdit::down-arrow {
        image: none;
        border-left: 5px solid transparent; border-right: 5px solid transparent;
        border-top: 5px solid white; width: 0; height: 0; margin-top: 2px;
    }
"""

SEARCH_FIELD_STYLE = """
    QLineEdit {
        background-color: #2D2D2D; color: #FFFFFF;
        border: 1px solid #3D3D3D; border-radius: 4px; padding: 6px; font-size: 11pt;
    }
"""

PANEL_HEADER_STYLE = """
    font-size: 13pt; font-weight: bold; color: #00D1FF;
    padding: 5px; background-color: #252525; border-radius: 4px;
"""

SIDEBAR_BUTTON_STYLE = "background-color: #2D2D2D; color: white; font-size: 12pt; padding: 6px;"
PRIMARY_SIDEBAR_BUTTON_STYLE = (
    "background-color: #0078D7; color: white; font-weight: bold; font-size: 12pt; padding: 6px;"
)

SORT_COMBO_STYLE = """
    QComboBox {
        background-color: #2D2D2D; color: #FFFFFF;
        border: 1px solid #3D3D3D; padding: 4px; border-radius: 4px; font-size: 10pt;
    }
"""

DB_INFO_LABEL_STYLE = (
    "color: #888888; font-size: 10pt; padding: 5px; background-color: #252525; border-radius: 4px;"
)

PLACEHOLDER_STYLE = """
    font-size: 14pt; color: #AAAAAA; padding: 40px;
    background-color: #252525; border-radius: 8px;
"""

CLIENT_NAME_STYLE = "font-size: 20pt; font-weight: bold; color: #00D1FF; padding: 5px 0;"
NOTES_BUTTON_STYLE = """
    QPushButton {
        background-color: transparent; color: #FFFFFF; border: none;
        font-size: 16pt; padding: 0px;
    }
    QPushButton:hover { background-color: #333333; border-radius: 18px; }
"""
ADD_ORDER_BUTTON_STYLE = """
    QPushButton {
        background-color: #28A745; color: white; border: 1px solid #28A745;
        border-radius: 4px; font-size: 12pt; padding: 4px; font-weight: bold;
    }
    QPushButton:hover { background-color: #218838; border-color: #1E7E34; }
"""
SETTINGS_GEAR_BUTTON_STYLE = """
    QPushButton {
        background-color: #2D2D2D; color: white; border: 1px solid #444444;
        border-radius: 4px; font-size: 12pt; padding: 4px;
    }
    QPushButton:hover { background-color: #3D3D3D; border-color: #555555; }
"""
SEPARATOR_STYLE = "background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 5px 0;"

STATUS_BAR_STYLE = "QStatusBar { color: #888888; background: transparent; font-size: 10pt; }"

DRAG_HINT_STYLE = (
    "color: #DDDDDD; font-size: 11pt; font-style: italic; padding: 5px 10px; "
    "background-color: #252525; border-radius: 4px; border: 1px dashed #555555;"
)


def label_accent(*, size: int = 13, padding: str = "0") -> str:
    return f"font-size: {size}pt; font-weight: bold; color: {COLOR_ACCENT}; padding: {padding};"


def label_muted_desc(*, size: int = 10, indent: int = 0) -> str:
    return f"color: {COLOR_TEXT_MUTED}; font-size: {size}pt; padding-left: {indent}px;"


def label_stat_value(color: str, *, size: int = 13) -> str:
    return f"color: {color}; font-size: {size}pt; font-weight: bold;"


def label_stat_title(*, size: int = 10) -> str:
    return f"color: {COLOR_TEXT_DIM}; font-size: {size}pt; font-weight: bold;"


def money_input_style(color: str) -> str:
    return f"""
        QLineEdit {{
            background-color: #252525; color: {color};
            border: 1px solid #444444; padding: 4px 8px;
            border-radius: 4px; font-size: 14pt; font-weight: bold;
        }}
        QLineEdit:focus {{ border: 1px solid {color}; }}
    """


def payment_status_style(color: str) -> str:
    return f"color: {color}; font-size: 11pt; font-weight: bold;"


def deadline_date_edit_style(
    bg: str,
    border: str,
    *,
    text: str = "white",
    tinted_dropdown: bool = False,
) -> str:
    dropdown = _DEADLINE_DATE_DROPDOWN_TINTED if tinted_dropdown else _DEADLINE_DATE_DROPDOWN
    return f"""
        QDateEdit {{
            color: {text}; padding: 4px 6px; border-radius: 3px;
            font-size: 13pt; font-weight: bold;
            background-color: {bg}; border: 1px solid {border};
        }}
        {dropdown}
    """


def status_bar_message(*, error: bool = False, saved: bool = False) -> str:
    if error:
        color = "#FF4B2B"
    elif saved:
        color = COLOR_SUCCESS
    else:
        color = "#888888"
    return f"QStatusBar {{ color: {color}; background: transparent; font-size: 10pt; }}"


def create_dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    return palette
