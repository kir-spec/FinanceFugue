import json
import uuid
import os
from pathlib import Path
from dataclasses import asdict
from typing import List
from PyQt6.QtWidgets import QMessageBox

from .models import Client, Order, Payment, ProjectFile

# --- ХРАНИЛИЩЕ ---
class CRMStorage:
    def __init__(self, filename="pro_database.json"):
        self.path = Path(filename)

    def load(self) -> List[Client]:
        if not self.path.exists(): 
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                clients = []
                for c_dict in data:
                    orders = []
                    for o in c_dict.get('orders', []):
                        files = [ProjectFile(**fi) for fi in o.get('files', [])]
                        
                        payments = []
                        for p in o.get('payments', []):
                            payment = Payment(
                                id=p.get('id', str(uuid.uuid4())),
                                type=p.get('type', 'платеж'),
                                amount=p.get('amount', 0.0),
                                date=p.get('date', ''),
                                note=p.get('note', '')
                            )
                            payments.append(payment)
                        
                        order = Order(
                            id=o.get('id', str(uuid.uuid4())),
                            service_type=o.get('service_type', ''),
                            price=o.get('price', 0.0),
                            currency=o.get('currency', 'RUB'),
                            advance=o.get('advance', 0.0),
                            created_at=o.get('created_at', ''),
                            deadline=o.get('deadline', ''),
                            status=o.get('status', 'В работе'),
                            files=files,
                            payments=payments
                        )
                        orders.append(order)
                    
                    client = Client(
                        id=c_dict.get('id', str(uuid.uuid4())),
                        name=c_dict.get('name', ''),
                        email=c_dict.get('email', ''),
                        social_link=c_dict.get('social_link', ''),
                        notes=c_dict.get('notes', ''),
                        orders=orders
                    )
                    clients.append(client)
                return clients
        except Exception as e:
            print(f"Ошибка загрузки базы данных: {e}")
            return []

    def save(self, clients: List[Client]):
        try:
            temp_path = self.path.with_suffix('.tmp')
            data = []
            for c in clients:
                c_dict = asdict(c)
                orders_data = []
                for order in c.orders:
                    order_dict = {
                        'id': order.id,
                        'service_type': order.service_type,
                        'price': order.price,
                        'currency': order.currency,
                        'advance': order.advance,
                        'created_at': order.created_at,
                        'deadline': order.deadline,
                        'status': order.status,
                        'files': [asdict(f) for f in order.files],
                        'payments': [p.to_dict() for p in order.payments]
                    }
                    orders_data.append(order_dict)
                c_dict['orders'] = orders_data
                data.append(c_dict)
            
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            if self.path.exists():
                os.remove(self.path)
            os.rename(temp_path, self.path)
        except Exception as e:
            print(f"Ошибка сохранения базы данных: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось сохранить базу данных: {e}")