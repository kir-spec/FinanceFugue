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
    CLIENT_ARCHIVE_BTN_STYLE,
    NOTES_BUTTON_STYLE,
    NOTES_CANCEL_BUTTON_STYLE,
    NOTES_EDIT_STYLE,
    NOTES_SAVE_BUTTON_STYLE,
    NO_ORDERS_STYLE,
    ORDERS_SECTION_STYLE,
    SEPARATOR_STYLE,
    SETTINGS_GEAR_BUTTON_STYLE,
)
from ....ui.dashboard import create_client_stats_widget
from ....widgets import OrderWidget
from ....widgets.avatar_widget import AvatarWidget


class ClientProfileMixin:
    def clear_profile_layout(self):
        """Полностью очищает profile_layout.

        Предыдущая версия утекала ``QSpacerItem`` на каждом
        пере-выборе клиента (``item.widget()`` возвращает
        ``None`` для spacer'ов, и они просто исчезали из layout
        без удаления). Теперь обрабатываются все item-type.
        """
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if widget is not self.placeholder:
                    widget.setParent(None)
                    widget.deleteLater()
            else:
                # layout-item без виджета: spacer или nested layout.
                spacer = item.spacerItem()
                if spacer is not None:
                    # QSpacerItem не имеет deleteLater: достаточно
                    # отвязать от layout; Python GC вернёт память.
                    del spacer
                else:
                    nested = item.layout()
                    if nested is not None:
                        nested.setParent(None)
                        nested.deleteLater()

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
        name_row.setSpacing(15)
        
        # Avatar
        self.avatar_widget = AvatarWidget(client, self.bridge, size=48)
        self.avatar_widget.avatar_changed.connect(lambda p: self.save_db())
        name_row.addWidget(self.avatar_widget)
        
        name_label = QLabel(client.name.upper())
        name_label.setStyleSheet(CLIENT_NAME_STYLE)
        name_row.addWidget(name_label)

        notes_btn = QPushButton("✏️")
        notes_btn.setFixedSize(36, 36)
        notes_btn.setToolTip("Редактировать комментарий к клиенту")
        notes_btn.clicked.connect(self.toggle_notes)
        notes_btn.setStyleSheet(NOTES_BUTTON_STYLE)
        name_row.addWidget(notes_btn)

        name_row.addStretch()
        header_layout.addLayout(name_row)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(10)

        add_order_btn = QPushButton("➕ Создать заказ")
        add_order_btn.setFixedHeight(36)
        add_order_btn.setStyleSheet(ADD_ORDER_BUTTON_STYLE)
        add_order_btn.clicked.connect(self.add_order)
        buttons_row.addWidget(add_order_btn)

        self.archive_completed_btn = QPushButton("📦 В архив завершенные")
        self.archive_completed_btn.setFixedHeight(36)
        self.archive_completed_btn.clicked.connect(self.archive_completed_orders)
        self.archive_completed_btn.setStyleSheet(CLIENT_ARCHIVE_BTN_STYLE)
        has_completed = any(o.status == "Завершен" for o in client.orders)
        self.archive_completed_btn.setVisible(has_completed)
        buttons_row.addWidget(self.archive_completed_btn)

        settings_btn = QPushButton("⚙ настройки")
        settings_btn.setToolTip("Редактировать профиль клиента (имя, email и т.д.)")
        settings_btn.setFixedHeight(36)
        settings_btn.setStyleSheet(SETTINGS_GEAR_BUTTON_STYLE)
        settings_btn.clicked.connect(self.open_client_settings)

        self.recycle_bin_orders_btn = QPushButton("🗑 Корзина заказов")
        self.recycle_bin_orders_btn.setFixedHeight(36)
        self.recycle_bin_orders_btn.setStyleSheet(CLIENT_ARCHIVE_BTN_STYLE)  # same style as archive
        self.recycle_bin_orders_btn.clicked.connect(self.open_recycle_bin_orders)
        has_deleted_orders = any(o.is_deleted for o in client.orders)
        self.recycle_bin_orders_btn.setVisible(has_deleted_orders)

        buttons_row.addWidget(self.recycle_bin_orders_btn)
        buttons_row.addWidget(settings_btn)
        buttons_row.addStretch()

        header_layout.addLayout(buttons_row)

        self.profile_layout.addWidget(header_widget)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(SEPARATOR_STYLE)
        self.profile_layout.addWidget(sep1)

        self.notes_container = QWidget()
        notes_layout = QVBoxLayout(self.notes_container)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(5)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(client.notes)
        self.notes_edit.setFixedHeight(100)
        self.notes_edit.setStyleSheet(NOTES_EDIT_STYLE)
        
        notes_buttons = QHBoxLayout()
        save_notes_btn = QPushButton("✅ Сохранить")
        save_notes_btn.setToolTip("Сохранить комментарий")
        save_notes_btn.setStyleSheet(NOTES_SAVE_BUTTON_STYLE)
        save_notes_btn.clicked.connect(self.save_notes)
        
        cancel_notes_btn = QPushButton("❌ Отмена")
        cancel_notes_btn.setToolTip("Отменить изменения и закрыть")
        cancel_notes_btn.setStyleSheet(NOTES_CANCEL_BUTTON_STYLE)
        cancel_notes_btn.clicked.connect(self.cancel_notes)
        
        notes_buttons.addWidget(save_notes_btn)
        notes_buttons.addWidget(cancel_notes_btn)
        notes_buttons.addStretch()

        notes_layout.addWidget(self.notes_edit)
        notes_layout.addLayout(notes_buttons)
        self.notes_container.setVisible(False)
        self.profile_layout.addWidget(self.notes_container)

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

        active_orders = [o for o in client.orders if not o.is_deleted]
        if active_orders:
            for order in active_orders:
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
            self.notes_container.setVisible(not self.notes_container.isVisible())
            if self.notes_container.isVisible():
                self.notes_edit.setPlainText(self.current_client.notes)

    def save_notes(self):
        """Сохраняет заметки и закрывает редактор."""
        if self.current_client:
            self.current_client.notes = self.notes_edit.toPlainText()
            self.save_db()
            self.notes_container.setVisible(False)
            
    def cancel_notes(self):
        """Отменяет редактирование заметок и закрывает редактор."""
        if self.current_client:
            self.notes_edit.setPlainText(self.current_client.notes)
            self.notes_container.setVisible(False)

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

    def archive_completed_orders(self):
        from PySide6.QtWidgets import QMessageBox
        answer = QMessageBox.question(
            self,
            "Архивация заказов",
            "Отправить все завершенные заказы этого клиента в архив?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.bridge.archive_completed_orders(self.current_client)

    def open_recycle_bin_orders(self):
        from ....dialogs import RecycleBinOrdersDialog
        if not self.current_client:
            return
            
        dialog = RecycleBinOrdersDialog(self.current_client, self.bridge)
        dialog.exec()
        self.render_client_profile()
