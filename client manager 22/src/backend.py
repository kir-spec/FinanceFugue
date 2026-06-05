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
from .sqlite_storage import SQLiteStorage
from .security import SecurityManager, SecurityMode

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
    securityRequest = Signal(str) # 'setup', 'unlock'

    def __init__(self, parent=None, main_window_settings: Optional[dict] = None):
        super().__init__(parent)
        
        self.app_settings = main_window_settings if main_window_settings is not None else self.load_settings()
        
        self.security = SecurityManager(settings_path="crm_settings.json")
        
        db_folder = self.app_settings.get('database_path', os.getcwd())
        if not os.path.isdir(db_folder):
            os.makedirs(db_folder, exist_ok=True)
            logger.info(f"Создана папка для БД: {db_folder}")

        self.db_path = os.path.join(db_folder, "pro_database.db")
        
        self.sqlite = SQLiteStorage(self.db_path)
        self.sqlite.set_security_manager(self.security)
        
        self._clients = []
        self.clients_model = ClientsModel(self)
        
        self._current_client = None
        self._current_client_wrapper = None

        self._stats_in_work = 0
        self._stats_done = 0
        self._stats_total_advance = 0.0
        self._stats_total_debt = 0.0
        self._stats_total_cash = 0.0

        self.last_deleted_file_count = 0
    
    def init_security_check(self):
        if not self.app_settings.get('first_run_completed', False):
            logger.info("Первый запуск приложения: требуется настройка.")
            self.securityRequest.emit("setup")
        elif self.security.has_app_password():
            logger.info("Требуется пароль для входа.")
            self.securityRequest.emit("unlock")
        else:
            logger.info("Безопасность настроена, пароль не требуется. Загружаем данные.")
            self._load_data()
        
    def _load_data(self):
        """Загрузка данных из БД (вызывается после разблокировки или если нет пароля)"""
        try:
            self._clients = self.sqlite.get_all_clients()
            self.clients_model.set_clients(self._clients)
            self.update_stats()
            logger.info(f"Загружено клиентов: {len(self._clients)}")
        except Exception as e:
            logger.critical(f"Критическая ошибка при загрузке данных: {e}", exc_info=True)
            self.errorMessage.emit(f"Критическая ошибка при загрузке данных: {e}. Проверьте файл БД.")
            sys.exit(1)

    @Slot(str, result=bool)
    def unlock_database(self, password: str) -> bool:
        """Разблокировка базы данных паролем"""
        if self.security.unlock(password):
            self._load_data()
            return True
        return False

    @Slot(str, result=bool)
    def unlock_database(self, password: str) -> bool:
        """Разблокировка базы данных паролем для приложения (НЕ для шифрования)"""
        if self.security.check_app_password(password):
            self._load_data()
            self.successMessage.emit("Добро пожаловать!")
            return True
        return False

    @Slot(str, str, bool, str, result=bool)
    def setup_initial_config(self, db_path: str, file_storage_mode: str, encryption_enabled: bool, app_password: Optional[str]) -> bool:
        """
        Применяет первоначальные настройки из диалога первого запуска.
        Обновляет путь к БД, режим хранения файлов и настройки безопасности.
        """
        try:
            self.db_path = os.path.join(db_path, "pro_database.db")
            self.sqlite.path = self.db_path
            
            if encryption_enabled:
                if not self.security.is_encrypted():
                    self.security.setup_encryption(app_password)
                else:
                    self.security.unlock(app_password)
            else:
                self.security.setup_no_encryption()

            if app_password:
                self.security.set_app_password(app_password)
            else:
                self.security.remove_app_password()
            
            self.app_settings['database_path'] = db_path
            self.app_settings['file_storage_mode'] = file_storage_mode
            self.app_settings['encryption_enabled'] = encryption_enabled
            
            self.save_settings()
            self.security._save_security_config()
            
            self._load_data()
            
            logger.info(f"Backend настроен: DB Path={self.db_path}, File Storage={file_storage_mode}, Encryption={encryption_enabled}, App Password={'Yes' if app_password else 'No'}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при первоначальной настройке backend: {e}", exc_info=True)
            self.errorMessage.emit(f"Ошибка при настройке: {e}")
            return False
    
    @Slot(str, bool, result=bool)
    def change_encryption_mode(self, password: str, enable_encryption: bool) -> bool:
        """Смена режима шифрования (требует текущий пароль если зашифровано или устанавливается пароль)"""
        use_internal_key = enable_encryption and not self.security.has_app_password()
        
        if self.security.is_encrypted() and not enable_encryption:
            if self.security.has_app_password() and not self.security.check_app_password(password):
                self.errorMessage.emit("Неверный пароль для расшифровки.")
                return False
            
            self.security.setup_no_encryption()
            self.sqlite.set_security_manager(self.security)
            self._re_save_all_data()
            self.app_settings['encryption_enabled'] = False
            self.save_settings()
            self.successMessage.emit("База данных успешно расшифрована.")
            return True

        elif not self.security.is_encrypted() and enable_encryption:
            
            if self.security.setup_encryption(password if not use_internal_key else None):
                self.sqlite.set_security_manager(self.security)
                self._re_save_all_data()
                self.app_settings['encryption_enabled'] = True
                self.save_settings()
                self.successMessage.emit("База данных успешно зашифрована.")
                return True
            else:
                self.errorMessage.emit("Ошибка при шифровании базы данных.")
                return False
            
        return True
    
    @Slot(str)
    def set_app_password(self, password: str):
        """Устанавливает или меняет пароль для входа в приложение."""
        if password:
            self.security.set_app_password(password)
            self.successMessage.emit("Пароль для входа установлен.")
        else:
            self.security.remove_app_password()
            self.successMessage.emit("Пароль для входа удален.")
        self.security._save_security_config()
        self.save_settings()
    
    def _re_save_all_data(self):
        """Перезаписывает все данные в базе (для смены режима шифрования)"""
        logger.info("Перезапись всех данных в БД для смены режима шифрования.")
        self.sqlite.clear_all_data()
        for client in self._clients:
            self.sqlite.add_client(client)
            for order in client.orders:
                self.sqlite.add_order(client.id, order)
                for p in order.payments:
                    self.sqlite.add_payment(client.id, order.id, p)
        logger.info("Данные успешно перезаписаны.")

    @Slot(str, result=bool)
    def change_encryption_mode(self, password: str, enable_encryption: bool) -> bool:
        """Смена режима шифрования (требует текущий пароль если зашифровано)"""
        # Сценарий: Сейчас зашифровано, хотим расшифровать
        if self.security.is_encrypted() and not enable_encryption:
             # Расшифровка базы
             # 1. Читаем все данные (они уже дешифруются при чтении)
             # 2. Переключаем режим безопасности
             # 3. Перезаписываем базу без шифрования
             if not self.security.check_password(password):
                 return False
             
             self.security.setup_no_encryption()
             self.sqlite.set_security_manager(self.security)
             
             # Принудительная перезапись всех данных
             # (В реальной БД надо делать VACUUM или перезапись таблицы,
             # пока просто обновляем всех клиентов)
             for client in self._clients:
                 self.sqlite.add_client(client)
                 for order in client.orders:
                     self.sqlite.add_order(client.id, order)
                     for p in order.payments:
                         self.sqlite.add_payment(client.id, order.id, p)
             
             return True

        # Сценарий: Сейчас не зашифровано, хотим зашифровать
        elif not self.security.is_encrypted() and enable_encryption:
             self.security.setup_encryption(password)
             self.sqlite.set_security_manager(self.security)
             
             # Принудительная перезапись всех данных с шифрованием
             for client in self._clients:
                 self.sqlite.add_client(client)
                 for order in client.orders:
                     self.sqlite.add_order(client.id, order)
                     for p in order.payments:
                         self.sqlite.add_payment(client.id, order.id, p)
             return True
             
        return True # Ничего не изменилось

    def load_settings(self):
        settings_path = Path("crm_settings.json")
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Файл настроек поврежден или пуст, используем настройки по умолчанию.")
                return {}
            except Exception as e:
                logger.error(f"Ошибка при загрузке настроек из {settings_path}: {e}", exc_info=True)
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
        return not self.app_settings.get('first_run_completed', False)

    def mark_first_run_completed(self, settings):
        self.app_settings['first_run_completed'] = True
        self.save_settings()
        
        if settings.get('file_storage_mode') == 'copy':
            db_folder = self.app_settings.get('database_path', os.getcwd())
            files_folder = os.path.join(db_folder, "attached_files")
            os.makedirs(files_folder, exist_ok=True)
            logger.info(f"Создана папка для прикрепленных файлов: {files_folder}")

    def get_all_clients_from_backend(self) -> List[Client]:
        return self._clients

    @Property(str, constant=True)
    def homePath(self):
        return QUrl.fromLocalFile(str(Path.home())).toString()

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
        self.update_stats()
    
    @Property(str, notify=clientsChanged)
    def lastDeletedFileCount(self):
        return str(self.last_deleted_file_count)

    @Property(str, notify=statsChanged)
    def databasePath(self):
        return os.path.dirname(self.db_path)

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
        
        if self.sqlite.add_client(new_client):
            self._clients.append(new_client)
            self.clients_model.set_clients(self._clients)
            self.save_database()
            logger.info(f"Добавлен новый клиент: {new_client.name}")
            self.successMessage.emit(f"Клиент '{name}' успешно создан")
            return True
        else:
            self.errorMessage.emit("Ошибка сохранения клиента в базе данных")
            return False

    @Slot(str, result=str)
    def add_client_get_id(self, name: str) -> str:
        """Добавляет клиента и возвращает его ID."""
        if not name.strip():
            self.errorMessage.emit("Введите имя клиента")
            return ""
        
        if any(c.name.lower() == name.strip().lower() for c in self._clients):
            self.errorMessage.emit("Клиент с таким именем уже существует")
            return ""
        
        new_client = Client(
            id=str(uuid.uuid4()),
            name=name.strip()
        )
        
        if self.sqlite.add_client(new_client):
            self._clients.append(new_client)
            self.clients_model.set_clients(self._clients)
            self.save_database()
            logger.info(f"Добавлен новый клиент: {new_client.name} (ID: {new_client.id})")
            self.successMessage.emit(f"Клиент '{name}' успешно создан")
            return new_client.id
        else:
            self.errorMessage.emit("Ошибка сохранения клиента в базе данных")
            return ""

    @Slot(str, str, str, str, str, str, str, result=bool)
    def update_client(self, client_id: str, name: str, email: str, telegram: str, vk: str, facebook: str, notes: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            client.name = name
            client.email = email
            client.telegram = telegram
            client.vk = vk
            client.facebook = facebook
            client.notes = notes
            
            self.sqlite.add_client(client)
            
            wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
            if wrapper:
                wrapper.set_name(name)
                wrapper.set_email(email)
                # wrapper.set_telegram(telegram)
                # wrapper.set_vk(vk)
                # wrapper.set_facebook(facebook)
                wrapper.set_notes(notes)
            
            self.save_database()
            self.refresh_clients()
            return True
        return False

    def update_client_full(self, client_obj: Client) -> bool:
        """Обновляет все данные клиента (и его заказов) в БД. Используется из MainWindow."""
        try:
            self.sqlite.add_client(client_obj)
            
            for order in client_obj.orders:
                self.sqlite.add_order(client_obj.id, order)
                for file_obj in order.files:
                    self.sqlite.add_file(client_obj.id, order.id, file_obj)
                for payment_obj in order.payments:
                    self.sqlite.add_payment(client_obj.id, order.id, payment_obj)

            self.clients_model.set_clients(self._clients)
            self.update_stats()
            logger.debug(f"Полное обновление данных клиента '{client_obj.name}' (ID: {client_obj.id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка полного обновления клиента '{client_obj.name}': {e}", exc_info=True)
            self.errorMessage.emit(f"Ошибка полного обновления клиента: {e}")
            return False

    @Slot(str, result=bool)
    def delete_client(self, client_id: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            return self.delete_clients_with_files([client], False)
        return False
        
    def delete_clients_with_files(self, clients_to_delete: List[Client], delete_from_disk: bool) -> bool:
        """
        Удаляет клиентов из БД и, опционально, связанные файлы с диска.
        Возвращает True в случае успеха, False в случае ошибки.
        """
        success = True
        self.last_deleted_file_count = 0
        db_folder = os.path.dirname(self.db_path)
        attached_files_dir = os.path.join(db_folder, "attached_files")

        for client in clients_to_delete:
            if client in self._clients:
                if delete_from_disk:
                    for order in client.orders:
                        for file in order.files:
                            if os.path.exists(file.path):
                                try:
                                    if os.path.commonpath([os.path.abspath(file.path), os.path.abspath(attached_files_dir)]) == os.path.abspath(attached_files_dir):
                                        os.remove(file.path)
                                        self.last_deleted_file_count += 1
                                    else:
                                        logger.warning(f"Файл {file.path} не находится в папке 'attached_files', пропуск удаления с диска.")
                                except Exception as e:
                                    logger.error(f"Не удалось удалить файл {file.path} с диска: {e}")
                
                if not self.sqlite.delete_client(client.id):
                    self.errorMessage.emit(f"Ошибка удаления клиента '{client.name}' из базы данных.")
                    success = False
                else:
                    self._clients.remove(client)
                    logger.info(f"Удален клиент: {client.name} (ID: {client.id})")
        
        self.clients_model.set_clients(self._clients)
        self.save_database()
        
        if delete_from_disk and os.path.exists(attached_files_dir):
            try:
                for root, dirs, files in os.walk(attached_files_dir, topdown=False):
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            logger.debug(f"Удалена пустая папка: {dir_path}")
            except Exception as e:
                logger.warning(f"Ошибка при удалении пустых папок: {e}")

        return success

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
        
        if self.sqlite.add_order(client_id, new_order):
            client.orders.append(new_order)
            
            wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
            if wrapper:
                wrapper.refresh_orders()
            
            self.save_database()
            logger.info(f"Добавлен заказ '{service_type}' для клиента {client.name}")
            self.successMessage.emit(f"Заказ '{service_type}' успешно создан")
            return True
        else:
            self.errorMessage.emit("Ошибка сохранения заказа в базе данных")
            return False

    @Slot(str, str, result=bool)
    def delete_order(self, client_id: str, order_id: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                if self.sqlite.delete_order(order_id):
                    client.orders.remove(order)
                    wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                    if wrapper:
                        wrapper.refresh_orders()
                    
                    self.save_database()
                    logger.info(f"Удален заказ '{order.service_type}'")
                    self.successMessage.emit(f"Заказ '{order.service_type}' успешно удален")
                    return True
                else:
                    self.errorMessage.emit("Ошибка удаления заказа из базы данных")
        return False

    @Slot(str, str, str, result=bool)
    def update_order_status(self, client_id: str, order_id: str, status: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                order.status = status
                
                self.sqlite.add_order(client_id, order)
                
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
                
                self.sqlite.add_order(client_id, order)
                
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
                
                self.sqlite.add_order(client_id, order)
                
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
                
                self.sqlite.add_order(client_id, order)
                
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
                    
                    new_payment = order.payments[-1]
                    if self.sqlite.add_payment(client_id, order_id, new_payment):
                        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                        if wrapper:
                            wrapper.refresh_orders()
                        
                        self.save_database()
                        return True
                    else:
                         # Rollback in-memory
                        order.payments.pop()
                        self.errorMessage.emit("Ошибка сохранения платежа в БД")
                        return False
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
                    # Find payment to restore if needed
                    payment_to_delete = next((p for p in order.payments if p.id == payment_id), None)
                    
                    order.delete_payment(payment_id)
                    
                    if self.sqlite.delete_payment(payment_id):
                        self.sqlite.add_order(client_id, order) # Update order totals/advance logic
                        
                        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                        if wrapper:
                            wrapper.refresh_orders()
                        
                        self.save_database()
                        return True
                    else:
                        # Restore in memory
                        if payment_to_delete:
                            order.payments.append(payment_to_delete)
                        self.errorMessage.emit("Ошибка удаления платежа из БД")
                        return False
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
                storage_mode = self.app_settings.get('file_storage_mode', 'link')
                
                if storage_mode == 'copy':
                    db_folder = self.app_settings.get('database_path', os.getcwd())
                    if not os.path.exists(db_folder):
                        os.makedirs(db_folder, exist_ok=True)
                        logger.info(f"Создана папка для базы данных: {db_folder}")

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
                
                if self.sqlite.add_file(client_id, order_id, project_file):
                    order.files.append(project_file)
                    
                    wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                    if wrapper:
                        wrapper.refresh_orders()
                    
                    self.save_database()
                    return True
                else:
                    self.errorMessage.emit("Ошибка сохранения файла в БД")
                    return False
        return False

    @Slot(str, str, str, result=bool)
    def delete_file(self, client_id: str, order_id: str, file_path: str) -> bool:
        client = self.clients_model.get_client_by_id(client_id)
        if client:
            order = next((o for o in client.orders if o.id == order_id), None)
            if order:
                file_obj = next((f for f in order.files if f.path == file_path), None)
                if file_obj:
                    if self.sqlite.delete_file(order_id, file_path):
                        order.files.remove(file_obj)
                        
                        wrapper = self.clients_model.get_client_wrapper_by_id(client_id)
                        if wrapper:
                            wrapper.refresh_orders()
                        
                        self.save_database()
                        return True
                    else:
                        self.errorMessage.emit("Ошибка удаления файла из БД")
                        return False
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
                        
                        # Удаляем старую запись файла, добавляем новую (проще чем update)
                        self.sqlite.delete_file(order_id, file_obj.path)
                        
                        file_obj.path = new_path
                        file_obj.name = new_name.strip()
                        
                        self.sqlite.add_file(client_id, order_id, file_obj)
                        
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
            if self.sqlite.export_to_json(path, self._clients):
                self.successMessage.emit(f"База данных экспортирована в: {path}")
                return True
            else:
                self.errorMessage.emit("Не удалось экспортировать базу данных.")
                return False
        except Exception as e:
            logger.error(f"Ошибка экспорта JSON: {e}", exc_info=True)
            self.errorMessage.emit(f"Не удалось экспортировать базу данных: {e}")
            return False

    @Slot(str, result=bool)
    def import_json(self, path: str) -> bool:
        try:
            db_folder = os.path.dirname(self.db_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_db_path = os.path.join(db_folder, f"pro_database_backup_{timestamp}.db")
            
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, backup_db_path)
                logger.info(f"Создан бэкап текущей БД: {backup_db_path}")

            if self.sqlite.import_from_json(path):
                self._clients = self.sqlite.get_all_clients()
                self._current_client = None
                self._current_client_wrapper = None
                self.currentClientChanged.emit()
                self.clients_model.set_clients(self._clients)
                self.save_database()
                
                self.successMessage.emit(f"База данных успешно импортирована. Создан бэкап: {backup_db_path}")
                return True
            else:
                self.errorMessage.emit("Выбранный файл не содержит корректных данных или произошла ошибка импорта.")
                return False
        except Exception as e:
            logger.error(f"Ошибка импорта JSON: {e}", exc_info=True)
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
            db_folder = os.path.dirname(self.db_path)
            attached_files_dir = os.path.join(db_folder, "attached_files")

            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                if os.path.exists(self.db_path):
                    zip_file.write(self.db_path, os.path.basename(self.db_path))
                
                file_count = 0
                if os.path.exists(attached_files_dir):
                    for root, dirs, files in os.walk(attached_files_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, db_folder)
                            zip_file.write(file_path, arcname)
                            file_count += 1

                result = f"Полная резервная копия успешно создана.\n\nФайл: {path}\n" \
                         f"Размер БД: {self.get_database_size()}\nФайлов в архиве: {file_count}"
                self.successMessage.emit(result)
                return result
        except Exception as e:
            logger.error(f"Ошибка создания полного бэкапа: {e}", exc_info=True)
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
            
            # Экспорт JSON через SQLiteStorage
            json_path = os.path.join(folder, f"{client.name}_заказы.json")
            if not self.sqlite.export_orders_to_json(json_path, client_id, selected_orders):
                return "Не удалось экспортировать заказы в JSON."

            # Если нужно экспортировать файлы
            if include_files == "true":
                files_folder = os.path.join(folder, "файлы_заказов", client.name) # Группируем по клиенту
                os.makedirs(files_folder, exist_ok=True)
                
                exported_file_count = 0
                for order in selected_orders:
                    order_folder = os.path.join(files_folder, order.service_type)
                    os.makedirs(order_folder, exist_ok=True)
                    
                    for file in order.files:
                        if os.path.exists(file.path):
                            try:
                                shutil.copy2(file.path, os.path.join(order_folder, file.name))
                                exported_file_count += 1
                            except Exception as e:
                                logger.error(f"Ошибка копирования файла {file.name}: {e}")
            
            result = f"Экспорт завершен\nЭкспортировано заказов: {len(selected_orders)}\nJSON файл: {json_path}\n" \
                     f"{'Файлы экспортированы в отдельную папку' if include_files == 'true' else 'Файлы не экспортированы'}"
            self.successMessage.emit(result)
            return result
        except Exception as e:
            logger.error(f"Ошибка экспорта заказов: {e}", exc_info=True)
            error = f"Ошибка: {e}"
            self.errorMessage.emit(error)
            return error
    
    @Slot(result=str)
    def get_database_size(self) -> str:
        """Возвращает размер файла базы данных в читаемом формате."""
        if os.path.exists(self.db_path):
            size_bytes = os.path.getsize(self.db_path)
            if size_bytes < 1024:
                return f"{size_bytes} байт"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} КБ"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} МБ"
        return "0 байт"

    @Slot(bool, result=bool)
    def delete_all_files(self, delete_from_disk: bool) -> bool:
        """Удаляет все файлы из базы данных (физически и ссылки)"""
        self.last_deleted_file_count = 0
        db_folder = os.path.dirname(self.db_path)
        attached_files_dir = os.path.join(db_folder, "attached_files")

        try:
            # 1. Очищаем списки файлов в объектах и в БД
            for client in self._clients:
                for order in client.orders:
                    self.last_deleted_file_count += len(order.files)
                    order.files = []
                    # Обновляем заказы в БД, чтобы у них очистились файлы
                    self.sqlite.add_order(client.id, order)
            
            # 2. Удаляем физическую папку attached_files если нужно
            if delete_from_disk and os.path.exists(attached_files_dir):
                shutil.rmtree(attached_files_dir)
                os.makedirs(attached_files_dir, exist_ok=True) # Создаем пустую обратно
                logger.info(f"Удалена папка со всеми прикрепленными файлами: {attached_files_dir}")
            
            self.save_database() # Обновляем статистику
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления всех файлов: {e}", exc_info=True)
            self.errorMessage.emit(f"Не удалось удалить все файлы: {e}")
            return False

    @Slot(bool, result=bool)
    def delete_full_database(self, delete_files_disk: bool) -> bool:
        """Полное удаление базы данных и, опционально, связанных файлов."""
        try:
            # 1. Удаляем файлы с диска если нужно
            if delete_files_disk:
                db_folder = os.path.dirname(self.db_path)
                attached_files_dir = os.path.join(db_folder, "attached_files")
                if os.path.exists(attached_files_dir):
                    shutil.rmtree(attached_files_dir)
                    logger.info(f"Удалена папка с прикрепленными файлами: {attached_files_dir}")
            
            # 2. Удаляем сам файл базы данных
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info(f"Удален файл базы данных: {self.db_path}")
            
            # 3. Сбрасываем внутреннее состояние
            self._clients = []
            self._current_client = None
            self._current_client_wrapper = None
            self.clients_model.set_clients(self._clients)
            self.update_stats()
            
            # Пересоздаем пустую базу данных
            self.sqlite = SQLiteStorage(self.db_path)
            self.sqlite.set_security_manager(self.security)
            # Таблицы создаются в init, но поскольку файл удален, нужно переинициализировать
            self.sqlite._init_db()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка полного удаления базы данных: {e}", exc_info=True)
            self.errorMessage.emit(f"Не удалось полностью удалить базу данных: {e}")
            return False