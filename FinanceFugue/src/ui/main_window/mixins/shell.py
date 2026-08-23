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
from PySide6.QtCore import Qt, QTimer

from .... import APP_NAME, VERSION
from ....dialogs import AboutDialog, FileManagerDialog, SettingsDialog, RecycleBinDialog, AnalyticsDialog
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
        self.resize(1400, 900)
        self.setMinimumSize(1000, 600)
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
        self.dash.setMinimumHeight(60)
        self.dash_layout = QHBoxLayout(self.dash)
        self.dash_layout.setContentsMargins(0, 0, 0, 0)
        self.dash_layout.setSpacing(8)
        self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Фильтр периода
        self.dash_filter_cb = QComboBox()
        self.dash_filter_cb.addItems([
            "За всё время",
            "Текущий год",
            "Прошлый год",
            "Текущий месяц"
        ])
        self.dash_filter_cb.setStyleSheet(SORT_COMBO_STYLE)
        self.dash_filter_cb.currentIndexChanged.connect(self.update_dash)
        self.dash_layout.addWidget(self.dash_filter_cb)
        
        main_layout.addWidget(self.dash)

        work_area = QHBoxLayout()
        work_area.setSpacing(15)

        left_panel = QWidget()
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(450)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        sidebar_header = QHBoxLayout()
        clients_label = QLabel("👤 КЛИЕНТЫ")
        clients_label.setStyleSheet(PANEL_HEADER_STYLE)
        
        self.archive_btn = QPushButton("🗄 Архив")
        self.archive_btn.clicked.connect(self.open_archive)
        self.archive_btn.setStyleSheet(PRIMARY_SIDEBAR_BUTTON_STYLE)
        
        self.analytics_btn = QPushButton("📊 Аналитика")
        self.analytics_btn.clicked.connect(self.open_analytics)
        self.analytics_btn.setStyleSheet(PRIMARY_SIDEBAR_BUTTON_STYLE)
        
        self.recycle_bin_btn = QPushButton("🗑 Корзина")
        self.recycle_bin_btn.clicked.connect(self.open_recycle_bin)
        self.recycle_bin_btn.setStyleSheet(PRIMARY_SIDEBAR_BUTTON_STYLE)
        
        sidebar_header.addWidget(clients_label)
        sidebar_header.addStretch()
        sidebar_header.addWidget(self.analytics_btn)
        sidebar_header.addWidget(self.archive_btn)
        sidebar_header.addWidget(self.recycle_bin_btn)
        
        left_layout.addLayout(sidebar_header)

        self.search_edit = QLineEdit()
        self.search_edit.setToolTip("Быстрый поиск клиента по имени")
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.setClearButtonEnabled(True)
        # Дебаунс 200мс: refresh_list не вызывается на каждом символе.
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(200)
        self._search_debounce.timeout.connect(self.refresh_list)
        self.search_edit.textChanged.connect(
            lambda _text: self._search_debounce.start()
        )
        self.search_edit.setStyleSheet(SEARCH_FIELD_STYLE)
        left_layout.addWidget(self.search_edit)

        self.sort_combo = QComboBox()
        self.sort_combo.setToolTip("Сортировка списка клиентов")
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

        from ....services.i18n import t, get_current_language
        get_current_language(self.app_settings)

        self.btn_files = QPushButton(t("sidebar_file_manager"))
        self.btn_files.setToolTip(t("sidebar_file_manager_tooltip"))
        self.btn_files.clicked.connect(self.open_file_manager)
        self.btn_files.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(self.btn_files)

        self.btn_add = QPushButton(t("sidebar_new_client"))
        self.btn_add.setToolTip(t("sidebar_new_client_tooltip"))
        self.btn_add.clicked.connect(self.add_client)
        self.btn_add.setStyleSheet(PRIMARY_SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(self.btn_add)

        self.btn_sync = QPushButton(t("sidebar_bot_sync"))
        self.btn_sync.setToolTip(t("sidebar_bot_sync_tooltip"))
        self.btn_sync.clicked.connect(self.open_telegram_sync)
        self.btn_sync.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(self.btn_sync)

        self.btn_set = QPushButton(t("sidebar_settings"))
        self.btn_set.setToolTip(t("sidebar_settings_tooltip"))
        self.btn_set.clicked.connect(self.open_settings)
        self.btn_set.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(self.btn_set)

        self.btn_help = QPushButton(t("sidebar_help"))
        self.btn_help.setToolTip(t("sidebar_help_tooltip"))
        self.btn_help.clicked.connect(self.open_help)
        self.btn_help.setStyleSheet(SIDEBAR_BUTTON_STYLE)
        left_layout.addWidget(self.btn_help)

        self.db_info_label = QLabel(t("sidebar_clients_count", count=len(self.clients)))
        self.db_info_label.setToolTip("Общее количество клиентов в базе")
        self.db_info_label.setStyleSheet(DB_INFO_LABEL_STYLE)
        left_layout.addWidget(self.db_info_label)

        work_area.addWidget(left_panel)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(SCROLL_AREA_TRANSPARENT_STYLE)

        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(30, 30, 30, 30)
        self.profile_layout.setSpacing(15)

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

    def open_archive(self):
        from ....dialogs import ArchiveViewerDialog
        dialog = ArchiveViewerDialog(self.bridge)
        dialog.exec()

    def open_recycle_bin(self):
        dialog = RecycleBinDialog(self.bridge)
        dialog.exec()
        self.refresh_list()

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

    def open_analytics(self):
        AnalyticsDialog(self.bridge).exec()

    def open_settings(self):
        if SettingsDialog(self).exec():
            self.refresh_list()
            self.render_client_profile()

    def check_deadline_notifications(self, *, popup: bool = True):
        if not self.app_settings.get("deadline_notifications", True):
            return
        alerts = collect_deadline_alerts(self.clients)
        if not alerts:
            return
        if popup:
            # Дедуп: если набор тех же заказов уже показывали —
            # не спамим. Ack-ключи в settings: deadline_alerts_acked (frozenset).
            acked: set[str] = set(
                self.app_settings.get("deadline_alerts_acked", [])
            )
            current_keys = {
                f"{a.client_name}|{a.order_name}|{a.deadline}"
                for a in alerts
            }
            new_keys = current_keys - acked
            if not new_keys:
                return
            self.app_settings["deadline_alerts_acked"] = sorted(current_keys)
            try:
                self.save_settings()
            except Exception as e:  # noqa: BLE001
                logger.warning("Не удалось сохранить deadline ack: %s", e)
            new_alerts = [
                a for a in alerts
                if f"{a.client_name}|{a.order_name}|{a.deadline}" in new_keys
            ]
            message = "Приближающиеся или просроченные дедлайны:\n\n" + format_alerts_message(
                new_alerts
            )
            QMessageBox.information(self, f"{APP_NAME} — сроки заказов", message)
        else:
            self.statusBar().showMessage(
                f"⚠ Дедлайны: {len(alerts)} заказ(ов) требуют внимания", 15000
            )

    def update_dash(self):
        # Очищаем дашборд (кроме фильтра)
        while self.dash_layout.count() > 1:
            item = self.dash_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        filter_text = self.dash_filter_cb.currentText()
        start_date = None
        end_date = None
        archive_clients = None

        if filter_text != "За всё время":
            from datetime import datetime, date
            today = date.today()
            if filter_text == "Текущий год":
                start_date = datetime(today.year, 1, 1)
                end_date = datetime(today.year, 12, 31)
            elif filter_text == "Прошлый год":
                start_date = datetime(today.year - 1, 1, 1)
                end_date = datetime(today.year - 1, 12, 31)
            elif filter_text == "Текущий месяц":
                start_date = datetime(today.year, today.month, 1)
                # Конец месяца
                if today.month == 12:
                    end_date = datetime(today.year, 12, 31)
                else:
                    end_date = datetime(today.year, today.month + 1, 1)
            
            # Если не "За всё время", то подгружаем архив для полной картины
            archive_clients = self.archive_manager.get_archive_clients()

        for title, value, color in calculate_global_dashboard(
            self.clients,
            archive_clients=archive_clients,
            start_date=start_date,
            end_date=end_date
        ):
            self.dash_layout.addWidget(create_stat_widget(title, value, color))

        self.dash_layout.addStretch()

    def closeEvent(self, event):
        try:
            self.save_db()
        except Exception as e:
            logger.error("Ошибка сохранения при выходе: %s", e, exc_info=True)
            answer = QMessageBox.question(
                self,
                APP_NAME,
                f"Не удалось сохранить базу данных при выходе:\n{e}\n\n"
                "Выйти без сохранения?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.backup_settings()
        if hasattr(self, "_deadline_timer"):
            self._deadline_timer.stop()
        if hasattr(self, "_search_debounce"):
            self._search_debounce.stop()
        if hasattr(self, "_instance_lock"):
            self._instance_lock.release()
        event.accept()

    def backup_settings(self):
        """Создает резервную копию настроек"""
        try:
            backup_settings_file(self.app_settings)
        except Exception as e:
            logger.error("Ошибка создания бэкапа настроек: %s", e, exc_info=True)
