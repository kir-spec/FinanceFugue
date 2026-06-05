import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QGroupBox, QRadioButton,
)
from PySide6.QtCore import Qt

from ..logger import get_logger
from .. import APP_NAME, VERSION
from ..theme import FIRST_RUN_DIALOG_STYLESHEET, label_accent, label_muted_desc

logger = get_logger("Dialogs")

# --- ДИАЛОГ ПЕРВОГО ЗАПУСКА ---
class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Добро пожаловать в {APP_NAME} {VERSION}!")
        self.resize(800, 600)
        self.setMinimumSize(600, 500)
        
        self.setStyleSheet(FIRST_RUN_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # Приветствие
        welcome_label = QLabel(
            f"Добро пожаловать в {APP_NAME} {VERSION}!\n\n"
            "Для начала работы настройте параметры хранения данных."
        )
        welcome_label.setStyleSheet(label_accent(size=16, padding="20px"))
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_label)
        
        # Выбор места хранения базы данных
        db_group = QGroupBox("Хранение базы данных")
        db_layout = QVBoxLayout(db_group)
        
        db_layout.addWidget(QLabel("Выберите место для хранения базы данных:"))
        
        self.db_path_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "FinanceFugue"))
        self.db_path_edit.setReadOnly(True)
        
        browse_btn = QPushButton("Выбрать папку...")
        browse_btn.clicked.connect(self.browse_db_folder)
        
        db_path_layout = QHBoxLayout()
        db_path_layout.addWidget(self.db_path_edit, 1)
        db_path_layout.addWidget(browse_btn)
        db_layout.addLayout(db_path_layout)
        
        layout.addWidget(db_group)
        
        # Выбор способа хранения файлов
        files_group = QGroupBox("Хранение файлов клиентов")
        files_layout = QVBoxLayout(files_group)
        
        files_layout.addWidget(QLabel("Как вы хотите хранить файлы клиентов?"))
        
        self.file_storage_original = QRadioButton("Оставлять файлы на своих местах")
        self.file_storage_original.setChecked(True)
        self.file_storage_original.toggled.connect(self.on_storage_changed)
        
        files_layout.addWidget(self.file_storage_original)
        
        original_desc = QLabel(
            "• Файлы остаются там, где они есть\n"
            "• Программа будет ссылаться на оригинальные файлы\n"
            "• Экономит место на диске\n"
            "• При перемещении файлов ссылки могут сломаться"
        )
        original_desc.setStyleSheet(label_muted_desc(size=11, indent=25))
        files_layout.addWidget(original_desc)
        
        self.file_storage_copy = QRadioButton("Копировать файлы в базу данных")
        self.file_storage_copy.toggled.connect(self.on_storage_changed)
        
        files_layout.addWidget(self.file_storage_copy)
        
        copy_desc = QLabel(
            "• Файлы копируются в папку базы данных\n"
            "• Все данные хранятся в одном месте\n"
            "• Занимает больше места на диске\n"
            "• Более надежно, файлы всегда доступны"
        )
        copy_desc.setStyleSheet(label_muted_desc(size=11, indent=25))
        files_layout.addWidget(copy_desc)
        
        layout.addWidget(files_group)

        self._storage_hint = QLabel("Выбрано: файлы остаются на своих местах (ссылки).")
        self._storage_hint.setStyleSheet(label_muted_desc(size=11))
        self._storage_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._storage_hint)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        start_btn = QPushButton("Начать работу")
        start_btn.setObjectName("successButton")
        start_btn.clicked.connect(self.accept)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(start_btn)
        
        layout.addLayout(buttons_layout)
    
    def browse_db_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для базы данных")
        if folder:
            self.db_path_edit.setText(folder)
    
    def on_storage_changed(self):
        if self.file_storage_copy.isChecked():
            self._storage_hint.setText(
                "Выбрано: файлы будут копироваться в папку базы данных при добавлении."
            )
        else:
            self._storage_hint.setText(
                "Выбрано: файлы остаются на своих местах (ссылки)."
            )
    
    def get_settings(self):
        storage_mode = 'link' if self.file_storage_original.isChecked() else 'copy'
        
        return {
            'database_path': self.db_path_edit.text(),
            'file_storage_mode': storage_mode
        }

