import sqlite3
import logging
import json
from typing import List, Optional
from .models import Client, Order, Payment, ProjectFile

# Настройка логгера
logger = logging.getLogger("SQLiteStorage")

class SQLiteStorage:
    def __init__(self, db_path: str = "crm_sqlite.db"):
        self.db_path = db_path
        self.security = None
        self._init_db()

    def set_security_manager(self, security_manager):
        self.security = security_manager

    def _encrypt(self, text: str) -> str:
        if self.security:
            return self.security.encrypt(text)
        return text

    def _decrypt(self, text: str) -> str:
        if self.security:
            return self.security.decrypt(text)
        return text

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        # Enable Foreign Keys globally
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        """Инициализация структуры БД (создание таблицы клиентов)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Создаем таблицу клиентов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clients (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        notes TEXT,
                        email TEXT,
                        telegram TEXT,
                        vk TEXT,
                        facebook TEXT,
                        social_link TEXT
                    )
                """)
                # Создаем таблицу заказов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id TEXT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        service_type TEXT,
                        price REAL,
                        currency TEXT,
                        advance REAL,
                        created_at TEXT,
                        deadline TEXT,
                        status TEXT,
                        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                    )
                """)
                # Создаем таблицу платежей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL,
                        client_id TEXT NOT NULL,
                        type TEXT,
                        amount REAL,
                        date TEXT,
                        note TEXT,
                        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                    )
                """)
                # Создаем таблицу файлов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id TEXT NOT NULL,
                        path TEXT NOT NULL,
                        name TEXT NOT NULL,
                        is_finished BOOLEAN,
                        is_folder BOOLEAN,
                        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                logger.info("SQLite: Database initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"SQLite: Database initialization error: {e}")

    def add_client(self, client: Client) -> bool:
        """Добавление нового клиента"""
        try:
            logger.info(f"SQLiteStorage.add_client: Добавляем клиента ID={client.id}, name='{client.name}'")
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, что все поля имеют значения
                notes_val = client.notes if hasattr(client, 'notes') else ""
                email_val = client.email if hasattr(client, 'email') else ""
                telegram_val = client.telegram if hasattr(client, 'telegram') else ""
                vk_val = client.vk if hasattr(client, 'vk') else ""
                facebook_val = client.facebook if hasattr(client, 'facebook') else ""
                social_link_val = client.social_link if hasattr(client, 'social_link') else ""
                
                encrypted_name = self._encrypt(client.name)
                logger.debug(f"Зашифрованное имя клиента: {encrypted_name[:20] if len(encrypted_name) > 20 else encrypted_name}...")
                
                cursor.execute("""
                    INSERT OR REPLACE INTO clients
                    (id, name, notes, email, telegram, vk, facebook, social_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    client.id,
                    encrypted_name,
                    self._encrypt(notes_val),
                    self._encrypt(email_val),
                    self._encrypt(telegram_val),
                    self._encrypt(vk_val),
                    self._encrypt(facebook_val),
                    self._encrypt(social_link_val)
                ))
                conn.commit()
                logger.info(f"SQLiteStorage.add_client: Клиент успешно добавлен в БД")
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error adding client: {e}", exc_info=True)
            return False

    def migrate_clients(self, clients: List[Client]):
        """Миграция клиентов из JSON"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = [(c.id, c.name, c.notes, c.email, c.telegram, c.vk, c.facebook, c.social_link) for c in clients]
                cursor.executemany("""
                    INSERT OR IGNORE INTO clients
                    (id, name, notes, email, telegram, vk, facebook, social_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                conn.commit()
                logger.info(f"SQLite: Migrated {len(clients)} clients.")
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error migrating clients: {e}")

    def migrate_orders(self, clients: List[Client]):
        """Миграция заказов из JSON"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for client in clients:
                    orders_data = [(
                        o.id, client.id, o.service_type, o.price, o.currency,
                        o.advance, o.created_at, o.deadline, o.status
                    ) for o in client.orders]
                    
                    if orders_data:
                        cursor.executemany("""
                            INSERT OR IGNORE INTO orders
                            (id, client_id, service_type, price, currency, advance, created_at, deadline, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, orders_data)
                conn.commit()
                logger.info("SQLite: Orders migrated successfully.")
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error migrating orders: {e}")

    def migrate_payments(self, clients: List[Client]):
        """Миграция платежей из JSON"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for client in clients:
                    for order in client.orders:
                        payments_data = [(
                            p.id, order.id, client.id, p.type, p.amount, p.date, p.note
                        ) for p in order.payments]
                        
                        if payments_data:
                            cursor.executemany("""
                                INSERT OR IGNORE INTO payments
                                (id, order_id, client_id, type, amount, date, note)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, payments_data)
                conn.commit()
                logger.info("SQLite: Payments migrated successfully.")
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error migrating payments: {e}")

    def migrate_files(self, clients: List[Client]):
        """Миграция файлов из JSON"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for client in clients:
                    for order in client.orders:
                        files_data = [(
                            order.id, f.path, f.name, f.is_finished, f.is_folder
                        ) for f in order.files]
                        
                        if files_data:
                            # Для файлов нет ID в JSON, поэтому просто вставляем
                            # Используем INSERT, дубликаты не проверяем так строго, как с ID
                            # Но можно сделать проверку по path+order_id
                             cursor.executemany("""
                                INSERT INTO files
                                (order_id, path, name, is_finished, is_folder)
                                SELECT ?, ?, ?, ?, ?
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM files WHERE order_id = ? AND path = ?
                                )
                            """, [(d[0], d[1], d[2], d[3], d[4], d[0], d[1]) for d in files_data])
                conn.commit()
                logger.info("SQLite: Files migrated successfully.")
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error migrating files: {e}")

    def add_order(self, client_id: str, order: Order) -> bool:
        """Добавление заказа в SQLite"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO orders
                    (id, client_id, service_type, price, currency, advance, created_at, deadline, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.id, client_id, self._encrypt(order.service_type), order.price, order.currency,
                    order.advance, order.created_at, order.deadline, order.status
                ))
                # Добавляем платежи, если есть (например, аванс при создании)
                for p in order.payments:
                     cursor.execute("""
                        INSERT OR REPLACE INTO payments
                        (id, order_id, client_id, type, amount, date, note)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (p.id, order.id, client_id, p.type, p.amount, p.date, self._encrypt(p.note)))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error adding order: {e}")
            return False

    def add_payment(self, client_id: str, order_id: str, payment: Payment) -> bool:
        """Добавление платежа в SQLite"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO payments
                    (id, order_id, client_id, type, amount, date, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (payment.id, order_id, client_id, payment.type, payment.amount, payment.date, self._encrypt(payment.note)))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error adding payment: {e}")
            return False

    def add_file(self, client_id: str, order_id: str, file_obj: ProjectFile) -> bool:
        """Добавление файла в SQLite"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO files
                    (order_id, path, name, is_finished, is_folder)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, self._encrypt(file_obj.path), self._encrypt(file_obj.name), file_obj.is_finished, file_obj.is_folder))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error adding file: {e}")
            return False

    def delete_client(self, client_id: str) -> bool:
        """Удаление клиента и всех его данных (Cascade)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error deleting client: {e}")
            return False

    def delete_order(self, order_id: str) -> bool:
        """Удаление заказа и его данных"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error deleting order: {e}")
            return False

    def delete_payment(self, payment_id: str) -> bool:
        """Удаление платежа"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error deleting payment: {e}")
            return False

    def delete_file(self, order_id: str, file_path: str) -> bool:
        """Удаление файла"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files WHERE order_id = ? AND path = ?", (order_id, file_path))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error deleting file: {e}")
            return False

    def update_order(self, client_id: str, order: Order) -> bool:
        """Обновление полей заказа"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE orders
                    SET service_type = ?, price = ?, currency = ?, advance = ?, deadline = ?, status = ?
                    WHERE id = ?
                """, (
                    self._encrypt(order.service_type), order.price, order.currency,
                    order.advance, order.deadline, order.status,
                    order.id
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error updating order: {e}")
            return False

    def get_all_clients(self) -> List[Client]:
        """Получение всех клиентов"""
        clients = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM clients")
                rows = cursor.fetchall()
                
                for row in rows:
                    client = Client(
                        id=row['id'],
                        name=self._decrypt(row['name']),
                        notes=self._decrypt(row['notes'] or ""),
                        email=self._decrypt(row['email'] or ""),
                        telegram=self._decrypt(row['telegram'] or ""),
                        vk=self._decrypt(row['vk'] or ""),
                        facebook=self._decrypt(row['facebook'] or ""),
                        social_link=self._decrypt(row['social_link'] or "")
                    )
                    # Загружаем заказы для клиента
                    client.orders = self.get_orders_by_client(client.id)
                    clients.append(client)
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error getting clients: {e}")
        
        return clients

    def get_orders_by_client(self, client_id: str) -> List[Order]:
        """Получение заказов клиента"""
        orders = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM orders WHERE client_id = ?", (client_id,))
                rows = cursor.fetchall()
                
                for row in rows:
                    order = Order(
                        id=row['id'],
                        service_type=self._decrypt(row['service_type']),
                        price=row['price'],
                        currency=row['currency'],
                        advance=row['advance'],
                        created_at=row['created_at'],
                        deadline=row['deadline'],
                        status=row['status'],
                        files=self.get_files_by_order(row['id']),
                        payments=self.get_payments_by_order(row['id'])
                    )
                    orders.append(order)
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error getting orders for client {client_id}: {e}")
        return orders

    def get_payments_by_order(self, order_id: str) -> List[Payment]:
        """Получение платежей заказа"""
        payments = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,))
                rows = cursor.fetchall()
                
                for row in rows:
                    payment = Payment(
                        id=row['id'],
                        type=row['type'],
                        amount=row['amount'],
                        date=row['date'],
                        note=self._decrypt(row['note'] or "")
                    )
                    payments.append(payment)
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error getting payments for order {order_id}: {e}")
        return payments

    def get_files_by_order(self, order_id: str) -> List[ProjectFile]:
        """Получение файлов заказа"""
        files = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM files WHERE order_id = ?", (order_id,))
                rows = cursor.fetchall()
                
                for row in rows:
                    file_obj = ProjectFile(
                        path=self._decrypt(row['path']),
                        name=self._decrypt(row['name']),
                        is_finished=bool(row['is_finished']),
                        is_folder=bool(row['is_folder'])
                    )
                    files.append(file_obj)
        except sqlite3.Error as e:
            logger.error(f"SQLite: Error getting files for order {order_id}: {e}")
        return files