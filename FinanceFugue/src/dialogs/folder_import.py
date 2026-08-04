import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QMessageBox, QLineEdit, QFileDialog, QCheckBox,
)

from ..logger import get_logger
from ..theme import FOLDER_IMPORT_DIALOG_STYLESHEET

logger = get_logger("Dialogs")

# --- ДИАЛОГ ИМПОРТА ИЗ ПАПКИ ---
class FolderImportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self.setWindowTitle("Импорт клиентов из папки")
        self.setFixedSize(500, 400)
        
        self.setStyleSheet(FOLDER_IMPORT_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # Выбор папки
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Папка для импорта:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_edit, 1)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)
        
        # Расширения файлов
        layout.addWidget(QLabel("Расширения файлов для импорта (через запятую):"))
        self.extensions_edit = QLineEdit(".mp3,.wav,.mid,.midi,.pdf,.doc,.docx,.txt")
        layout.addWidget(self.extensions_edit)
        
        # Группировка файлов
        layout.addWidget(QLabel("Группировать файлы по:"))
        group_layout = QHBoxLayout()
        self.group_by_name = QCheckBox("Имени файла (без расширения)")
        self.group_by_name.setChecked(True)
        self.group_by_type = QCheckBox("Типу файла")
        group_layout.addWidget(self.group_by_name)
        group_layout.addWidget(self.group_by_type)
        layout.addLayout(group_layout)

        # Опция импорта пустых
        self.import_empty_cb = QCheckBox("Импортировать папки без файлов")
        layout.addWidget(self.import_empty_cb)
        
        # Предварительный просмотр
        layout.addWidget(QLabel("Будут созданы клиенты и заказы:"))
        self.preview_list = QListWidget()
        layout.addWidget(self.preview_list)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        scan_btn = QPushButton("Сканировать папку")
        scan_btn.clicked.connect(self.scan_folder)
        import_btn = QPushButton("Импортировать")
        import_btn.clicked.connect(self.accept)
        import_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(scan_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(import_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        self.scan_btn = scan_btn
        self.import_btn = import_btn
        self.scan_results = []
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для импорта")
        if folder:
            self.folder_edit.setText(folder)
    
    def scan_folder(self):
        folder = self.folder_edit.text()
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "Ошибка", "Выберите существующую папку")
            return
        
        # 1. Исходная структура папок: Программа получает на вход путь к Папке Клиента.
        # Внутри неё структура строго следующая:
        # Папка Клиента (Пример: "Верди")
        #   Папка Заказа (Пример: "Травиата") — это уровень создания карточек.
        #     Вложенные элементы (Пример: "Действие 1", "Действие 2", "Файл_инфо.txt") — это содержимое карточки.
        
        self.preview_list.clear()
        self.scan_results = []
        
        # Просканируй все папки внутри выбранной "Папки Клиента" (корневой папки импорта)
        # В контексте диалога: пользователь выбирает "Корневую папку", в которой лежат папки КЛИЕНТОВ.
        # Т.е. структура: Root -> Client -> Order -> Files/Dirs
        
        # Если пользователь выбирает сразу папку Клиента (например "Верди"), то мы должны это определить.
        # Но для универсальности будем считать, что пользователь выбирает папку,
        # В КОТОРОЙ лежат папки клиентов.
        
        # ИЛИ, следуя задаче: "Программа получает на вход путь к Папке Клиента".
        # Если диалог называется "Импорт из папки", логичнее выбирать корневую папку с клиентами.
        # Давайте поддержим оба варианта:
        # 1. Выбрана папка с клиентами (внутри папки клиентов, внутри папки заказов)
        # 2. Выбрана папка одного клиента (внутри папки заказов)
        
        try:
            root_items = [
                os.path.join(folder, item)
                for item in os.listdir(folder)
            ]
        except OSError as e:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось прочитать папку:\n{folder}\n\n{e}",
            )
            return
        subfolders = [d for d in root_items if os.path.isdir(d)]

        # Проходимся по каждой папке (Клиенту).
        # Каждый os.listdir обёрнут в try/except OSError,
        # иначе одна защищённая папка ломает весь импорт.
        for client_path in subfolders:
            client_name = os.path.basename(client_path)

            try:
                client_items = [
                    os.path.join(client_path, item)
                    for item in os.listdir(client_path)
                ]
            except OSError as e:
                logger.warning("Не удалось прочитать папку клиента %s: %s", client_path, e)
                self.preview_list.addItem(f"⚠ Пропуск: {client_name} ({e})")
                continue

            order_folders = [d for d in client_items if os.path.isdir(d)]

            for order_path in order_folders:
                order_name = os.path.basename(order_path)

                order_content = []
                try:
                    for item in os.listdir(order_path):
                        item_path = os.path.join(order_path, item)
                        order_content.append((item, item_path))
                except OSError as e:
                    logger.warning(
                        "Не удалось прочитать папку заказа %s: %s", order_path, e
                    )
                    continue

                if order_content:
                    self.scan_results.append({
                        'client_name': client_name,
                        'order_name': order_name,
                        'files': order_content,
                    })
                    count = len(order_content)
                    self.preview_list.addItem(f"Клиент: {client_name} -> Заказ: {order_name} (Обнаружено элементов: {count})")

        if self.scan_results:
            self.import_btn.setEnabled(True)
            self.preview_list.addItem(f"\nВсего будет создано: {len(self.scan_results)} заказов")
        else:
            self.preview_list.addItem("Структура не распознана. Убедитесь, что структура папок соответствует:\nПапка Клиента -> Папка Заказа -> Содержимое")

