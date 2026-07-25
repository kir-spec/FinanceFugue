import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QCheckBox, QDateEdit, QSizePolicy,
)
from PySide6.QtCore import Qt

from ..models import Order
from ..services.currency import currency_symbol
from ..ui.app_bridge import AppBridge
from ..logger import get_logger
from ..theme import (
    BUTTON_COMPACT_STYLE,
    DATE_EDIT_STYLE,
    DEADLINE_LABEL_STYLE,
    DRAG_HINT_STYLE,
    FIELD_LABEL_STYLE,
    FILES_SECTION_LABEL_STYLE,
    ORDER_DELETE_BTN_STYLE,
    ORDER_FRAME_STYLE,
    ORDER_STATUS_CHECKBOX_STYLE,
    ORDER_TITLE_STYLE,
    ORDER_TOGGLE_BTN_STYLE,
    PAYMENT_ADD_BTN_STYLE,
    PAYMENT_HISTORY_BTN_STYLE,
    PAYMENTS_FRAME_STYLE,
    SEPARATOR_LINE_STYLE,
    SEPARATOR_STYLE,
    START_DATE_LABEL_STYLE,
    VERTICAL_SEPARATOR_STYLE,
    money_input_style,
)
from .file_item_widget import FileItemWidget
from .order_files_mixin import OrderFilesMixin
from .order_financial_mixin import OrderFinancialMixin

logger = get_logger('Widgets')

