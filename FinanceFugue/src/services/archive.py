import logging
from typing import List, Optional

from ..models import Client
from ..storage import CRMStorage

logger = logging.getLogger("ArchiveManager")

class ArchiveManager:
    def __init__(self, active_storage: CRMStorage):
        self.active_storage = active_storage
        
        # Determine archive path based on active path
        active_path = str(self.active_storage.path)
        archive_path = active_path.replace("pro_database.json", "pro_archive.json")
        if "pro_archive.json" not in archive_path:
            # Fallback if the original name wasn't pro_database.json
            archive_path = str(self.active_storage.path.parent / "pro_archive.json")
            
        self.archive_storage = CRMStorage(archive_path)
        self._archive_clients_cache: Optional[List[Client]] = None

    def get_archive_clients(self) -> List[Client]:
        if self._archive_clients_cache is None:
            self._archive_clients_cache = self.archive_storage.load()
        return self._archive_clients_cache

    def _get_or_create_archive_client(self, archive_clients: List[Client], active_client: Client) -> Client:
        for c in archive_clients:
            if c.id == active_client.id:
                return c
        
        # Create a copy without orders
        new_client = Client(
            id=active_client.id,
            name=active_client.name,
            email=active_client.email,
            social_link=active_client.social_link,
            notes=active_client.notes,
            orders=[]
        )
        archive_clients.append(new_client)
        return new_client

    def archive_order(self, active_clients: List[Client], client_id: str, order_id: str) -> bool:
        """Перемещает один завершенный заказ в архив."""
        active_client = next((c for c in active_clients if c.id == client_id), None)
        if not active_client:
            return False
            
        order_idx = next((i for i, o in enumerate(active_client.orders) if o.id == order_id), -1)
        if order_idx == -1:
            return False
            
        order = active_client.orders[order_idx]
        if order.status != "Завершен":
            raise ValueError("Можно архивировать только завершенные заказы")

        # Загружаем архив
        archive_clients = self.get_archive_clients()
        arch_client = self._get_or_create_archive_client(archive_clients, active_client)
        
        # Перемещаем
        arch_client.orders.append(order)
        active_client.orders.pop(order_idx)
        
        # Сохраняем
        self.archive_storage.save(archive_clients)
        self._archive_clients_cache = archive_clients
        self.active_storage.save(active_clients)
        return True

    def archive_completed_orders(self, active_clients: List[Client], client_id: str) -> int:
        """Перемещает все завершенные заказы клиента в архив."""
        active_client = next((c for c in active_clients if c.id == client_id), None)
        if not active_client:
            return 0
            
        completed_orders = [o for o in active_client.orders if o.status == "Завершен"]
        if not completed_orders:
            return 0
            
        archive_clients = self.get_archive_clients()
        arch_client = self._get_or_create_archive_client(archive_clients, active_client)
        
        arch_client.orders.extend(completed_orders)
        active_client.orders = [o for o in active_client.orders if o.status != "Завершен"]
        
        self.archive_storage.save(archive_clients)
        self._archive_clients_cache = archive_clients
        self.active_storage.save(active_clients)
        return len(completed_orders)

    def archive_client(self, active_clients: List[Client], client_id: str) -> bool:
        """Перемещает клиента целиком (со всеми заказами) в архив."""
        client_idx = next((i for i, c in enumerate(active_clients) if c.id == client_id), -1)
        if client_idx == -1:
            return False
            
        active_client = active_clients.pop(client_idx)
        
        archive_clients = self.get_archive_clients()
        arch_client = self._get_or_create_archive_client(archive_clients, active_client)
        
        # Добавляем все заказы, которых еще нет в архиве
        existing_order_ids = {o.id for o in arch_client.orders}
        for o in active_client.orders:
            if o.id not in existing_order_ids:
                arch_client.orders.append(o)
                
        self.archive_storage.save(archive_clients)
        self._archive_clients_cache = archive_clients
        self.active_storage.save(active_clients)
        return True
