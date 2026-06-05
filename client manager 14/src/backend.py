import os
import sys
import json
import uuid
import zipfile
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot, pyqtProperty as Property, QAbstractListModel, Qt, QModelIndex, QUrl
from PyQt6.QtGui import QClipboard, QGuiApplication

from .logger import get_logger
from .models import Client, Order, ProjectFile, Payment
from .storage import CRMStorage

logger = get_logger("Backend")


class ProjectFileWrapper(QObject):
    """Обёртка для ProjectFile для использования в QML"""
    def __init__(self, file_obj: ProjectFile, parent=None):
        super().__init__(parent)
        self._file = file_obj

    @Property(str, constant=True)
    def name(self):
        return self._file.name

    @Property(str, constant=True)
    def path(self):
        return self._file.path

    @Property(bool, constant=True)
    def isFinished(self):
        return self._file.is_finished

    @Property(bool, constant=True)
    def isFolder(self):
        return self._file.is_folder

    def get_file(self):
        return self._file


class PaymentWrapper(QObject):
    """Обёртка для Payment для использования в QML"""
    def __init__(self, payment: Payment, parent=None):
        super().__init__(parent)
        self._payment = payment

    @Property(str, constant=True)
    def id(self):
        return self._payment.id

    @Property(str, constant=True)
    def type(self):
        return self._payment.type

    @Property(float, constant=True)
    def amount(self):
        return self._payment.amount

    @Property(str, constant=True)
    def date(self):
        return self._payment.date

    @Property(str, constant=True)
    def note(self):
        return self._payment.note

    def get_payment(self):
        return self._payment


class OrderWrapper(QObject):
    """Обёртка для Order для использования в QML"""
    orderChanged = Signal()

    def __init__(self, order: Order, parent=None):
        super().__init__(parent)
        self._order = order
        self._files = []
        self._payments = []
        self._update_files()
        self._update_payments()

    @Property(str, notify=orderChanged)
    def id(self):
        return self._order.id

    @Property(str, notify=orderChanged)
    def serviceType(self):
        return self._order.service_type

    @Property(float, notify=orderChanged)
    def price(self):
        return self._order.price

    @Property(str, notify=orderChanged)
    def currency(self):
        return self._order.currency

    @Property(float, notify=orderChanged)
    def advance(self):
        return self._order.advance

    @Property(str, notify=orderChanged)
    def createdAt(self):
        return self._order.created_at

    @Property(str, notify=orderChanged)
    def deadline(self):
        return self._order.deadline

    @Property(str, notify=orderChanged)
    def status(self):
        return self._order.status

    @Property(float, notify=orderChanged)
    def totalReceived(self):
        return self._order.total_received

    @Property(float, notify=orderChanged)
    def debt(self):
        return self._order.debt

    @Property(int, notify=orderChanged)
    def daysUntilDeadline(self):
        return self._order.days_until_deadline or 999

    def get_order(self):
        return self._order

    def _update_files(self):
        self._files = [ProjectFileWrapper(f, self) for f in self._order.files]
        self.orderChanged.emit()

    def _update_payments(self):
        self._payments = [PaymentWrapper(p, self) for p in self._order.payments]
        self.orderChanged.emit()

    @Property('QVariantList', notify=orderChanged)
    def files(self):
        return self._files

    @Property('QVariantList', notify=orderChanged)
    def payments(self):
        return self._payments