class OrderWidget(OrderFinancialMixin, OrderFilesMixin, QFrame):
    def _currency_sym(self) -> str:
        return currency_symbol(getattr(self.order, "currency", "RUB"))

    def __init__(self, order: Order, bridge: AppBridge):
        super().__init__()
        self.order = order
        self._bridge = bridge
        self.setAcceptDrops(True)  # Разрешаем drag and drop
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(ORDER_FRAME_STYLE)
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
        self.toggle_btn.setStyleSheet(ORDER_TOGGLE_BTN_STYLE)

        title = QLabel(f"{self.order.service_type}")
        title.setStyleSheet(ORDER_TITLE_STYLE)
        
        # Кнопка удаления заказа - СЕРАЯ
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setFixedWidth(70)
        self.delete_btn.clicked.connect(self.delete_order)
        self.delete_btn.setStyleSheet(ORDER_DELETE_BTN_STYLE)

        # Чекбокс "Выполнен"
        self.status_cb = QCheckBox("Выполнен")
        self.status_cb.setChecked(self.order.status == "Завершен")
        self.status_cb.stateChanged.connect(self.update_order_status)
        self.status_cb.setStyleSheet(ORDER_STATUS_CHECKBOX_STYLE)

        header.addWidget(self.toggle_btn)
        header.addWidget(title)
        header.addSpacing(10)
        header.addWidget(self.status_cb)
        header.addWidget(self.delete_btn)
        header.addStretch()
        self.main_layout.addLayout(header)

        # Содержимое
        self.content = QWidget()
        self.c_layout = QVBoxLayout(self.content)
        self.c_layout.setSpacing(4)
        
        # Горизонтальная линия ПЕРЕД датами
        sep_before_dates = QFrame()
        sep_before_dates.setFrameShape(QFrame.Shape.HLine)
        sep_before_dates.setStyleSheet(SEPARATOR_LINE_STYLE)
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
        start_date_label.setStyleSheet(START_DATE_LABEL_STYLE)
        
        self.order_date_edit = QDateEdit()
        self.order_date_edit.setCalendarPopup(True)
        self.order_date_edit.setDisplayFormat("dd.MM.yyyy")
        try:
            if self.order.created_at:
                d_str = self.order.created_at.split()[0]
                self.order_date_edit.setDate(datetime.strptime(d_str, "%d.%m.%Y").date())
            else:
                self.order_date_edit.setDate(datetime.now().date())
        except ValueError:
            self.order_date_edit.setDate(datetime.now().date())
            
        self.order_date_edit.setFixedWidth(110)
        self.order_date_edit.dateChanged.connect(self.sync_order_date)
        self.order_date_edit.setStyleSheet(DATE_EDIT_STYLE)
        
        date_box_layout.addWidget(start_date_label)
        date_box_layout.addWidget(self.order_date_edit)
        info_layout.addWidget(date_box)
        
        # Срок выполнения
        deadline_box = QWidget()
        deadline_layout = QHBoxLayout(deadline_box)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_layout.setSpacing(5)
        
        deadline_label = QLabel("⏰ Срок:")
        deadline_label.setStyleSheet(DEADLINE_LABEL_STYLE)
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("dd.MM.yyyy")
        self.deadline_edit.setFixedWidth(110)
        
        if self.order.deadline:
            try:
                self.deadline_edit.setDate(datetime.strptime(self.order.deadline, "%d.%m.%Y").date())
            except ValueError:
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
        sep_after_dates.setStyleSheet(SEPARATOR_LINE_STYLE)
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
            lbl.setStyleSheet(FIELD_LABEL_STYLE)
            
            edit = QLineEdit(self.format_number(value))
            # Ширина должна быть одинаковой и соответствовать ширине нижних блоков
            # 120 + 120 + 10 (spacing) = ~250 на блок, здесь 3 блока
            # Сделаем чуть шире
            edit.setFixedWidth(120)
            edit.editingFinished.connect(callback)
            edit.setStyleSheet(money_input_style(color))
            layout.addWidget(lbl)
            layout.addWidget(edit)
            return box, edit

        # Для выравнивания ширины верхнего и нижнего блока (инструменты экспорта)
        # Нижний блок состоит из двух колонок: Платежи и Файлы
        # Платежи имеют фиксированную ширину кнопок (120 + 120 + spacing) ~ 260-280px
        # Файлы тянутся
        # Здесь у нас 3 поля ввода. Сделаем их ширину такой, чтобы она была сопоставима с нижним блоком.
        
        cost_box, self.cost_edit = create_money_box("СТОИМОСТЬ", self.order.price, "#00D1FF", self.sync_price)
        advance_box, self.advance_edit = create_money_box("АВАНС", self.order.advance, "#FFD700", self.sync_advance)
        debt_box, self.debt_edit = create_money_box("ДОЛГ", self.order.debt, "#FF4B2B", self.sync_debt)

        money_row.addWidget(cost_box)
        money_row.addWidget(advance_box)
        money_row.addWidget(debt_box)
        money_row.addStretch()
        
        financial_layout.addLayout(money_row)
        
        # Разделитель между финансовыми полями и блоком платежей/файлов
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setStyleSheet(SEPARATOR_STYLE)
        financial_layout.addWidget(sep_line)

        # Нижний блок: Платежи (слева) и Файлы (справа)
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        bottom_layout.setSpacing(10)

        # --- Блок Платежей: С рамкой ---
        payments_frame = QFrame()
        payments_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        payments_frame.setStyleSheet(PAYMENTS_FRAME_STYLE)
        payments_box_layout = QVBoxLayout(payments_frame)
        payments_box_layout.setContentsMargins(10, 4, 10, 8)
        payments_box_layout.setSpacing(4)
        
        payments_label = QLabel("ПЛАТЕЖИ:")
        payments_label.setStyleSheet(FIELD_LABEL_STYLE)
        
        btns_row = QHBoxLayout()
        btns_row.setSpacing(10)
        
        add_payment_btn = QPushButton("✚ добавить")
        add_payment_btn.clicked.connect(self.add_payment_dialog)
        add_payment_btn.setStyleSheet(PAYMENT_ADD_BTN_STYLE)
        
        history_payment_btn = QPushButton("📋 история")
        history_payment_btn.clicked.connect(self.show_payments_history)
        history_payment_btn.setStyleSheet(PAYMENT_HISTORY_BTN_STYLE)
        
        btns_row.addWidget(add_payment_btn)
        btns_row.addWidget(history_payment_btn)
        # btns_row.addStretch() # Убрали stretch, чтобы рамка сжималась
        
        # Статус оплаты
        self.payment_status = QLabel()
        
        payments_box_layout.addWidget(payments_label)
        payments_box_layout.addLayout(btns_row)
        
        # Добавляем блок платежей в нижний лэйаут
        bottom_layout.addWidget(payments_frame)
        
        # Разделитель между блоком платежей и файлов
        vertical_sep = QFrame()
        vertical_sep.setFrameShape(QFrame.Shape.VLine)
        vertical_sep.setStyleSheet(VERTICAL_SEPARATOR_STYLE)
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
        files_label.setStyleSheet(FILES_SECTION_LABEL_STYLE)
        
        files_header.addWidget(files_label)
        files_header.addStretch()
        
        self.files_layout.addLayout(files_header)
        
        if not self.order.files:
            drag_label = QLabel("Перетащите файлы сюда")
            drag_label.setStyleSheet(DRAG_HINT_STYLE)
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
            
            for f in sorted_files:
                # Проставляем флаг is_folder если его нет (для старых записей)
                if not hasattr(f, 'is_folder'):
                    f.is_folder = os.path.isdir(f.path)
                    
                fw = FileItemWidget(f, self._bridge, self.order)
                fw.statusChanged.connect(self._bridge.request_save)
                self.files_layout.addWidget(fw)

        # Кнопки управления файлами
        btns_container = QWidget()
        btns_container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        btns = QHBoxLayout(btns_container)
        btns.setContentsMargins(0,0,0,0)
        btns.setSpacing(5)

        b_f = QPushButton("+ Добавить")
        b_f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_f.clicked.connect(self.add_file)
        b_f.setStyleSheet(BUTTON_COMPACT_STYLE)

        b_z = QPushButton("📦 Экспорт")
        b_z.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_z.clicked.connect(self.export_files_to_zip)
        b_z.setStyleSheet(BUTTON_COMPACT_STYLE)
        
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

    def toggle_contents(self):
        visible = self.content.isVisible()
        self.content.setVisible(not visible)
        # Меняем стрелочку в зависимости от состояния
        self.toggle_btn.setText("▲" if visible else "▼")
