from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ....dialogs import ClientSettingsDialog
from ....services.client_stats import calculate_client_stats
from ....theme import (
    ADD_ORDER_BUTTON_STYLE,
    CLIENT_NAME_STYLE,
    NOTES_BUTTON_STYLE,
    NOTES_EDIT_STYLE,
    NO_ORDERS_STYLE,
    ORDERS_SECTION_STYLE,
    SEPARATOR_STYLE,
    SETTINGS_GEAR_BUTTON_STYLE,
)
from ....ui.dashboard import create_client_stats_widget
from ....widgets import OrderWidget


class ClientProfileMixin:
    def clear_profile_layout(self):
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.placeholder:
                widget.setParent(None)
                widget.deleteLater()

        if not self.current_client:
            self.placeholder.show()
        else:
            self.placeholder.hide()

    def select_client(self, item):
        client_id = item.data(Qt.ItemDataRole.UserRole)
        for client in self.clients:
            if client.id == client_id:
                self.current_client = client
                self.render_client_profile()
                break

    def render_client_profile(self):
        if self.current_client is None:
            return

        self.clear_profile_layout()
        client = self.current_client

        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)

        name_row = QHBoxLayout()
        name_label = QLabel(client.name.upper())
        name_label.setStyleSheet(CLIENT_NAME_STYLE)
        name_row.addWidget(name_label)

        notes_btn = QPushButton("✏️")
        notes_btn.setFixedSize(36, 36)
        notes_btn.setToolTip("Заметки")
        notes_btn.clicked.connect(self.toggle_notes)
        notes_btn.setStyleSheet(NOTES_BUTTON_STYLE)
        name_row.addWidget(notes_btn)

        name_row.addStretch()
        header_layout.addLayout(name_row)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(10)

        add_order_btn = QPushButton("➕ добавить заказ")
        add_order_btn.setFixedWidth(140)
        add_order_btn.setFixedHeight(36)
        add_order_btn.setStyleSheet(ADD_ORDER_BUTTON_STYLE)
        add_order_btn.clicked.connect(self.add_order)
        buttons_row.addWidget(add_order_btn)

        settings_btn = QPushButton("⚙ настройки")
        settings_btn.setFixedWidth(120)
        settings_btn.setFixedHeight(36)
        settings_btn.setStyleSheet(SETTINGS_GEAR_BUTTON_STYLE)
        settings_btn.clicked.connect(self.open_client_settings)

        buttons_row.addWidget(settings_btn)
        buttons_row.addStretch()

        header_layout.addLayout(buttons_row)

        self.profile_layout.addWidget(header_widget)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(SEPARATOR_STYLE)
        self.profile_layout.addWidget(sep1)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(client.notes)
        self.notes_edit.setFixedHeight(100)
        self.notes_edit.setVisible(False)
        self.notes_edit.textChanged.connect(self.save_notes)
        self.notes_edit.setStyleSheet(NOTES_EDIT_STYLE)
        self.profile_layout.addWidget(self.notes_edit)

        client_stats = self.calculate_client_stats(client)
        stats_widget = self.create_client_stats_widget(client_stats)
        self.profile_layout.addWidget(stats_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(SEPARATOR_STYLE)
        self.profile_layout.addWidget(sep2)

        orders_label = QLabel("📋 ЗАКАЗЫ КЛИЕНТА")
        orders_label.setStyleSheet(ORDERS_SECTION_STYLE)
        self.profile_layout.addWidget(orders_label)

        if client.orders:
            for order in client.orders:
                order_widget = OrderWidget(order, self.bridge)
                self.profile_layout.addWidget(order_widget)
        else:
            no_orders = QLabel("📋 У клиента пока нет заказов")
            no_orders.setStyleSheet(NO_ORDERS_STYLE)
            no_orders.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.profile_layout.addWidget(no_orders)

        self.profile_layout.addStretch()

    def calculate_client_stats(self, client):
        return calculate_client_stats(client)

    def create_client_stats_widget(self, stats):
        return create_client_stats_widget(stats)

    def toggle_notes(self):
        if self.current_client:
            self.notes_edit.setVisible(not self.notes_edit.isVisible())

    def save_notes(self):
        if self.current_client:
            self.current_client.notes = self.notes_edit.toPlainText()
            self.save_db()

    def open_client_settings(self):
        if not self.current_client:
            return

        dialog = ClientSettingsDialog(self.current_client, self.bridge)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_client.name = dialog.name_edit.text()
            self.current_client.email = dialog.email_edit.text()
            self.current_client.social_link = dialog.link_edit.text()
            self.current_client.notes = dialog.notes_edit.toPlainText()
            self.save_db()
            self.render_client_profile()
            self.refresh_list()