class ClientWrapper(QObject):
    """Обёртка для Client для использования в QML"""
    clientChanged = Signal()

    def __init__(self, client: Client, parent=None):
        super().__init__(parent)
        self._client = client
        self._orders = []
        self._update_orders()

    @Property(str, notify=clientChanged)
    def id(self):
        return self._client.id

    @Property(str, notify=clientChanged)
    def name(self):
        return self._client.name

    @Property(str, notify=clientChanged)
    def email(self):
        return self._client.email

    @Property(str, notify=clientChanged)
    def socialLink(self):
        return self._client.social_link

    @Property(str, notify=clientChanged)
    def notes(self):
        return self._client.notes

    def set_name(self, name):
        self._client.name = name
        self.clientChanged.emit()

    def set_email(self, email):
        self._client.email = email
        self.clientChanged.emit()

    def set_social_link(self, link):
        self._client.social_link = link
        self.clientChanged.emit()

    def set_notes(self, notes):
        self._client.notes = notes
        self.clientChanged.emit()

    @Property('QVariantList', notify=clientChanged)
    def orders(self):
        return self._orders

    @Property(int, notify=clientChanged)
    def totalOrders(self):
        return len(self._client.orders)

    @Property(int, notify=clientChanged)
    def completedOrders(self):
        return sum(1 for o in self._client.orders if o.status == "Завершен")

    @Property(float, notify=clientChanged)
    def totalReceived(self):
        return sum(o.total_received for o in self._client.orders)

    @Property(float, notify=clientChanged)
    def totalAdvance(self):
        return sum(o.advance for o in self._client.orders)

    @Property(float, notify=clientChanged)
    def totalDebt(self):
        return sum(o.debt for o in self._client.orders if o.status != "Завершен")

    def _update_orders(self):
        self._orders = [OrderWrapper(o, self) for o in self._client.orders]
        self.clientChanged.emit()

    def refresh_orders(self):
        self._update_orders()

    def get_client(self):
        return self._client


class ClientsModel(QAbstractListModel):
    """Модель клиентов для ListView в QML"""
    clientsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clients = []

    def roleNames(self):
        return {
            Qt.ItemDataRole.DisplayRole: b"name",
            Qt.ItemDataRole.UserRole: b"id",
            Qt.ItemDataRole.UserRole + 1: b"wrapper"
        }

    def data(self, index, role):
        if not index.isValid():
            return None

        if index.row() >= len(self._clients):
            return None

        client_wrapper = self._clients[index.row()]
        client = client_wrapper.get_client()

        if role == Qt.ItemDataRole.DisplayRole:
            return client.name
        elif role == Qt.ItemDataRole.UserRole:
            return client.id
        elif role == Qt.ItemDataRole.UserRole + 1:
            return client_wrapper

        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._clients)

    def set_clients(self, clients: List[Client]):
        self.beginResetModel()
        self._clients = [ClientWrapper(c, self) for c in clients]
        self.endResetModel()
        self.clientsChanged.emit()

    def get_client_wrapper_by_id(self, client_id: str) -> Optional[ClientWrapper]:
        for wrapper in self._clients:
            if wrapper.id == client_id:
                return wrapper
        return None

    def get_client_by_id(self, client_id: str) -> Optional[Client]:
        wrapper = self.get_client_wrapper_by_id(client_id)
        if wrapper:
            return wrapper.get_client()
        return None


