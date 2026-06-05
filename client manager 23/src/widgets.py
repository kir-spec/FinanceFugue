import os
import platform
import logging
from .logger import get_logger

logger = get_logger("Widgets")
import subprocess
import zipfile
import shutil
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QMenu, QInputDialog, QLineEdit, QFrame,
    QCheckBox, QDialog, QFormLayout, QComboBox, QDateEdit,
    QDialogButtonBox, QFileDialog, QTextEdit, QSizePolicy,
    QListWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QRectF, QSize, Signal as pyqtSignal
from PySide6.QtGui import QAction, QDoubleValidator, QFont, QFontMetrics, QGuiApplication, QPainter, QColor, QPen, QLinearGradient, QPainterPath

from .models import ProjectFile, Order
class AutoResizeLabel(QLabel):
    def __init__(self, text="", parent=None, min_size=12, max_size=24):
        super().__init__(text, parent)
        self.min_size = min_size
        self.max_size = max_size
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(30)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_font()
        
    def adjust_font(self):
        text = self.text()
        if not text:
            return
            
        # Начинаем с максимального размера
        font = self.font()
        font.setPixelSize(self.max_size)
        
        # Доступная ширина (с учетом отступов)
        available_width = self.width() - 10
        if available_width <= 0: return

        fm = QFontMetrics(font)
        
        # Уменьшаем шрифт пока текст не влезет или не достигнем минимума
        current_size = self.max_size
        while fm.horizontalAdvance(text) > available_width and current_size > self.min_size:
            current_size -= 1
            font.setPixelSize(current_size)
            fm = QFontMetrics(font)
            
        self.setFont(font)
