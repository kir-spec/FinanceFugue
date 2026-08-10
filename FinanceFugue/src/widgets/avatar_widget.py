import os
import shutil
from PySide6.QtWidgets import QWidget, QFileDialog, QMessageBox
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QBrush, QColor, QCursor
from PySide6.QtCore import Qt, Signal

class AvatarWidget(QWidget):
    avatar_changed = Signal(str)

    def __init__(self, client, bridge, size=80, parent=None):
        super().__init__(parent)
        self.client = client
        self.bridge = bridge
        self.size = size
        self.setFixedSize(self.size, self.size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Нажмите, чтобы изменить аватар")
        
        self.pixmap = None
        self._load_avatar()

    def _load_avatar(self):
        if not self.client.avatar_path:
            self.pixmap = None
            return

        db_folder = self.bridge.app_settings.get('database_path', self.bridge.storage_db_dir())
        
        # Path resolution (relative or absolute)
        if os.path.isabs(self.client.avatar_path):
            path = self.client.avatar_path
        else:
            path = os.path.normpath(os.path.join(db_folder, self.client.avatar_path))

        if os.path.exists(path):
            self.pixmap = QPixmap(path)
        else:
            self.pixmap = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()
        path = QPainterPath()
        path.addEllipse(rect)
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            # Scale and crop to fill
            scaled = self.pixmap.scaled(
                self.size, self.size, 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                Qt.TransformationMode.SmoothTransformation
            )
            # Center it
            x = (self.size - scaled.width()) // 2
            y = (self.size - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # Draw placeholder
            painter.setBrush(QBrush(QColor("#2d2d2d")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(self.size // 3)
            font.setBold(True)
            painter.setFont(font)
            
            # Initial letter
            initial = self.client.name[0].upper() if self.client.name else "?"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initial)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._change_avatar()
        super().mouseReleaseEvent(event)

    def _change_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите фото",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return

        try:
            db_folder = self.bridge.app_settings.get('database_path', self.bridge.storage_db_dir())
            avatars_dir = os.path.join(db_folder, "attached_files", "avatars")
            os.makedirs(avatars_dir, exist_ok=True)

            ext = os.path.splitext(file_path)[1]
            new_filename = f"avatar_{self.client.id}{ext}"
            new_path_abs = os.path.join(avatars_dir, new_filename)

            # Copy file
            shutil.copy2(file_path, new_path_abs)

            # Delete old avatar if it exists and is different
            if self.client.avatar_path:
                old_path = self.client.avatar_path
                if not os.path.isabs(old_path):
                    old_path = os.path.normpath(os.path.join(db_folder, old_path))
                if os.path.exists(old_path) and old_path != new_path_abs:
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            # Store relative path
            rel_path = os.path.join("attached_files", "avatars", new_filename).replace('\\', '/')
            self.client.avatar_path = rel_path
            
            self._load_avatar()
            self.update()
            
            self.avatar_changed.emit(rel_path)
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить фото:\n{e}")