class CRMBackend(QObject):
    """Основной бэкенд для взаимодействия с QML"""
    clientsChanged = Signal()
    currentClientChanged = Signal()
    statsChanged = Signal()
    settingsChanged = Signal()
    errorMessage = Signal(str)
    infoMessage = Signal(str)
    successMessage = Signal(str)
    questionMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_settings = self.load_settings()
        
        db_filename = "pro_database.json"
        if 'database_path' in self.app_settings:
            db_path = self.app_settings['database_path']
            if os.path.exists(db_path):
                db_filename = os.path.join(db_path, "pro_database.json")
        
        self.storage = CRMStorage(db_filename)
        self._clients = self.storage.load()
        
        self.clients_model = ClientsModel(self)
        self.clients_model.set_clients(self._clients)
        
        self._current_client = None
        self._current_client_wrapper = None

        # Статистика
        self._stats_in_work = 0
        self._stats_done = 0
        self._stats_total_advance = 0.0
        self._stats_total_debt = 0.0
        self._stats_total_cash = 0.0
        
        self.update_stats()

    def load_settings(self):
        settings_path = Path("crm_settings.json")
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_settings(self):
        settings_path = Path("crm_settings.json")
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(self.app_settings, f, ensure_ascii=False, indent=4)
            self.settingsChanged.emit()
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
            self.errorMessage.emit(f"Ошибка сохранения настроек: {e}")

    def is_first_run(self):
        return 'first_run_completed' not in self.app_settings

    def mark_first_run_completed(self, settings):
        self.app_settings.update(settings)
        self.app_settings['first_run_completed'] = True
        self.save_settings()
        
        if 'database_path' in settings:
            new_db_path = os.path.join(settings['database_path'], "pro_database.json")
            self.storage = CRMStorage(new_db_path)
            self._clients = self.storage.load()
            self.clients_model.set_clients(self._clients)
            
        if settings.get('file_storage_mode') == 'copy':
            db_folder = settings.get('database_path', os.path.dirname(self.storage.path))
            files_folder = os.path.join(db_folder, "attached_files")
            os.makedirs(files_folder, exist_ok=True)

    @Property(str, constant=True)
    def homePath(self):
        return QUrl.fromLocalFile(str(Path.home())).toString()

    @Property(ClientsModel, notify=clientsChanged)
    def clients(self):
        return self.clients_model

    @Property(QObject, notify=currentClientChanged)
    def currentClient(self):
        return self._current_client_wrapper

    @Slot(str)
    def set_current_client(self, client_id: str):
        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
        if wrapper:
            self._current_client = wrapper.get_client()
            self._current_client_wrapper = wrapper
            self.currentClientChanged.emit()
            return True
        return False

    @Property(int, notify=statsChanged)
    def statsInWork(self):
        return self._stats_in_work

    @Property(int, notify=statsChanged)
    def statsDone(self):
        return self._stats_done

    @Property(str, notify=statsChanged)
    def statsTotalAdvance(self):
        return f"{self._stats_total_advance:,.0f} ₽"

    @Property(str, notify=statsChanged)
    def statsTotalDebt(self):
        return f"{self._stats_total_debt:,.0f} ₽"

    @Property(str, notify=statsChanged)
    def statsTotalCash(self):
        return f"{self._stats_total_cash:,.0f} ₽"

    def update_stats(self):
        self._stats_in_work = 0
        self._stats_done = 0
        self._stats_total_advance = 0.0
        self._stats_total_debt = 0.0
        self._stats_total_cash = 0.0
        
        for client in self._clients:
            for order in client.orders:
                self._stats_total_advance += order.advance
                self._stats_total_cash += order.total_received
                if order.status == "Завершен":
                    self._stats_done += 1
                else:
                    self._stats_in_work += 1
                    self._stats_total_debt += order.debt
        
        self.statsChanged.emit()

    @Slot()
    def save_database(self):
        try:
            self.storage.save(self._clients)
            self.update_stats()
            logger.info("База данных сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения базы данных: {e}")
            self.errorMessage.emit(f"Не удалось сохранить базу данных: {e}")

    @Slot()
    def refresh_clients(self):
        self.clients_model.set_clients(self._clients)

    @Slot(str, result=QObject)
    def get_client_wrapper(self, client_id: str) -> QObject:
        return self.clients_model.get_client_wrapper_by_id(client_id)

    @Slot(str, str, result=QObject)
    def get_order_wrapper(self, client_id: str, order_id: str) -> QObject:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            for order in client.orders:
                if order.id == order_id:
                    return OrderWrapper(order, self)
        return None

    # Клиенты
    @Slot(str, result=bool)
    def add_client(self, name: str) -> bool:
        if not name.strip():
            self.errorMessage.emit("Введите имя клиента")
            return False
        
        if any(c.name.lower() == name.strip().lower() for c in self._clients):
            self.errorMessage.emit("Клиент с таким именем уже существует")
            return False
        
        new_client = Client(
            id=str(uuid.uuid4()),
            name=name.strip()
        )
        self._clients.append(new_client)
        self.clients_model.set_clients(self._clients)
        self.save_database()
        logger.info(f"Добавлен новый клиент: {new_client.name}")
        self.successMessage.emit(f"Клиент '{name}' успешно создан")
        return True

    @Slot(str, str, str, str, str, result=bool)
    def update_client(self, client_id: str, name: str, email: str, social_link: str, notes: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            client.name = name
            client.email = email
            client.social_link = social_link
            client.notes = notes
            
            wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
            if wrapper:
                wrapper.set_name(name)
                wrapper.set_email(email)
                wrapper.set_social_link(social_link)
                wrapper.set_notes(notes)
            
            self.save_database()
            self.refresh_clients()
            return True
        return False

    @Slot(str, result=bool)
    def delete_client(self, client_id: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            self._clients.remove(client)
            if self._current_client == client:
                self._current_client = None
                self._current_client_wrapper = None
                self.currentClientChanged.emit()
            
            self.clients_model.set_clients(self._clients)
            self.save_database()
            logger.info(f"Удален клиент: {client.name}")
            self.successMessage.emit(f"Клиент '{client.name}' успешно удален")
            return True
        return False

    # Заказы
    @Slot(str, str, float, str, float, str, result=bool)
    def add_order(self, client_id: str, service_type: str, price: float, currency: str, advance: float, deadline: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if not client:
            self.errorMessage.emit("Клиент не найден")
            return False
        
        new_order = Order(
            id=str(uuid.uuid4()),
            service_type=service_type,
            price=price,
            currency=currency,
            advance=advance,
            created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
            deadline=deadline,
            status="В работе",
            payments=[]
        )
        
        if advance > 0:
            new_order.add_payment(advance, "аванс", "Первоначальный аванс")
        
        client.orders.append(new_order)
        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
        if wrapper:
            wrapper.refresh_orders()
        
        self.save_database()
        logger.info(f"Добавлен заказ '{service_type}' для клиента {client.name}")
        self.successMessage.emit(f"Заказ '{service_type}' успешно создан")
        return True

    @Slot(str, str, result=bool)
    def delete_order(self, client_id: str, order_id: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                client.orders.remove(order)
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                logger.info(f"Удален заказ '{order.service_type}'")
                self.successMessage.emit(f"Заказ '{order.service_type}' успешно удален")
                return True
        return False

    @Slot(str, str, str, result=bool)
    def update_order_status(self, client_id: str, order_id: str, status: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                order.status = status
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                return True
        return False

    @Slot(str, str, float, result=bool)
    def update_order_price(self, client_id: str, order_id: str, price: float) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                order.price = price
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                return True
        return False

    @Slot(str, str, float, result=bool)
    def update_order_advance(self, client_id: str, order_id: str, advance: float) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                order.advance = advance
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                return True
        return False

    @Slot(str, str, str, result=bool)
    def update_order_deadline(self, client_id: str, order_id: str, deadline: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                order.deadline = deadline
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                return True
        return False

    # Платежи
    @Slot(str, str, float, str, str, str, result=bool)
    def add_payment(self, client_id: str, order_id: str, amount: float, payment_type: str, note: str, date: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                try:
                    order.add_payment(amount, payment_type, note, date + " 00:00")
                    wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                    if wrapper:
                        wrapper.refresh_orders()
                    
                    self.save_database()
                    return True
                except ValueError as e:
                    self.errorMessage.emit(str(e))
                    return False
        return False

    @Slot(str, str, str, result=bool)
    def delete_payment(self, client_id: str, order_id: str, payment_id: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                try:
                    order.delete_payment(payment_id)
                    wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                    if wrapper:
                        wrapper.refresh_orders()
                    
                    self.save_database()
                    return True
                except ValueError as e:
                    self.errorMessage.emit(str(e))
                    return False
        return False

    # Файлы
    @Slot(str, str, str, bool, result=bool)
    def add_file(self, client_id: str, order_id: str, file_path: str, is_folder: bool) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                # Проверяем режим хранения файлов
                storage_mode = self.app_settings.get('file_storage_mode', 'copy')
                
                if storage_mode == 'copy':
                    db_folder = self.app_settings.get('database_path', os.path.dirname(self.storage.path))
                    files_folder = os.path.join(db_folder, "attached_files", order.id)
                    os.makedirs(files_folder, exist_ok=True)
                    
                    base_name = os.path.basename(file_path)
                    new_path = os.path.join(files_folder, base_name)
                    
                    counter = 1
                    name, ext = os.path.splitext(base_name)
                    while os.path.exists(new_path):
                        new_path = os.path.join(files_folder, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    try:
                        if is_folder:
                            shutil.copytree(file_path, new_path)
                        else:
                            shutil.copy2(file_path, new_path)
                        final_path = new_path
                    except Exception as e:
                        self.errorMessage.emit(f"Не удалось скопировать файл: {e}")
                        final_path = file_path
                else:
                    final_path = file_path
                
                project_file = ProjectFile(
                    path=final_path,
                    name=os.path.basename(final_path),
                    is_finished=False,
                    is_folder=is_folder
                )
                order.files.append(project_file)
                
                wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                if wrapper:
                    wrapper.refresh_orders()
                
                self.save_database()
                return True
        return False

    @Slot(str, str, str, result=bool)
    def delete_file(self, client_id: str, order_id: str, file_path: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                file_obj = next((f for f in order.files if f.path == file_path), None)
                if file_obj:
                    order.files.remove(file_obj)
                    wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                    if wrapper:
                        wrapper.refresh_orders()
                    
                    self.save_database()
                    return True
        return False

    @Slot(str, str, str, str, result=bool)
    def rename_file(self, client_id: str, order_id: str, old_path: str, new_name: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                file_obj = next((f for f in order.files if f.path == old_path), None)
                if file_obj:
                    try:
                        old_dir = os.path.dirname(old_path)
                        new_path = os.path.join(old_dir, new_name.strip())
                        os.rename(old_path, new_path)
                        file_obj.path = new_path
                        file_obj.name = new_name.strip()
                        
                        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                        if wrapper:
                            wrapper.refresh_orders()
                        
                        self.save_database()
                        return True
                    except Exception as e:
                        self.errorMessage.emit(f"Не удалось переименовать файл: {e}")
                        return False
        return False

    # Экспорт и импорт
    @Slot(str, result=bool)
    def export_json(self, path: str) -> bool:
        try:
            temp_storage = CRMStorage(path)
            temp_storage.save(self._clients)
            self.successMessage.emit(f"База данных экспортирована в: {path}")
            return True
        except Exception as e:
            self.errorMessage.emit(f"Не удалось экспортировать базу данных: {e}")
            return False

    @Slot(str, result=bool)
    def import_json(self, path: str) -> bool:
        try:
            temp_storage = CRMStorage(path)
            imported_clients = temp_storage.load()
            if not imported_clients:
                self.errorMessage.emit("Выбранный файл не содержит данных")
                return False
            
            # Создаем бэкап
            backup_path = self.storage.path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            if self.storage.path.exists():
                shutil.copy2(self.storage.path, backup_path)
            
            self._clients = imported_clients
            self._current_client = None
            self._current_client_wrapper = None
            self.currentClientChanged.emit()
            self.clients_model.set_clients(self._clients)
            self.save_database()
            
            self.successMessage.emit(f"Импортировано клиентов: {len(imported_clients)}")
            return True
        except Exception as e:
            self.errorMessage.emit(f"Не удалось импортировать базу данных: {e}")
            return False

    # Сортировка
    @Slot(str)
    def sort_clients(self, mode: str):
        if mode == "Имя (А-Я)":
            self._clients.sort(key=lambda x: x.name.lower())
        elif mode == "Имя (Я-А)":
            self._clients.sort(key=lambda x: x.name.lower(), reverse=True)
        elif mode == "Новые заказы":
            def get_last_order_date(client):
                if not client.orders:
                    return datetime.min
                try:
                    dates = []
                    for o in client.orders:
                        d_str = o.created_at
                        if " " in d_str:
                            dt = datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                        else:
                            dt = datetime.strptime(d_str, "%d.%m.%Y")
                        dates.append(dt)
                    return max(dates)
                except:
                    return datetime.min
            self._clients.sort(key=get_last_order_date, reverse=True)
        elif mode == "Старые заказы":
            def get_last_order_date(client):
                if not client.orders:
                    return datetime.min
                try:
                    dates = []
                    for o in client.orders:
                        d_str = o.created_at
                        if " " in d_str:
                            dt = datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                        else:
                            dt = datetime.strptime(d_str, "%d.%m.%Y")
                        dates.append(dt)
                    return max(dates)
                except:
                    return datetime.min
            self._clients.sort(key=get_last_order_date)
        elif mode == "Срочные":
            def get_nearest_deadline(client):
                if not client.orders:
                    return datetime.max
                deadlines = []
                for o in client.orders:
                    if o.status != "Завершен" and o.deadline:
                        try:
                            dt = datetime.strptime(o.deadline, "%d.%m.%Y")
                            deadlines.append(dt)
                        except:
                            pass
                if not deadlines:
                    return datetime.max
                return min(deadlines)
            self._clients.sort(key=get_nearest_deadline)
        
        self.clients_model.set_clients(self._clients)

    # Утилиты
    @Slot(str)
    def open_file(self, path: str):
        try:
            if os.path.exists(path):
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess = __import__('subprocess')
                    subprocess.Popen(["open", path])
                else:
                    subprocess = __import__('subprocess')
                    subprocess.Popen(["xdg-open", path])
            else:
                self.errorMessage.emit(f"Файл не найден: {path}")
        except Exception as e:
            self.errorMessage.emit(f"Не удалось открыть файл: {e}")

    @Slot(str, str, str, result=bool)
    def export_order_files(self, client_id: str, order_id: str, export_path: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                ready_files = [f for f in order.files if os.path.exists(f.path)]
                if not ready_files:
                    self.errorMessage.emit("Нет файлов для экспорта")
                    return False
                
                try:
                    with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as z:
                        for f in ready_files:
                            z.write(f.path, f.name)
                    
                    self.successMessage.emit(f"Экспортировано файлов: {len(ready_files)}")
                    return True
                except Exception as e:
                    self.errorMessage.emit(f"Не удалось создать архив: {e}")
                    return False
            return False
        
    @Slot(str, result=str)
    def export_full_backup(self, path: str) -> str:
        """Полный бэкап (ZIP)"""
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(str(self.storage.path), "database.json")
                file_count = 0
                for client in self._clients:
                    for order in client.orders:
                        for file in order.files:
                            if os.path.exists(file.path):
                                arcname = os.path.join(
                                    "files",
                                    client.name,
                                    order.service_type,
                                    file.name
                                )
                                zip_file.write(file.path, arcname)
                                file_count += 1
                result = f"Полная резервная копия успешно создана.\n\nФайл: {path}\nКлиентов: {len(self._clients)}\nФайлов в архиве: {file_count}"
                self.successMessage.emit(result)
                return result
        except Exception as e:
            logger.error(f"Ошибка создания полного бэкапа: {e}")
            error = f"Ошибка: {e}"
            self.errorMessage.emit(error)
            return error
    
    @Slot(str, str, result=str)
    def export_client_files(self, client_id: str, folder: str) -> str:
        """Экспорт всех файлов клиента"""
        try:
            client = self.clients_model.get_client_by_id(client_id)
            if not client:
                return "Клиент не найден"
            
            total_files = 0
            exported_orders = 0
            
            for order in client.orders:
                if not order.files:
                    continue
                
                ready_files = [f for f in order.files if os.path.exists(f.path)]
                if not ready_files:
                    continue
                
                # Создаем папку с датой заказа
                try:
                    order_date = datetime.strptime(order.created_at.split()[0], "%d.%m.%Y")
                    date_folder = os.path.join(folder, order_date.strftime("%Y-%m-%d"))
                except:
                    date_folder = os.path.join(folder, "без_даты")
                
                os.makedirs(date_folder, exist_ok=True)
                
                # Создаем архив
                archive_name = f"{order.service_type}_{order.id[:8]}.zip"
                archive_path = os.path.join(date_folder, archive_name)
                
                try:
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
                        for f in ready_files:
                            z.write(f.path, f.name)
                            total_files += 1
                    
                    exported_orders += 1
                except Exception as e:
                    return f"Не удалось создать архив для заказа '{order.service_type}': {e}"
            
            if exported_orders > 0:
                result = f"Экспорт завершен\nЭкспортировано заказов: {exported_orders}\nЭкспортировано файлов: {total_files}\nПапка: {folder}"
                self.successMessage.emit(result)
                return result
            else:
                return "У клиента нет файлов для экспорта."
        except Exception as e:
            logger.error(f"Ошибка экспорта файлов клиента: {e}")
            error = f"Ошибка: {e}"
            self.errorMessage.emit(error)
            return error
    
    @Slot(str, str, str, str, result=str)
    def export_client_orders(self, client_id: str, folder: str, include_files: str, order_ids: str) -> str:
        """Экспорт заказов клиента"""
        try:
            client = self.clients_model.get_client_by_id(client_id)
            if not client:
                return "Клиент не найден"
            
            # Парсим ID заказов
            selected_order_ids = order_ids.split(',') if order_ids else []
            selected_orders = []
            
            if selected_order_ids:
                selected_orders = [o for o in client.orders if o.id in selected_order_ids]
            else:
                selected_orders = client.orders
            
            if not selected_orders:
                return "Не выбрано ни одного заказа для экспорта"
            
            # Экспорт JSON
            json_path = os.path.join(folder, f"{client.name}_заказы.json")
            orders_data = []
            for order in selected_orders:
                order_dict = {
                    'id': order.id,
                    'service_type': order.service_type,
                    'price': order.price,
                    'advance': order.advance,
                    'created_at': order.created_at,
                    'deadline': order.deadline,
                    'status': order.status,
                    'files': [{'name': f.name, 'path': f.path} for f in order.files],
                    'payments': [p.to_dict() for p in order.payments]
                }
                orders_data.append(order_dict)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(orders_data, f, ensure_ascii=False, indent=4)
            
            # Если нужно экспортировать файлы
            if include_files == "true":
                files_folder = os.path.join(folder, "файлы_заказов")
                os.makedirs(files_folder, exist_ok=True)
                
                for order in selected_orders:
                    order_folder = os.path.join(files_folder, order.service_type)
                    os.makedirs(order_folder, exist_ok=True)
                    
                    for file in order.files:
                        if os.path.exists(file.path):
                            try:
                                shutil.copy2(file.path, os.path.join(order_folder, file.name))
                            except Exception as e:
                                logger.error(f"Ошибка копирования файла {file.name}: {e}")
            
            result = f"Экспорт завершен\nЭкспортировано заказов: {len(selected_orders)}\nJSON файл: {json_path}\n{'Файлы экспортированы' if include_files == 'true' else 'Файлы не экспортированы'}"
            self.successMessage.emit(result)
            return result
        except Exception as e:
            logger.error(f"Ошибка экспорта заказов: {e}")
            error = f"Ошибка: {e}"
            self.errorMessage.emit(error)
            return error