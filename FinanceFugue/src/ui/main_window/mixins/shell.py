from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt

from .... import APP_NAME, VERSION
from ....dialogs import AboutDialog, FileManagerDialog, SettingsDialog
from ....services.client_stats import calculate_global_dashboard
from ....services.deadline_notifier import collect_deadline_alerts, format_alerts_message
from ....theme import (
    DB_INFO_LABEL_STYLE,
    MAIN_WINDOW_STYLESHEET,
    PANEL_HEADER_STYLE,
    PLACEHOLDER_STYLE,
    PRIMARY_SIDEBAR_BUTTON_STYLE,
    SCROLL_AREA_TRANSPARENT_STYLE,
    SEARCH_FIELD_STYLE,
    SIDEBAR_BUTTON_STYLE,
    SORT_COMBO_STYLE,
    STATUS_BAR_STYLE,
    TRANSPARENT_FRAME_STYLE,
    create_dark_palette,
    status_bar_message,
)
from ....ui.client_list_widget import ClientListWidget
from ....ui.dashboard import create_stat_widget
from ....ui.icon_loader import load_app_icon
from ....services.backup import backup_settings_file
from ....logger import get_logger

logger = get_logger("MainWindow")


class ShellMixin:
    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.resize(900, 800)
        icon = load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.set_dark_palette()
        self.setStyleSheet(MAIN_WINDOW_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        self.dash = QFrame()
        self.dash.setStyleSheet(TRANSPARENT_FRAME_STYLE)
        self.dash.setFixedHeight(60)
        self.dash_layout = QHBoxLayout(self.dash)
        self.dash_layout.setContentsMargins(0, 0, 0, 0)
        self.dash_layout.setSpacing(8)
        self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.dash)

        work_area = QHBoxLayout()
        work_area.setSpacing(15)

        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        clients_label = QLabel("👤 КЛИЕНТЫ")
        clients_label.setStyleSheet(PANEL_HEADER_STYLE)
        left_layout.addWidget(clients_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh_list)
        self.search_edit.setStyleSheet(SEARCH_FIELD_STYLE)
        left_layout.addWidget(self.search_edit)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Имя (А-Я)", "Имя (Я-А)", "Новые заказы", "Старые заказы", "Срочные"]
        )
        self.sort_combo.currentIndexChanged.connect(self.sort_clients)
        self.sort_combo.setStyleSheet(SORT_COMBO_STYLE)
        left_layout.addWidget(self.sort_combo)

        self.cl_list = ClientListWidget()
        self.cl_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.cl_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cl_list.customContextMenuRequested.connect(self.show_client_context_menu)
        self.cl_list.itemClicked.connect(self.select_client)
        self.cl_list.folder_dropped.connect(self.import_dropped_client_folder)
        left_layout.addWidget(self.cl_list)

        btn_files = QPushButton("📁 Менеджер файлов")
        btn_files.clicked.connect(self.open_file_manager)
        btn_files.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(btn_files)

        btn_add = QPushButton("➕ Новый клиент")
        btn_add.clicked.connect(self.add_client)
        btn_add.setStyleSheet(PRIMARY_SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(btn_add)

        btn_set = QPushButton("⚙ Настройки")
        btn_set.clicked.connect(self.open_settings)
        btn_set.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(btn_set)

        btn_help = QPushButton("❓ Справка")
        btn_help.clicked.connect(self.open_help)
        btn_help.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(btn_help)

        self.db_info_label = QLabel(f"Клиентов: {len(self.clients)}")
        self.db_info_label.setStyleSheet(DB_INFO_LABEL_STYLE)
        left_layout.addWidget(self.db_info_label)

        work_area.addWidget(left_panel)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(SCROLL_AREA_TRANSPARENT_STYLE)

        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(15, 15, 15, 15)
        self.profile_layout.setSpacing(10)

        self.placeholder = QLabel("👈 Выберите клиента из списка или создайте нового")
        self.placeholder.setStyleSheet(PLACEHOLDER_STYLE)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_layout.addWidget(self.placeholder)

        self.scroll.setWidget(self.profile_container)
        work_area.addWidget(self.scroll, 1)

        main_layout.addLayout(work_area)

        self.refresh_list()
        self.update_dash()
        self._init_status_bar()

    def _init_status_bar(self):
        self.statusBar().setStyleSheet(STATUS_BAR_STYLE)
        self._set_save_status("Готово")

    def _set_save_status(self, message: str, *, error: bool = False) -> None:
        saved = message == "Сохранено"
        self.statusBar().setStyleSheet(
            status_bar_message(error=error, saved=saved)
        )
        self.statusBar().showMessage(message, 0 if error else 5000)

    def set_dark_palette(self):
        self.setPalette(create_dark_palette())

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_client)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_db)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_client)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_search)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file_manager)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.open_settings)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh_list)

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def open_file_manager(self):
        FileManagerDialog(self, self).exec()

    def open_about(self):
        AboutDialog(self).exec()

    def open_help(self):
        from ....utils.paths import resource_path

        help_path = resource_path("help.html")
        if not help_path.exists():
            QMessageBox.warning(self, APP_NAME, "Файл справки help.html не найден.")
            return
        import webbrowser

        webbrowser.open(help_path.as_uri())

    def open_settings(self):
        SettingsDialog(self).exec()

    def check_deadline_notifications(self, *, popup: bool = True):
        if not self.app_settings.get("deadline_notifications", True):
            return
        alerts = collect_deadline_alerts(self.clients)
        if not alerts:
            return
        message = "Приближающиеся или просроченные дедлайны:\n\n" + format_alerts_message(
            alerts
        )
        if popup:
            QMessageBox.information(self, f"{APP_NAME} — сроки заказов", message)
        else:
            self.statusBar().showMessage(
                f"⚠ Дедлайны: {len(alerts)} заказ(ов) требуют внимания", 15000
            )

    def update_dash(self):
        while self.dash_layout.count():
            item = self.dash_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for title, value, color in calculate_global_dashboard(self.clients):
            self.dash_layout.addWidget(create_stat_widget(title, value, color))

        self.dash_layout.addStretch()

    def closeEvent(self, event):
        try:
            self.save_db()
        except Exception as e:
            logger.error("Ошибка сохранения при выходе: %s", e, exc_info=True)
            QMessageBox.warning(
                self,
                APP_NAME,
                f"Не удалось сохранить базу данных при выходе:\n{e}",
            )
        self.backup_settings()
        if hasattr(self, "_instance_lock"):
            self._instance_lock.release()
        event.accept()

    def backup_settings(self):
        """Создает резервную копию настроек"""
        try:
            backup_settings_file(self.app_settings)
        except Exception as e:
            logger.error("Ошибка создания бэкапа настроек: %s", e, exc_info=True)