class HelpButtonMixin:
    # Mixin to easily add contextual help button to any QWidget subclass
    
    def init_help_button(self, parent_app, context_key, layout_to_add_to=None):
        self.parent_app = parent_app
        self.context_key = context_key
        
        # 1. Create Button
        self.help_btn = QPushButton("❓")
        self.help_btn.setFixedSize(26, 26)
        
        # Style based on request: round, red '?' on light/neutral background
        self.help_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; /* Light/Neutral background */
                color: #D32F2F; /* Red question mark */
                border: 2px solid #AAAAAA;
                border-radius: 13px; /* Round */
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #EEEEEE;
                border-color: #FF4B2B; /* Slightly brighter on hover */
            }
        """)
        
        self.help_btn.setToolTip("Справка по текущему окну")
        self.help_btn.clicked.connect(self.show_contextual_help)
        
        # 2. Place button in layout (if provided)
        if layout_to_add_to:
            layout_to_add_to.addWidget(self.help_btn)
        
        return self.help_btn

    def show_contextual_help(self):
        if not self.parent_app:
            QMessageBox.critical(self, "Ошибка", "Нет доступа к главному приложению для получения справки.")
            return
            
        context = {}
        if hasattr(self, 'get_help_context'):
            context = self.get_help_context()
            
        if not hasattr(self.parent_app, 'get_help_text'):
            # Fallback if parent_app is not the main FinanceFugue window but has the method
            # In some cases parent_app might be passed down
            QMessageBox.critical(self, "Ошибка", "Главное приложение не предоставляет функцию получения справки.")
            return

        help_html = self.parent_app.get_help_text(self.context_key, context)
        
        if not help_html:
            help_html = f"<p>⚠️ Справка для раздела '{self.context_key}' временно недоступна.</p>"

        title = "Справка FinanceFugue"
        
        # Local import to avoid circular dependency
        from .dialogs import ContextualHelpDialog
        dialog = ContextualHelpDialog(title, help_html, self)
        dialog.exec()

class HoverShadowFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_shadow()
        
    def init_shadow(self):
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(4)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(self.shadow)
        
        # Animation props
        self._blur_radius = 15
        self._y_offset = 4
        
        # Animation objects
        self.anim_blur = QPropertyAnimation(self.shadow, b"blurRadius")
        self.anim_blur.setDuration(200)
        self.anim_blur.setEasingCurve(QEasingCurve.OutQuad)
        
        self.anim_y = QPropertyAnimation(self.shadow, b"yOffset")
        self.anim_y.setDuration(200)
        self.anim_y.setEasingCurve(QEasingCurve.OutQuad)

    def enterEvent(self, event):
        self.anim_blur.setStartValue(self.shadow.blurRadius())
        self.anim_blur.setEndValue(30)
        self.anim_blur.start()
        
        self.anim_y.setStartValue(self.shadow.yOffset())
        self.anim_y.setEndValue(8)
        self.anim_y.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim_blur.setStartValue(self.shadow.blurRadius())
        self.anim_blur.setEndValue(15)
        self.anim_blur.start()
        
        self.anim_y.setStartValue(self.shadow.yOffset())
        self.anim_y.setEndValue(4)
        self.anim_y.start()
        super().leaveEvent(event)

class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, width=120, height=28, on_text="ГОТОВО", off_text="В РАБОТЕ"):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.on_text = on_text
        self.off_text = off_text

        self._checked = False
        self._position = 0.0 # 0.0 to 1.0

        self.animation = QPropertyAnimation(self, b"position", self)
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.animation.stop()
            self.animation.setStartValue(self._position)
            self.animation.setEndValue(1.0 if checked else 0.0)
            self.animation.start()
            self.toggled.emit(checked)
        else:
            self._position = 1.0 if checked else 0.0
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 3
        radius = h / 2

        # Draw Track
        track_rect = QRectF(0, 0, w, h)
        
        # Colors: Red for OFF (not completed), Green for ON (completed)
        off_color = QColor("#D32F2F") # Red
        on_color = QColor("#28A745")  # Green
        
        # Interpolate color
        current_color = QColor()
        current_color.setRedF(off_color.redF() + (on_color.redF() - off_color.redF()) * self._position)
        current_color.setGreenF(off_color.greenF() + (on_color.greenF() - off_color.greenF()) * self._position)
        current_color.setBlueF(off_color.blueF() + (on_color.blueF() - off_color.blueF()) * self._position)

        # 3D Track Effect
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, radius, radius)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(current_color)
        painter.drawPath(track_path)
        
        # Inner shadow (simulated)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 60), 2))
        painter.drawRoundedRect(track_rect.adjusted(1, 1, -1, -1), radius, radius)

        # Draw Text
        # Text depends on state mostly, but we can fade between them or move them
        # Let's draw text centered in the available space
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        
        # Calculate knob geometry first to know where to draw text
        knob_radius = radius - margin
        knob_diameter = knob_radius * 2
        min_x = margin
        max_x = w - margin - knob_diameter
        current_x = min_x + (max_x - min_x) * self._position
        
        # Draw "НЕ ВЫПОЛНЕН" if we are closer to left (OFF)
        # Draw "ВЫПОЛНЕН" if closer to right (ON)
        # Or fade them.
        
        text_rect = QRectF(0, 0, w, h)
        
        # Opacity for text
        # If pos is 0 (left) -> "НЕ ВЫПОЛНЕН" opacity 1
        # If pos is 1 (right) -> "ВЫПОЛНЕН" opacity 1
        
        # Draw Left Text ("НЕ ВЫПОЛНЕН") - visible when OFF
        opacity_off = 1.0 - self._position
        if opacity_off > 0.1:
            painter.setPen(QColor(255, 255, 255, int(255 * opacity_off)))
            # Align right of the knob space (knob is on left)
            # Align right of the knob space (knob is on left)
            off_text_rect = QRectF(current_x + knob_diameter, 0, w - (current_x + knob_diameter), h)
            painter.drawText(off_text_rect, Qt.AlignmentFlag.AlignCenter, self.off_text)

        # Draw Right Text ("ВЫПОЛНЕН") - visible when ON
        opacity_on = self._position
        if opacity_on > 0.1:
            painter.setPen(QColor(255, 255, 255, int(255 * opacity_on)))
            # Align left of the knob space (knob is on right)
            on_text_rect = QRectF(0, 0, current_x, h)
            painter.drawText(on_text_rect, Qt.AlignmentFlag.AlignCenter, self.on_text)

        # Draw Knob
        knob_rect = QRectF(current_x, margin, knob_diameter, knob_diameter)
        
        # Knob Gradient
        knob_gradient = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomLeft())
        knob_gradient.setColorAt(0.0, QColor("#FFFFFF"))
        knob_gradient.setColorAt(1.0, QColor("#B0B0B0"))
        
        painter.setPen(QPen(QColor(0,0,0, 40), 1))
        painter.setBrush(knob_gradient)
        painter.drawEllipse(knob_rect)

class ClickableCardWidget(QFrame):
    clicked = Signal(str) # Отправляет ID или тип выбранной карточки

    def __init__(self, card_id, title, description, icon_text, parent=None):
        super().__init__(parent)
        self.card_id = card_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(260, 160)
        
        self.is_selected = False
        
        self.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 12px;
                padding: 12px;
            }
            QFrame:hover {
                border: 2px solid #00D1FF;
            }
            QFrame.selected {
                border: 2px solid #28A745;
                background-color: #3A3A3A;
            }
            QLabel {
                color: #DDDDDD;
                background: transparent;
                border: none;
            }
            QLabel#CardTitle {
                font-size: 15px; /* Уменьшаем размер шрифта заголовка */
                font-weight: bold;
                color: #00D1FF;
            }
            QLabel#CardDescription {
                font-size: 10px; /* Уменьшаем размер шрифта описания */
                color: #AAAAAA;
                line-height: 130%; /* Уменьшаем межстрочный интервал */
            }
            QLabel#CardIcon {
                font-size: 28px; /* Уменьшаем размер иконки */
                color: #FFFFFF;
                qproperty-alignment: AlignCenter;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) # Уменьшаем отступы
        layout.setSpacing(3) # Уменьшаем интервал

        self.icon_label = QLabel(icon_text)
        self.icon_label.setObjectName("CardIcon")
        layout.addWidget(self.icon_label)
        
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.description_label = QLabel(description)
        self.description_label.setObjectName("CardDescription")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.card_id)
        super().mousePressEvent(event)

    def setSelected(self, selected):
        self.is_selected = selected
        if selected:
            self.setProperty("class", "selected")
        else:
            self.setProperty("class", "")
        self.style().polish(self) # Обновить стиль
        self.update()

class ClientListWidget(QListWidget):
    folderDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Проверяем, есть ли среди перетаскиваемого хотя бы одна папка
            for url in event.mimeData().urls():
                if os.path.isdir(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
             event.acceptProposedAction()
        else:
             event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.folderDropped.emit(path)

class ClickableStatBox(QFrame):
    clicked = Signal()

    def __init__(self, title, value, color, check_debt=False, currency='RUB', parent=None):
        super().__init__(parent)
        self.currency = currency
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
            }
            QFrame:hover {
                border: 1px solid #00D1FF;
                background-color: #2E2E2E;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.val_label = QLabel(self.format_money(value))
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        text_color = color
        if check_debt and value <= 0:
            text_color = "#777777"
            
        self.val_label.setStyleSheet(f"font-size: 20px; color: {text_color}; font-weight: bold; border: none; background: transparent;")
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        
        layout.addWidget(self.val_label)
        layout.addWidget(title_label)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        super().mouseReleaseEvent(event)

    def format_money(self, value):
        return f"{value:,.0f} {self.currency}"

class ClientStatsWidget(QFrame):
    # Сигналы для каждого блока
    sum_clicked = Signal()
    paid_clicked = Signal()
    adv_clicked = Signal()
    debt_clicked = Signal()

    def __init__(self, stats, currency='RUB', parent=None):
        super().__init__(parent)
        self.currency = currency
        self.init_ui(stats)

    def init_ui(self, stats):
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(0, 10, 0, 10)
        
        self.sum_box = ClickableStatBox("СУММА ЗАКАЗОВ", stats['total_sum'], "#00D1FF", currency=self.currency)
        self.sum_box.clicked.connect(self.sum_clicked)
        
        self.paid_box = ClickableStatBox("ВСЕГО ОПЛАЧЕНО", stats['total_received'], "#28A745", currency=self.currency)
        self.paid_box.clicked.connect(self.paid_clicked)

        self.adv_box = ClickableStatBox("АВАНСЫ", stats['total_advance'], "#FFD700", currency=self.currency)
        self.adv_box.clicked.connect(self.adv_clicked)

        self.debt_box = ClickableStatBox("ДОЛГ", stats['total_debt'], "#FF4B2B", check_debt=True, currency=self.currency)
        self.debt_box.clicked.connect(self.debt_clicked)

        self.layout.addWidget(self.sum_box)
        self.layout.addWidget(self.paid_box)
        self.layout.addWidget(self.adv_box)
        self.layout.addWidget(self.debt_box)

    def update_stats(self, stats):
        self.sum_box.val_label.setText(self.sum_box.format_money(stats['total_sum']))
        self.paid_box.val_label.setText(self.paid_box.format_money(stats['total_received']))
        self.adv_box.val_label.setText(self.adv_box.format_money(stats['total_advance']))
        self.debt_box.val_label.setText(self.debt_box.format_money(stats['total_debt']))
        
        debt_color = "#777777" if stats['total_debt'] <= 0 else "#FF4B2B"
        self.debt_box.val_label.setStyleSheet(f"font-size: 20px; color: {debt_color}; font-weight: bold; border: none; background: transparent;")

class AdaptiveDashLabel(QLabel):
    def __init__(self, value, color, is_money=True, parent=None):
        super().__init__(parent)
        self._value = 0.0 # Internal value for animation
        self.target_value = float(value)
        self.text_color = color
        self.is_money = is_money
        self.is_condensed = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(50)
        
        # Animation
        self.anim = QPropertyAnimation(self, b"animated_value", self)
        self.anim.setDuration(800)
        self.anim.setEasingCurve(QEasingCurve.OutExpo)
        
        # Start animation immediately to target
        self.animated_value = self.target_value # Set initial without anim to avoid 0-jump on creation if desired, OR animate from 0
        # Let's animate from 0 for "intro" effect or from current for updates
        # For initialization, let's just set it.
        self.update_display()

    @Property(float)
    def animated_value(self):
        return self._value

    @animated_value.setter
    def animated_value(self, val):
        self._value = val
        self.update_display()

    def set_value(self, new_value):
        if self.target_value != new_value:
            self.anim.stop()
            self.anim.setStartValue(self._value)
            self.anim.setEndValue(float(new_value))
            self.target_value = float(new_value)
            self.anim.start()

    def update_display(self):
        current_val = self._value
        
        # 1. Подготовка текста
        if self.is_money:
            self.display_text = f"{current_val:,.0f}".replace(",", " ")
            self.digits_count = len(str(int(abs(current_val))))
        else:
            if current_val == int(current_val):
                self.display_text = str(int(current_val))
            else:
                self.display_text = f"{current_val:.1f}"
            self.digits_count = len(self.display_text)

        # 2. Расчет базового размера шрифта
        base_size = 26
        if self.is_money:
            if 7 <= self.digits_count <= 9:
                self.target_font_size = int(base_size * 0.85)
            elif 10 <= self.digits_count <= 12:
                self.target_font_size = int(base_size * 0.70)
            elif self.digits_count > 12:
                self.target_font_size = int(base_size * 0.60)
            else:
                self.target_font_size = base_size
        else:
            self.target_font_size = base_size

        self.is_condensed = False
        self.render_html()

    def render_html(self, condensed=None):
        if condensed is not None:
            self.is_condensed = condensed
            
        font_weight = "bold" if not self.is_condensed else "normal"
        letter_spacing = "0px" if not self.is_condensed else "-0.5px"
        
        # Основной стиль текста
        style = f"font-size:{self.target_font_size}px; color:{self.text_color}; font-weight:{font_weight}; letter-spacing:{letter_spacing};"
        
        if self.is_money:
            # Символ рубля меньше на ~20%
            rub_size = int(self.target_font_size * 0.8)
            html = f'<span style="{style}">{self.display_text}</span>'
            html += f'<span style="font-size:{rub_size}px; color:{self.text_color}; opacity:0.7; font-weight:normal;"> ₽</span>'
        else:
            html = f'<span style="{style}">{self.display_text}</span>'
        
        self.setText(html)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.check_overflow()

    def check_overflow(self):
        # Проверка на переполнение контейнера
        avail_width = self.width()
        if avail_width <= 0:
            return

        # Приблизительная оценка ширины текста
        # Используем QFontMetrics с аналогичными настройками
        font = QFont()
        font.setPixelSize(self.target_font_size)
        font.setBold(True)
        fm = QFontMetrics(font)
        
        text_width = fm.horizontalAdvance(self.display_text)
        if self.is_money:
             # Добавляем ширину символа рубля (он меньше)
            font_rub = QFont()
            font_rub.setPixelSize(int(self.target_font_size * 0.8))
            fm_rub = QFontMetrics(font_rub)
            text_width += fm_rub.horizontalAdvance(" ₽")
        
        # Если текст шире контейнера, применяем сжатый стиль
        # Добавляем небольшой запас (padding)
        should_be_condensed = text_width > (avail_width - 10)
        
        if should_be_condensed != self.is_condensed:
            self.render_html(condensed=should_be_condensed)

class FileItemWidget(QWidget):
    statusChanged = pyqtSignal()
    renameRequested = pyqtSignal(str, str)  # old_path, new_name
    
    def __init__(self, file_obj: ProjectFile, parent_app):
        super().__init__()
        self.file_obj = file_obj
        self.parent_app = parent_app
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Определяем иконку или префикс в зависимости от типа
        is_folder = getattr(file_obj, 'is_folder', os.path.isdir(file_obj.path))
        prefix = "📁 " if is_folder else "📄 "
        
        # Название файла/папки
        self.name_label = QLabel(f"{prefix}{file_obj.name}")
        
        # Стилизуем папку иначе
        if is_folder:
            self.name_label.setStyleSheet("color: #00D1FF; font-size: 13px; font-weight: bold;")
            open_text = "Открыть"
        else:
            self.name_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")
            open_text = "Открыть"
            
        self.name_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.name_label.customContextMenuRequested.connect(self.show_context_menu)
        
        # Кнопка открытия файла/папки (делаем ее кликабельной на самом названии)
        # self.name_label.mousePressEvent = lambda e: self.open_file() # Перехват клика
        
        # Но у нас есть отдельная кнопка Open. Сделаем кнопку более заметной для папки?
        
        btn_open = QPushButton(open_text)
        btn_open.setFixedWidth(60)
        btn_open.clicked.connect(self.open_file)
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        # Кнопка удаления файла
        btn_delete = QPushButton("Удалить")
        btn_delete.setFixedWidth(60)
        btn_delete.clicked.connect(self.delete_file)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: 1px solid #DC3545;
                padding: 4px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """)
        
        layout.addWidget(self.name_label, 1)
        layout.addWidget(btn_open)
        layout.addWidget(btn_delete)
        
        # Делаем label кликабельным как кнопку
        self.name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.name_label.mouseReleaseEvent = lambda e: self.open_file()
    
    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        open_action = QAction("📂 Открыть", self)
        open_action.triggered.connect(self.open_file)
        menu.addAction(open_action)
        
        show_folder_action = QAction("🔍 Показать в папке", self)
        show_folder_action.triggered.connect(self.show_in_folder)
        menu.addAction(show_folder_action)
        
        copy_path_action = QAction("🔗 Копировать путь", self)
        copy_path_action.triggered.connect(self.copy_absolute_path)
        menu.addAction(copy_path_action)
        
        menu.addSeparator()
        
        rename_action = QAction("✏️ Переименовать", self)
        rename_action.triggered.connect(self.rename_file)
        menu.addAction(rename_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ Удалить из заказа", self)
        delete_action.triggered.connect(self.delete_file)
        menu.addAction(delete_action)
        
        menu.exec(self.name_label.mapToGlobal(pos))

    def show_in_folder(self):
        """Открывает папку и выделяет файл"""
        path = os.path.abspath(self.file_obj.path)
        if not os.path.exists(path):
            return
            
        if platform.system() == "Windows":
            subprocess.run(['explorer', '/select,', path])
        elif platform.system() == "Darwin":
            subprocess.run(['open', '-R', path])
        else:
            # Для Linux обычно просто открываем родительскую папку
            subprocess.run(['xdg-open', os.path.dirname(path)])

    def copy_absolute_path(self):
        """Копирует полный путь в буфер обмена"""
        QGuiApplication.clipboard().setText(os.path.abspath(self.file_obj.path))
    
    def rename_file(self):
        new_name, ok = QInputDialog.getText(
            self,
            "Переименование файла",
            "Введите новое имя файла:",
            QLineEdit.EchoMode.Normal,
            self.file_obj.name
        )
        
        if ok and new_name.strip() and new_name != self.file_obj.name:
            old_path = self.file_obj.path
            old_dir = os.path.dirname(old_path)
            new_path = os.path.join(old_dir, new_name.strip())
            
            try:
                # Переименовываем файл в файловой системе
                os.rename(old_path, new_path)
                
                # Обновляем объект файла
                self.file_obj.path = new_path
                self.file_obj.name = new_name.strip()
                self.name_label.setText(new_name.strip())
                
                # Сохраняем изменения
                self.parent_app.save_db()
                QMessageBox.information(self, "Успех", "Файл переименован")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать файл: {e}")
    
    def mouseReleaseEvent(self, event):
        # Обработка клика по виджету для открытия
        self.open_file()
        super().mouseReleaseEvent(event)

    def open_file(self):
        try:
            path = self.file_obj.path
            if os.path.exists(path):
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            else:
                # Пытаемся проверить, может это относительный путь?
                # Но у нас хранятся абсолютные пути обычно.
                QMessageBox.warning(self, "Объект не найден", f"Объект '{self.file_obj.name}' не найден по пути:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть объект: {e}")
    
    def delete_file(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление файла")
        msg_box.setText(f"Вы уверены, что хотите удалить файл '{self.file_obj.name}' из заказа?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            # Находим заказ, которому принадлежит файл
            for client in self.parent_app.clients:
                for order in client.orders:
                    if self.file_obj in order.files:
                        order.files.remove(self.file_obj)
                        
                        # SQLite delete
                        self.parent_app.sqlite.delete_file(order.id, self.file_obj.path)
                        
                        self.parent_app.render_client_profile()
                        self.parent_app.save_db() # UI update
                        return

class OrderWidget(HoverShadowFrame, HelpButtonMixin):
    def __init__(self, order: Order, parent_app):
        super().__init__()
        self.order = order
        self.parent_app = parent_app
        self.setAcceptDrops(True)  # Разрешаем drag and drop

        # Initialize Help Button
        self.init_help_button(
            parent_app=parent_app,
            context_key="order_details",
            layout_to_add_to=None
        )
        
        self.init_ui()
        # self.update_deadline_color() # Вызов перенесен ниже, после создания deadline_edit
        
        # Placement: Top right of the header row (L855)
        header_layout = self.main_layout.itemAt(0).layout()
        header_layout.addWidget(self.help_btn)


    def get_help_context(self):
        # Context for Order Widget
        return {
            "order_id": self.order.id,
            "status": self.order.status,
            "debt": self.order.debt,
            "deadline": self.order.deadline
        }

    def init_ui(self):
        self.setStyleSheet("""
            QFrame#OrderCard {
                background-color: #2A2A2A;
                border-radius: 8px;
                border: 1px solid #3D3D3D;
                margin-bottom: 5px;
            }
        """)
        self.setObjectName("OrderCard")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(4)

        # Заголовок
        header = QHBoxLayout()
        
        # Явная стрелка для сворачивания - СЛЕВА
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.clicked.connect(self.toggle_contents)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D;
                color: #00D1FF;
                border: 1px solid #555555;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #4D4D4D;
                color: #FFFFFF;
                border-color: #00D1FF;
            }
        """)

        title = QLabel(f"{self.order.service_type}")
        title.setStyleSheet("font-weight: bold; color: #00D1FF; font-size: 18px;")
        
        # Кнопка настроек (шестеренка)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.clicked.connect(self.show_settings_menu)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
                border-color: #666666;
            }
        """)

        # Тумблер "Выполнен"
        self.status_switch = ToggleSwitch(width=110, height=26, on_text="ГОТОВО", off_text="В РАБОТЕ")
        self.status_switch.setChecked(self.order.status == "Завершен")
        self.status_switch.toggled.connect(self.update_order_status)
        
        # Метка статуса рядом с тумблером (опционально)
        # status_label = QLabel("Выполнен")
        # status_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")

        header.addWidget(self.toggle_btn)
        header.addWidget(title)
        header.addSpacing(10)
        # header.addWidget(status_label)
        header.addWidget(self.status_switch)
        header.addWidget(self.settings_btn)
        header.addStretch()
        self.main_layout.addLayout(header)

        # Содержимое
        self.content = QWidget()
        self.c_layout = QVBoxLayout(self.content)
        self.c_layout.setSpacing(4)
        
        # Горизонтальная линия ПЕРЕД датами
        sep_before_dates = QFrame()
        sep_before_dates.setFrameShape(QFrame.Shape.HLine)
        sep_before_dates.setStyleSheet("background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 3px 0;")
        self.c_layout.addWidget(sep_before_dates)
        
        # Информация (ID и дата заказа)
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Редактируемая дата заказа
        date_box = QWidget()
        date_box_layout = QHBoxLayout(date_box)
        date_box_layout.setContentsMargins(0,0,0,0)
        date_box_layout.setSpacing(5)
        
        start_date_label = QLabel("📅 Дата заказа:")
        start_date_label.setStyleSheet("color: #28A745; font-size: 14px; font-weight: bold;")
        
        self.order_date_edit = QDateEdit()
        self.order_date_edit.setCalendarPopup(True)
        self.order_date_edit.setDisplayFormat("dd.MM.yyyy")
        try:
            if self.order.created_at:
                d_str = self.order.created_at.split()[0]
                self.order_date_edit.setDate(datetime.strptime(d_str, "%d.%m.%Y").date())
            else:
                self.order_date_edit.setDate(datetime.now().date())
        except:
            self.order_date_edit.setDate(datetime.now().date())
            
        self.order_date_edit.setFixedWidth(110)
        self.order_date_edit.dateChanged.connect(self.sync_order_date)
        self.order_date_edit.setStyleSheet("""
            QDateEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                font-size: 14px;
                font-weight: bold;
                padding: 4px 6px;
                border-radius: 3px;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
                background-color: #444444;
            }
            QDateEdit::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                width: 0;
                height: 0;
                margin-top: 2px;
            }
        """)
        
        date_box_layout.addWidget(start_date_label)
        date_box_layout.addWidget(self.order_date_edit)
        info_layout.addWidget(date_box)
        
        # Срок выполнения
        deadline_box = QWidget()
        deadline_layout = QHBoxLayout(deadline_box)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_layout.setSpacing(5)
        
        deadline_label = QLabel("⏰ Срок:")
        deadline_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("dd.MM.yyyy")
        self.deadline_edit.setFixedWidth(110)
        
        if self.order.deadline:
            try:
                self.deadline_edit.setDate(datetime.strptime(self.order.deadline, "%d.%m.%Y").date())
            except:
                self.deadline_edit.setDate(datetime.now().date())
        else:
            self.deadline_edit.setDate(datetime.now().date())
            
        self.deadline_edit.dateChanged.connect(self.sync_deadline)
        
        deadline_layout.addWidget(deadline_label)
        deadline_layout.addWidget(self.deadline_edit)
        
        info_layout.addWidget(deadline_box)
        info_layout.addStretch()
        
        self.update_deadline_color()
        
        self.c_layout.addWidget(info_widget)
        
        # Горизонтальная линия ПОСЛЕ дат
        sep_after_dates = QFrame()
        sep_after_dates.setFrameShape(QFrame.Shape.HLine)
        sep_after_dates.setStyleSheet("background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 3px 0;")
        self.c_layout.addWidget(sep_after_dates)
        
        # Финансовый блок
        financial_container = QWidget()
        financial_layout = QVBoxLayout(financial_container)
        financial_layout.setContentsMargins(0, 2, 0, 2)
        financial_layout.setSpacing(8)

        # Верхняя строка: Стоимость, Аванс, Долг
        money_row = QHBoxLayout()
        money_row.setSpacing(15)

        # Функция для создания стилизованного блока ввода с меткой
        def create_money_box(label_text, value, color, callback):
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #DDDDDD; font-size: 12px; font-weight: bold;")
            
            edit = QLineEdit(self.format_number(value))
            # Ширина должна быть одинаковой и соответствовать ширине нижних блоков
            # 120 + 120 + 10 (spacing) = ~250 на блок, здесь 3 блока
            # Сделаем чуть шире
            edit.setFixedWidth(120)
            edit.editingFinished.connect(callback)
            edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #252525;
                    color: {color};
                    border: 1px solid #444444;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                QLineEdit:focus {{
                    border: 1px solid {color};
                }}
            """)
            layout.addWidget(lbl)
            layout.addWidget(edit)
            return box, edit

        # Reactive Controller Pattern bindings
        cost_box, self.cost_edit = create_money_box("СТОИМОСТЬ", self.order.price, "#00D1FF", lambda: self.on_field_change("price"))
        advance_box, self.advance_edit = create_money_box("АВАНС", self.order.advance, "#FFD700", lambda: self.on_field_change("advance"))
        debt_box, self.debt_edit = create_money_box("ДОЛГ", self.order.debt, "#FF4B2B", lambda: self.on_field_change("debt"))

        money_row.addWidget(cost_box)
        money_row.addWidget(advance_box)
        money_row.addWidget(debt_box)
        money_row.addStretch()
        
        financial_layout.addLayout(money_row)
        
        # Разделитель между финансовыми полями и блоком платежей/файлов
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setStyleSheet("background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 5px 0;")
        financial_layout.addWidget(sep_line)

        # Нижний блок: Платежи (слева) и Файлы (справа)
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        bottom_layout.setSpacing(10)

        # --- Блок Платежей: С рамкой ---
        payments_frame = QFrame()
        payments_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        payments_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                background-color: #2D2D2D;
            }
            QLabel { border: none; background: transparent; }
            QPushButton { border-radius: 4px; }
        """)
        payments_box_layout = QVBoxLayout(payments_frame)
        payments_box_layout.setContentsMargins(10, 4, 10, 8)
        payments_box_layout.setSpacing(4)
        
        payments_label = QLabel("ПЛАТЕЖИ:")
        payments_label.setStyleSheet("color: #DDDDDD; font-size: 12px; font-weight: bold;")
        
        btns_row = QHBoxLayout()
        btns_row.setSpacing(10)
        
        add_payment_btn = QPushButton("✚ добавить")
        add_payment_btn.clicked.connect(self.add_payment_dialog)
        add_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        history_payment_btn = QPushButton("📋 история")
        history_payment_btn.clicked.connect(self.show_payments_history)
        history_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                font-weight: bold;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056A3;
            }
        """)
        
        btns_row.addWidget(add_payment_btn)
        btns_row.addWidget(history_payment_btn)
        # btns_row.addStretch() # Убрали stretch, чтобы рамка сжималась
        
        # Статус оплаты (Switch Button)
        self.payment_status_btn = QPushButton()
        self.payment_status_btn.setCheckable(True)
        self.payment_status_btn.clicked.connect(self.on_payment_status_toggle)
        self.payment_status_btn.setFixedHeight(26)
        self.payment_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.payment_status_btn.setStyleSheet("""
            QPushButton {
                border-radius: 13px;
                padding: 0 15px;
                font-weight: bold;
                font-size: 12px;
                border: none;
            }
        """)
        
        payments_box_layout.addWidget(payments_label)
        payments_box_layout.addLayout(btns_row)
        payments_box_layout.addWidget(self.payment_status_btn) # Добавляем кнопку-свитч
        
        # Добавляем блок платежей в нижний лэйаут
        bottom_layout.addWidget(payments_frame)
        
        # Разделитель между блоком платежей и файлов
        vertical_sep = QFrame()
        vertical_sep.setFrameShape(QFrame.Shape.VLine)
        vertical_sep.setStyleSheet("background-color: #3D3D3D; min-width: 1px; max-width: 1px; border: none; margin: 0 5px;")
        bottom_layout.addWidget(vertical_sep)

        # --- Блок Файлов (справа) ---
        files_widget = QWidget()
        self.files_layout = QVBoxLayout(files_widget)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(2)
        
        # Заголовок файлов
        files_header = QHBoxLayout()
        
        # Считаем количество элементов
        files_count = len(self.order.files)
        files_label = QLabel(f"📎 Файлы ({files_count}):")
        files_label.setStyleSheet("font-weight: bold; color: #DDDDDD; font-size: 13px;")
        
        files_header.addWidget(files_label)
        files_header.addStretch()
        
        self.files_layout.addLayout(files_header)
        
        if not self.order.files:
            drag_label = QLabel("Перетащите файлы сюда")
            drag_label.setStyleSheet("color: #DDDDDD; font-size: 12px; font-style: italic; padding: 5px 10px; background-color: #252525; border-radius: 4px; border: 1px dashed #555555;")
            drag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            drag_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            
            # Контейнер для drag_label, чтобы он не растягивался на всю ширину
            drag_container = QWidget()
            drag_container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            drag_layout = QHBoxLayout(drag_container)
            drag_layout.setContentsMargins(0,0,0,0)
            drag_layout.addWidget(drag_label)

            self.files_layout.addWidget(drag_container)
        
        # Список файлов
        if self.order.files:
            # Сортируем: сначала папки, потом файлы
            sorted_files = sorted(self.order.files, key=lambda x: (not getattr(x, 'is_folder', os.path.isdir(x.path)), x.name.lower()))
            
            # Показываем только первые 5 файлов
            displayed_files = sorted_files[:5]
            hidden_count = len(sorted_files) - 5
            
            for f in displayed_files:
                if not hasattr(f, 'is_folder'):
                    f.is_folder = os.path.isdir(f.path)
                fw = FileItemWidget(f, self.parent_app)
                fw.statusChanged.connect(self.parent_app.save_db)
                self.files_layout.addWidget(fw)
            
            # Кнопка "Еще..."
            if hidden_count > 0:
                more_btn = QPushButton(f"Еще {hidden_count} файлов...")
                more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                more_btn.clicked.connect(self.open_internal_file_manager)
                more_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #00D1FF;
                        border: 1px dashed #444444;
                        border-radius: 4px;
                        padding: 6px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #333333;
                        color: #FFFFFF;
                        border-color: #00D1FF;
                    }
                """)
                self.files_layout.addWidget(more_btn)

        # Кнопки управления файлами
        btns_container = QWidget()
        btns_container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        btns = QHBoxLayout(btns_container)
        btns.setContentsMargins(0,0,0,0)
        btns.setSpacing(5)

        b_f = QPushButton("+ Добавить")
        b_f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_f.clicked.connect(self.add_file)
        b_f.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        b_z = QPushButton("📦 Экспорт")
        b_z.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_z.clicked.connect(self.export_files_to_zip)
        b_z.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        btns.addWidget(b_f)
        btns.addWidget(b_z)
        
        self.files_layout.addWidget(btns_container)
        self.files_layout.addStretch() # Прижимаем файлы к верху
        
        bottom_layout.addWidget(files_widget, 1) # Файлы занимают оставшееся место
        bottom_layout.addStretch()
        
        # Добавляем финансовый блок (в котором теперь только цифры) и нижний блок в основной лэйаут
        financial_layout.addWidget(bottom_container)
        
        self.c_layout.addWidget(financial_container)

        self.main_layout.addWidget(self.content)

    # Drag and drop методы
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        files_to_add = []
        folders_to_handle = []
        
        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files_to_add.append(file_path)
            elif os.path.isdir(file_path):
                folders_to_handle.append(file_path)
        
        # Обрабатываем папки
        for folder_path in folders_to_handle:
            # Считаем файлы в папке
            all_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            if len(all_files) > 5:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Много файлов в папке")
                msg_box.setText(f"В папке '{os.path.basename(folder_path)}' найдено {len(all_files)} файлов.")
                msg_box.setInformativeText("Как вы хотите добавить эту папку?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                
                btn_add_all = msg_box.addButton("Добавить все файлы", QMessageBox.ButtonRole.YesRole)
                btn_link = msg_box.addButton("Создать ссылку на папку", QMessageBox.ButtonRole.NoRole)
                btn_cancel = msg_box.addButton("Пропустить", QMessageBox.ButtonRole.RejectRole)
                
                msg_box.exec()
                
                clicked_button = msg_box.clickedButton()
                
                if clicked_button == btn_add_all:
                    files_to_add.extend(all_files)
                elif clicked_button == btn_link:
                    # Создаем кнопку для доступа к папке
                    self.add_folder_access_button(folder_path)
                # Если Cancel - пропускаем эту папку
            else:
                files_to_add.extend(all_files)
        
        # Обрабатываем файлы
        for file_path in files_to_add:
            self.add_file_with_storage_option(file_path)
        
        self.parent_app.render_client_profile()
        self.parent_app.save_db()

    def add_folder_access_button(self, folder_path):
        """Добавляет кнопку для быстрого доступа к папке"""
        folder_name = os.path.basename(folder_path)
        
        # Создаем специальный файл-ссылку (в реальной системе это может быть текстовый файл с путем)
        link_file_path = os.path.join(os.path.dirname(folder_path), f"LINK_{folder_name}.txt")
        with open(link_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Ссылка на папку: {folder_path}\n")
            f.write(f"Добавлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        # Добавляем как обычный файл
        project_file = ProjectFile(
            path=link_file_path,
            name=f"📁 Доступ к папке: {folder_name}",
            is_finished=False
        )
        self.order.files.append(project_file)
        
        # Также добавляем кнопку открытия папки
        self.create_folder_access_widget(folder_path)

    def create_folder_access_widget(self, folder_path):
        """Создает виджет с кнопкой доступа к папке"""
        folder_widget = QWidget()
        folder_layout = QHBoxLayout(folder_widget)
        folder_layout.setContentsMargins(5, 2, 5, 2)
        
        folder_label = QLabel(f"📁 {os.path.basename(folder_path)}")
        folder_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")
        
        open_btn = QPushButton("Открыть папку")
        open_btn.setFixedWidth(80)
        open_btn.clicked.connect(lambda: self.open_folder(folder_path))
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        folder_layout.addWidget(folder_label, 1)
        folder_layout.addWidget(open_btn)
        
        # Вставляем виджет перед кнопками управления файлами
        # Кнопки (btns) - это последний Layout в self.files_layout
        # insertWidget работает с виджетами. Поскольку кнопки - это Layout, они учитываются в count(), но вставка перед ними может быть сложнее
        # Проще добавить в конец, если кнопок нет, или пересобрать.
        # Но у нас кнопки всегда есть.
        
        # Попробуем вставить перед кнопками (предпоследняя позиция, т.к. stretch последний)
        count = self.files_layout.count()
        if count >= 2:
            self.files_layout.insertWidget(count - 2, folder_widget)
        else:
            self.files_layout.addWidget(folder_widget)

    def open_internal_file_manager(self):
        """Открывает внутренний менеджер файлов"""
        from .dialogs import InternalFileManagerDialog
        dialog = InternalFileManagerDialog(self.order, self.parent_app)
        dialog.exec()
        # Обновляем список после закрытия (если были изменения)
        self.parent_app.render_client_profile()

    def open_folder(self, folder_path):
        """Открывает папку в проводнике"""
        if os.path.exists(folder_path):
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        else:
            QMessageBox.warning(self, "Папка не найдена", f"Папка {folder_path} не существует.")

    def add_file_with_storage_option(self, file_path):
        """Добавляет файл или папку с предложением о месте хранения"""
        is_dir = os.path.isdir(file_path)
        
        if not self.parent_app.app_settings:
            # Если настройки не загружены, используем прямое добавление (как ссылку)
            self.order.files.append(ProjectFile(
                path=file_path,
                name=os.path.basename(file_path),
                is_finished=False,
                is_folder=is_dir
            ))
            return
        
        storage_mode = self.parent_app.app_settings.get('file_storage_mode', 'copy')
        
        if storage_mode == 'link':
            # Оставляем файл на месте
            final_path = file_path
        else:  # 'copy'
            # Копируем файл в папку базы данных
            db_folder = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
            files_folder = os.path.join(db_folder, "attached_files", self.order.id)
            os.makedirs(files_folder, exist_ok=True)
            
            base_name = os.path.basename(file_path)
            new_path = os.path.join(files_folder, base_name)
            
            # Проверяем, не существует ли уже файл/папка с таким именем
            counter = 1
            name, ext = os.path.splitext(base_name)
            while os.path.exists(new_path):
                new_path = os.path.join(files_folder, f"{name}_{counter}{ext}")
                counter += 1
            
            try:
                if is_dir:
                    # Копирование папки
                    shutil.copytree(file_path, new_path)
                else:
                    # Копирование файла
                    shutil.copy2(file_path, new_path)
                final_path = new_path
            except Exception as e:
                QMessageBox.warning(self, "Ошибка копирования", f"Не удалось скопировать объект: {e}")
                # Если не удалось скопировать, оставляем ссылку на оригинал
                final_path = file_path
        
        new_file = ProjectFile(
            path=final_path,
            name=os.path.basename(final_path),
            is_finished=False,
            is_folder=is_dir
        )
        self.order.files.append(new_file)
        
        # SQLite add
        client_id = None
        for c in self.parent_app.clients:
            if self.order in c.orders:
                client_id = c.id
                break
        
        if client_id:
            self.parent_app.sqlite.add_file(client_id, self.order.id, new_file)

    def format_number(self, num):
        """Форматирует число без точек"""
        if num == int(num):
            return str(int(num))
        return str(num).rstrip('0').rstrip('.') if '.' in str(num) else str(num)

    def toggle_contents(self):
        visible = self.content.isVisible()
        self.content.setVisible(not visible)
        # Меняем стрелочку в зависимости от состояния
        self.toggle_btn.setText("▲" if visible else "▼")

    def export_files_to_zip(self):
        """Экспортирует все файлы из заказа в ZIP архив"""
        ready_files = [f for f in self.order.files if os.path.exists(f.path)]
        if not ready_files:
            QMessageBox.information(
                self, 
                "Нет файлов", 
                "Нет файлов для экспорта."
            )
            return
        
        default_name = f"{self.order.service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Экспорт файлов заказа", 
            default_name,
            "ZIP архивы (*.zip)"
        )
        
        if path:
            try:
                with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in ready_files:
                        z.write(f.path, f.name)
                
                QMessageBox.information(
                    self, 
                    "Экспорт завершен", 
                    f"Файлы успешно экспортированы в архив:\n{path}\n"
                    f"Экспортировано файлов: {len(ready_files)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив: {e}")

    def on_field_change(self, field_name):
        """Reactive Event Listener"""
        widget_map = {
            "price": self.cost_edit,
            "advance": self.advance_edit,
            "debt": self.debt_edit
        }
        widget = widget_map.get(field_name)
        if not widget: return

        try:
            text = widget.text().replace(',', '.').replace(' ', '')
            new_value = float(text) if text else 0.0
        except ValueError:
            self.update_financial_display()
            return

        self.calculate_engine(field_name, new_value)

    def calculate_engine(self, field_name, new_value):
        """Central Calculation Engine implementing Reactive Controller Pattern"""
        
        # 1. Price Change Logic
        if field_name == "price":
            if new_value < 0:
                QMessageBox.warning(self.parent_app, "Ошибка", "Стоимость не может быть отрицательной")
                self.update_financial_display()
                return

            if new_value < self.order.total_received:
                # Ask user if they want to refund excess
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость ({new_value:.2f} руб.) меньше полученной суммы ({self.order.total_received:.2f} руб.).")
                msg_box.setInformativeText(f"Это приведет к возврату {self.order.total_received - new_value:.2f} руб.\nПродолжить?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                msg_box.exec()

                if msg_box.clickedButton() == btn_yes:
                    diff = self.order.total_received - new_value
                    self.order.add_payment(-diff, "корректировка", "Возврат из-за уменьшения стоимости")
                    self.order.price = new_value
                    # Auto-correct advance if needed
                    if self.order.advance > new_value:
                        self.order.advance = new_value
                else:
                    self.update_financial_display()
                    return
            elif new_value < self.order.advance:
                 # Ask user if they want to refund advance part
                diff = self.order.advance - new_value
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость меньше аванса.")
                msg_box.setInformativeText(f"Вернуть часть аванса ({diff:.2f} руб.)?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                msg_box.exec()

                if msg_box.clickedButton() == btn_yes:
                    self.order.advance = new_value
                    self.order.add_payment(-diff, "аванс", "Возврат части аванса")
                    self.order.price = new_value
                else:
                    self.update_financial_display()
                    return
            else:
                self.order.price = new_value

        # 2. Advance Change Logic
        elif field_name == "advance":
            if new_value < 0 or new_value > self.order.price:
                QMessageBox.warning(self.parent_app, "Ошибка", "Некорректная сумма аванса")
                self.update_financial_display()
                return

            delta = new_value - self.order.advance
            if delta != 0:
                # Manual override logging
                # Direction logic: if delta > 0 (Add), if delta < 0 (Subtract)
                comment = "Manual field override"
                
                if delta < 0:
                    # For safety, confirm returns
                    msg_box = QMessageBox(self.parent_app)
                    msg_box.setWindowTitle("Изменение аванса")
                    msg_box.setText(f"Уменьшение аванса создаст возврат на {abs(delta):.2f} руб.")
                    msg_box.setInformativeText("Продолжить?")
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                    btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                    msg_box.exec()
                    
                    if msg_box.clickedButton() != btn_yes:
                        self.update_financial_display()
                        return

                self.order.add_payment(delta, "аванс", comment)
                self.order.advance = new_value

        # 3. Debt Change Logic (Accounting Equation)
        elif field_name == "debt":
            if new_value < 0 or new_value > self.order.price:
                QMessageBox.warning(self.parent_app, "Ошибка", "Некорректная сумма долга")
                self.update_financial_display()
                return

            # Equation: Total = Paid + Advance + Debt
            # We need to adjust Paid (Corrections) to satisfy the new Debt value
            # Paid_New = Total - Advance - New_Debt
            # Delta_Paid = Paid_New - Paid_Old = (Total - Advance - New_Debt) - (Total - Advance - Old_Debt)
            # Delta_Paid = Old_Debt - New_Debt
            
            old_debt = self.order.debt
            delta_paid = old_debt - new_value
            
            if delta_paid != 0:
                # Direction flag logic implies: actual_adjustment = amount * direction
                # Here delta_paid is the actual signed amount
                comment = "Manual field override"
                
                if delta_paid < 0:
                    # Negative adjustment (Refund/Correction)
                    # Confirm with user for safety
                    msg_box = QMessageBox(self.parent_app)
                    msg_box.setWindowTitle("Изменение долга")
                    msg_box.setText(f"Увеличение долга создаст отрицательную корректировку (возврат) на {abs(delta_paid):.2f} руб.")
                    msg_box.setInformativeText("Продолжить?")
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                    btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                    msg_box.exec()
                    
                    if msg_box.clickedButton() != btn_yes:
                        self.update_financial_display()
                        return

                self.order.add_payment(delta_paid, "корректировка", comment)
                # Note: We don't explicitly set self.order.debt because it is a calculated property
                # based on (Price - Received). By adding payment, we effectively update the debt.

        # Bottom-Up Propagation
        self.dispatch_global_update()

    def dispatch_global_update(self):
        """Global State Propagation"""
        # 1. Update Local UI
        self.update_financial_display()
        # 2. Dispatch to Global State (App -> DB -> Dashboard)
        self.parent_app.save_db()
        # 3. Update Client Stats in Profile
        if hasattr(self.parent_app, 'update_client_stats'):
            self.parent_app.update_client_stats()

    def sync_deadline(self, qdate):
        self.order.deadline = qdate.toString("dd.MM.yyyy")
        logger.info(f"Изменен срок заказа {self.order.id}: {self.order.deadline}")
        self.update_deadline_color()
        self.parent_app.save_db()
        
    def sync_order_date(self, qdate):
        new_date = qdate.toString("dd.MM.yyyy")
        # Сохраняем время если оно было
        if " " in self.order.created_at:
            time_part = self.order.created_at.split()[1]
            self.order.created_at = f"{new_date} {time_part}"
        else:
            self.order.created_at = f"{new_date} 00:00"
        logger.info(f"Изменена дата заказа {self.order.id}: {self.order.created_at}")
        self.parent_app.save_db()
    
    def update_deadline_color(self):
        """Обновление цвета поля дедлайна в зависимости от оставшегося времени"""
        if not self.order.deadline:
            self.deadline_edit.setStyleSheet("""
                QDateEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #555555;
                    background-color: #444444;
                }
                QDateEdit::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid white;
                    width: 0;
                    height: 0;
                    margin-top: 2px;
                }
            """)
            return
            
        try:
            deadline_date = datetime.strptime(self.order.deadline, "%d.%m.%Y")
            today = datetime.now()
            days_left = (deadline_date - today).days
            
            common_style = """
                QDateEdit {
                    color: white;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #555555;
                    background-color: rgba(0,0,0,0.2);
                }
                QDateEdit::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid white;
                    width: 0;
                    height: 0;
                    margin-top: 2px;
                }
            """
            
            if days_left <= 3:
                # Осталось 3 дня или меньше - красный
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #FF4B2B; border: 1px solid #FF4B2B; }")
            elif days_left < 5:
                # Менее 5 дней (но больше 3) - желтый
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #FFA500; border: 1px solid #FFA500; color: #000000; }")
            else:
                # Более 5 дней - зеленый
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #28A745; border: 1px solid #28A745; }")
        except ValueError:
            # Неверный формат даты
            self.deadline_edit.setStyleSheet("""
                QDateEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #555555;
                    background-color: #444444;
                }
                QDateEdit::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid white;
                    width: 0;
                    height: 0;
                    margin-top: 2px;
                }
            """)

    def update_financial_display(self):
        # Обновляем поля ввода
        self.cost_edit.setText(self.format_number(self.order.price))
        self.advance_edit.setText(self.format_number(self.order.advance))
        self.debt_edit.setText(self.format_number(self.order.debt))
        
        # Обновляем статусы
        self.update_payment_status()

    def update_order_status(self, checked):
        if checked:  # Если заказ переводится в статус "Завершен"
            if self.order.debt > 0:
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Завершение заказа")
                msg_box.setText(f"У заказа есть долг в размере {self.order.debt:,.2f} ₽.")
                msg_box.setInformativeText("Хотите автоматически погасить долг и закрыть заказ?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                btn_yes = msg_box.addButton("Да, погасить долг", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет, оставить как есть", QMessageBox.ButtonRole.NoRole)
                msg_box.exec()

                if msg_box.clickedButton() == btn_yes:
                    try:
                        # Используем специальную заметку для идентификации автоматического платежа
                        self.order.add_payment(self.order.debt, "платеж", "Автоматическое погашение при завершении")
                        self.order.status = "Завершен"
                        self.dispatch_global_update()
                    except ValueError as e:
                        QMessageBox.warning(self.parent_app, "Ошибка", str(e))
                        self.status_switch.setChecked(False) # Revert toggle
                else:
                    # Пользователь отказался погашать долг, но заказ все равно должен быть завершен
                    self.order.status = "Завершен"
            else:
                self.order.status = "Завершен"
        else:
            # Если заказ переводят обратно "в работу"
            # Проверяем, был ли последний платеж автоматическим
            if self.order.payments and self.order.payments[-1].note == "Автоматическое погашение при завершении":
                last_payment = self.order.payments[-1]
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Возврат заказа в работу")
                msg_box.setText(f"Последний платеж ({last_payment.amount:,.2f} ₽) был создан автоматически.")
                msg_box.setInformativeText("Хотите отменить этот платеж и вернуть сумму в долг?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                btn_yes = msg_box.addButton("Да, отменить платеж", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет, оставить оплаченным", QMessageBox.ButtonRole.NoRole)
                msg_box.exec()

                if msg_box.clickedButton() == btn_yes:
                    try:
                        self.order.delete_payment(last_payment.id)
                        self.order.status = "В работе"
                        self.dispatch_global_update()
                    except Exception as e:
                        QMessageBox.warning(self.parent_app, "Ошибка", f"Не удалось удалить платеж: {e}")
                        self.status_switch.setChecked(True) # Revert toggle
                else:
                    # Пользователь решил оставить платеж, просто меняем статус
                    self.order.status = "В работе"
            else:
                self.order.status = "В работе"
        
        # Сохраняем и обновляем UI
        self.parent_app.save_db()
        self.dispatch_global_update()

    def update_payment_status(self):
        # Если стоимость 0
        if self.order.price == 0:
             self.payment_status_btn.setText("Бесплатно")
             self.payment_status_btn.setStyleSheet("background-color: #555555; color: #AAAAAA; border-radius: 13px; font-weight: bold; font-size: 12px;")
             self.payment_status_btn.setChecked(True)
             self.payment_status_btn.setEnabled(False)
             return

        self.payment_status_btn.setEnabled(True)
        
        # Обновляем вид кнопки в зависимости от долга
        if self.order.debt <= 0.01: # Учитываем погрешность float
            self.payment_status_btn.setText("✅ ОПЛАЧЕНО")
            self.payment_status_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28A745;
                    color: white;
                    border-radius: 13px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #218838; }
            """)
            self.payment_status_btn.setChecked(True) # State ON
        else:
            self.payment_status_btn.setText("❌ НЕ ОПЛАЧЕНО")
            self.payment_status_btn.setStyleSheet("""
                QPushButton {
                    background-color: #333333;
                    color: #FF4B2B;
                    border: 1px solid #FF4B2B;
                    border-radius: 13px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #3D3D3D; }
            """)
            self.payment_status_btn.setChecked(False) # State OFF

    def on_payment_status_toggle(self, checked):
        # Логика переключения свитча
        if checked:
            # Пользователь нажал, чтобы стало "ОПЛАЧЕНО"
            # Значит нужно погасить долг
            if self.order.debt > 0:
                amount_to_pay = self.order.debt
                try:
                    self.order.add_payment(amount_to_pay, "платеж", "Полная оплата (авто)")
                    self.dispatch_global_update()
                    # Инфо не показываем, так как действие очевидно
                except Exception as e:
                    QMessageBox.warning(self.parent_app, "Ошибка", f"Не удалось добавить платеж: {e}")
                    self.update_payment_status() # Revert visual state
            else:
                self.update_payment_status() # Уже оплачено, ничего не делаем
        else:
            # Пользователь нажал, чтобы стало "НЕ ОПЛАЧЕНО"
            # Значит нужно отменить оплату?
            # Предлагаем удалить последний платеж
            if not self.order.payments:
                self.update_payment_status()
                return

            last_payment = self.order.payments[-1]
            
            msg_box = QMessageBox(self.parent_app)
            msg_box.setWindowTitle("Отмена оплаты")
            msg_box.setText(f"Выключив этот статус, вы удалите последний платеж ({last_payment.amount} руб.).")
            msg_box.setInformativeText("Продолжить?")
            msg_box.setIcon(QMessageBox.Icon.Question)
            
            btn_yes = msg_box.addButton("Да, удалить", QMessageBox.ButtonRole.YesRole)
            btn_no = msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_yes:
                try:
                    self.order.delete_payment(last_payment.id)
                    self.dispatch_global_update()
                    if hasattr(self.parent_app, 'update_client_stats'):
                        self.parent_app.update_client_stats()
                except Exception as e:
                    QMessageBox.warning(self.parent_app, "Ошибка", f"Не удалось удалить платеж: {e}")
            
            # В любом случае обновляем UI, чтобы кнопка вернулась в правильное состояние (соответствующее долгу)
            self.update_payment_status()

    def add_payment_dialog(self):
        dialog = QDialog(self.parent_app)
        dialog.setWindowTitle("Добавить платеж")
        dialog.setFixedWidth(400)
        
        dialog.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #333333; color: #FFFFFF;
                border: 1px solid #444444; padding: 6px; border-radius: 3px; font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        # Тип платежа
        type_label = QLabel("Тип платежа:")
        type_combo = QComboBox()
        type_combo.addItems(["платеж", "аванс", "корректировка"])
        form_layout.addRow(type_label, type_combo)

        # Подтип корректировки (Скрыт по умолчанию)
        corr_reason_label = QLabel("Вид корректировки:")
        corr_reason_combo = QComboBox()
        corr_reason_combo.addItems([
            "Возврат средств (Refund)", 
            "Скидка / Списание (Write-off)", 
            "Техническая правка (+)",
            "Техническая правка (-)"
        ])
        corr_reason_label.setVisible(False)
        corr_reason_combo.setVisible(False)
        form_layout.addRow(corr_reason_label, corr_reason_combo)
        
        # Сумма
        amount_label = QLabel("Сумма:")
        amount_edit = QLineEdit()
        amount_validator = QDoubleValidator(-9999999, 9999999, 2)
        amount_edit.setValidator(amount_validator)
        form_layout.addRow(amount_label, amount_edit)
        
        # Логика переключения полей
        def on_type_changed(text):
            is_correction = (text == "корректировка")
            corr_reason_label.setVisible(is_correction)
            corr_reason_combo.setVisible(is_correction)
            
            if is_correction:
                # Сброс суммы при переключении
                amount_edit.setPlaceholderText("Введите сумму")
            else:
                amount_edit.setPlaceholderText("0.00")

        type_combo.currentTextChanged.connect(on_type_changed)

        # Дата платежа
        date_label = QLabel("Дата:")
        date_edit = QDateEdit()
        date_edit.setDate(datetime.now().date())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        form_layout.addRow(date_label, date_edit)
        
        # Примечание
        note_label = QLabel("Примечание:")
        note_edit = QTextEdit()
        note_edit.setMaximumHeight(60)
        form_layout.addRow(note_label, note_edit)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                amount_text = amount_edit.text().replace(',', '.')
                if not amount_text:
                    QMessageBox.warning(self.parent_app, "Ошибка", "Введите сумму платежа")
                    return
                    
                raw_amount = float(amount_text)
                note = note_edit.toPlainText()
                date = date_edit.date().toString("dd.MM.yyyy")
                payment_type = type_combo.currentText()
                
                final_amount = raw_amount
                
                # Обработка логики корректировки
                if payment_type == "корректировка":
                    reason = corr_reason_combo.currentText()
                    if not note: note = reason # Автозаполнение примечания
                    
                    if "Возврат" in reason:
                        # Возврат должен быть отрицательным
                        final_amount = -abs(raw_amount)
                    elif "Скидка" in reason:
                        # Скидка не меняет цену, но уменьшает долг?
                        # Чтобы уменьшить долг (Price - Paid), нужно увеличить Paid.
                        # Значит Скидка = Платёж (+).
                        final_amount = abs(raw_amount)
                    elif "Техническая правка (-)" in reason:
                         final_amount = -abs(raw_amount)
                    elif "Техническая правка (+)" in reason:
                         final_amount = abs(raw_amount)

                self.order.add_payment(final_amount, payment_type, note, date + " 00:00")
                
                # SQLite save: мы должны найти ID клиента для этого заказа
                # В текущей архитектуре Order не знает о Client, но PaymentDialog получает parent_app
                # Мы можем найти клиента перебором (неэффективно, но работает)
                client_id = None
                for c in self.parent_app.clients:
                    if self.order in c.orders:
                        client_id = c.id
                        break
                
                if client_id:
                    # Добавляем последний добавленный платеж в БД
                    new_payment = self.order.payments[-1]
                    self.parent_app.sqlite.add_payment(client_id, self.order.id, new_payment)
                    # Также обновляем заказ (например, аванс мог измениться)
                    self.parent_app.sqlite.add_order(client_id, self.order)

                logger.info(f"Добавлен платеж: {final_amount} ({payment_type}) для заказа {self.order.service_type}")
                
                # Reactive Update
                self.dispatch_global_update()
                
                # Info message logic
                msg_title = "Платеж добавлен"
                if final_amount < 0: msg_title = "Возврат оформлен"
                
                QMessageBox.information(
                    self.parent_app,
                    msg_title,
                    f"Операция успешна.\nСумма: {final_amount:.2f} руб.\n"
                    f"Долг: {self.order.debt:.2f} руб."
                )
                
            except ValueError as e:
                QMessageBox.warning(self.parent_app, "Ошибка", str(e))

    def show_payments_history(self):
        from .dialogs import PaymentsDialog
        dialog = PaymentsDialog(self.order, self.parent_app)
        dialog.exec()
        self.update_financial_display()
        
        # Обновляем статистику клиента (в случае удаления платежей)
        if hasattr(self.parent_app, 'update_client_stats'):
            self.parent_app.update_client_stats()

    def add_file(self):
        msg_box = QMessageBox(self.parent_app)
        msg_box.setWindowTitle("Добавление элементов")
        msg_box.setText("Что вы хотите добавить?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_files = msg_box.addButton("Файлы", QMessageBox.ButtonRole.ActionRole)
        btn_folder = msg_box.addButton("Папку", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == btn_cancel:
            return

        if clicked == btn_files:
            paths, _ = QFileDialog.getOpenFileNames(
                self.parent_app,
                "Выберите файлы для заказа",
                "",
                "Все файлы (*.*)"
            )
            if paths:
                for p in paths:
                    logger.info(f"Добавление файла в заказ: {os.path.basename(p)}")
                    self.add_file_with_storage_option(p)
                self.parent_app.render_client_profile()
                self.parent_app.save_db()
        
        elif clicked == btn_folder:
            folder = QFileDialog.getExistingDirectory(
                self.parent_app,
                "Выберите папку для добавления"
            )
            if folder:
                logger.info(f"Добавление папки в заказ: {os.path.basename(folder)}")
                self.add_file_with_storage_option(folder)
                self.parent_app.render_client_profile()
                self.parent_app.save_db()

    def show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3D3D3D;
            }
        """)

        # 1. Изменить название услуги
        rename_action = QAction("✏ Изменить название", self)
        rename_action.triggered.connect(self.rename_service)
        menu.addAction(rename_action)

        # 1.5. Изменить валюту
        change_currency_action = QAction("💰 Изменить валюту", self)
        change_currency_action.triggered.connect(self.change_currency)
        menu.addAction(change_currency_action)

        # 2. Копировать ID заказа
        copy_id_action = QAction("🆔 Копировать ID заказа", self)
        copy_id_action.triggered.connect(self.copy_order_id)
        menu.addAction(copy_id_action)

        menu.addSeparator()

        # 3. Экспорт файлов (существующая функция)
        export_action = QAction("📦 Экспорт файлов (ZIP)", self)
        export_action.triggered.connect(self.export_files_to_zip)
        menu.addAction(export_action)

        # 4. Открыть папку с файлами
        open_folder_action = QAction("📂 Открыть папку файлов", self)
        open_folder_action.triggered.connect(self.open_order_folder)
        menu.addAction(open_folder_action)

        menu.addSeparator()

        # 5. Дублировать заказ
        duplicate_action = QAction("📋 Дублировать заказ", self)
        duplicate_action.triggered.connect(self.duplicate_order)
        menu.addAction(duplicate_action)

        menu.addSeparator()

        # 6. Удалить заказ (существующая функция)
        delete_action = QAction("🗑 Удалить заказ", self)
        delete_action.triggered.connect(self.delete_order)
        menu.addAction(delete_action)

        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))

    def duplicate_order(self):
        """Создает копию текущего заказа для того же клиента"""
        import uuid
        new_order = Order(
            id=str(uuid.uuid4()),
            service_type=f"{self.order.service_type} (копия)",
            price=self.order.price,
            currency=self.order.currency,
            advance=0.0,
            created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
            deadline=self.order.deadline,
            status="В работе",
            files=[],
            payments=[]
        )
        # Находим клиента
        for client in self.parent_app.clients:
            if self.order in client.orders:
                client.orders.append(new_order)
                break
        
        self.parent_app.render_client_profile()
        self.parent_app.save_db()

    def change_currency(self):
        currencies = self.parent_app.app_settings.get("currencies", ["RUB", "USD", "EUR", "UAH"])
        current_currency = getattr(self.order, 'currency', 'RUB')
        
        # Убедимся, что текущая валюта есть в списке
        if current_currency not in currencies:
            currencies.insert(0, current_currency)
            
        new_currency, ok = QInputDialog.getItem(
            self.parent_app, 
            "Смена валюты", 
            "Выберите новую валюту для заказа:", 
            currencies, 
            currencies.index(current_currency), 
            False
        )
        
        if ok and new_currency != current_currency:
            self.order.currency = new_currency
            self.parent_app.save_db()
            self.update_financial_display() # Обновляем отображение
            # Также нужно обновить статистику клиента, если она отображается
            if hasattr(self.parent_app, 'update_client_stats'):
                self.parent_app.update_client_stats()

    def rename_service(self):
        new_name, ok = QInputDialog.getText(
            self.parent_app,
            "Переименование заказа",
            "Введите новое название услуги:",
            QLineEdit.EchoMode.Normal,
            self.order.service_type
        )
        if ok and new_name.strip():
            self.order.service_type = new_name.strip()
            self.parent_app.render_client_profile() # Перерисовываем для обновления заголовка
            self.parent_app.save_db()

    def copy_order_id(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.order.id)
        # Опционально: показать тултип или маленький месседж, но в Qt это сложнее без статусбара
        
    def open_order_folder(self):
        # Логика определения папки такая же как при добавлении файлов в режиме 'copy'
        if not self.parent_app.app_settings:
             return
             
        db_folder = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
        files_folder = os.path.join(db_folder, "attached_files", self.order.id)
        
        if os.path.exists(files_folder):
            if platform.system() == "Windows":
                os.startfile(files_folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", files_folder])
            else:
                subprocess.Popen(["xdg-open", files_folder])
        else:
            QMessageBox.information(self.parent_app, "Инфо", "У этого заказа нет отдельной папки с файлами (или она еще не создана).")

    def delete_order(self):
        if not self.order:
            return
        
        msg_box = QMessageBox(self.parent_app)
        msg_box.setWindowTitle("Удаление заказа")
        msg_box.setText(f"Вы уверены, что хотите удалить заказ '{self.order.service_type}'?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            logger.info(f"Удаление заказа: {self.order.service_type} (ID: {self.order.id})")
            
            # Предлагаем удалить файлы
            delete_files = False
            files_exist = any(os.path.exists(f.path) for f in self.order.files)
            
            # Также проверяем папку в базе
            db_folder = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
            order_files_folder = os.path.join(db_folder, "attached_files", self.order.id)
            folder_exists = os.path.exists(order_files_folder)
            
            if files_exist or folder_exists:
                ask_files = QMessageBox(self.parent_app)
                ask_files.setWindowTitle("Удаление файлов")
                ask_files.setText("Удалить связанные с заказом файлы с диска?")
                ask_files.setInformativeText("Это действие необратимо.")
                ask_files.setIcon(QMessageBox.Icon.Warning)
                btn_yes_files = ask_files.addButton("Да, удалить всё", QMessageBox.ButtonRole.YesRole)
                btn_no_files = ask_files.addButton("Нет, оставить файлы", QMessageBox.ButtonRole.NoRole)
                ask_files.exec()
                
                if ask_files.clickedButton() == btn_yes_files:
                    delete_files = True

            # Удаляем файлы если нужно
            if delete_files:
                # 1. Удаляем файлы из списка
                for f in self.order.files:
                    if os.path.exists(f.path):
                        try:
                            if os.path.isdir(f.path):
                                shutil.rmtree(f.path)
                            else:
                                os.remove(f.path)
                        except Exception as e:
                            logger.error(f"Не удалось удалить {f.path}: {e}")
                
                # 2. Удаляем папку заказа в базе (если есть)
                if folder_exists:
                    try:
                        shutil.rmtree(order_files_folder)
                    except Exception as e:
                        logger.error(f"Не удалось удалить папку заказа {order_files_folder}: {e}")

            # Находим клиента, которому принадлежит заказ
            for client in self.parent_app.clients:
                if self.order in client.orders:
                    # SQLite delete
                    self.parent_app.sqlite.delete_order(self.order.id)
                    
                    client.orders.remove(self.order)
                    break
            
            # Перерисовываем профиль
            self.parent_app.render_client_profile()
            self.parent_app.save_db()
