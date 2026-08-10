import time
import random
from src.models import Client, Order
from src.services.client_stats import sum_by_currency, calculate_global_dashboard

def test_extreme_scale():
    # Создаем 10 000 клиентов по 50 заказов = 500 000 заказов
    num_clients = 10000
    orders_per_client = 50
    total_orders = num_clients * orders_per_client
    
    clients = []
    
    start_time = time.time()
    for c_idx in range(num_clients):
        orders = []
        for o_idx in range(orders_per_client):
            # Разные цены, чтобы усложнить аккумуляцию
            price = random.choice([10.1, 55.55, 1000.0, 99.99])
            o = Order(id=f"o_{c_idx}_{o_idx}", service_type="A", price=price)
            # Вносим полную оплату
            o.add_payment(price, "платеж")
            orders.append(o)
            
        c = Client(id=f"c_{c_idx}", name=f"Client {c_idx}", orders=orders)
        clients.append(c)
        
    generation_time = time.time() - start_time
    print(f"Generated {total_orders} orders in {generation_time:.2f}s")
    
    # 1. Измеряем скорость и точность sum_by_currency
    start_time = time.time()
    all_orders = [o for c in clients for o in c.orders]
    cash_by = sum_by_currency(all_orders, field="total_received")
    calc_time = time.time() - start_time
    
    print(f"Aggregation time for {total_orders} items: {calc_time:.4f}s")
    print("Accumulated cash:", repr(cash_by.get("RUB", 0.0)))
    
    # 2. Измеряем скорость формирования дашборда (имитация загрузки приложения)
    start_time = time.time()
    dashboard = calculate_global_dashboard(clients)
    dash_time = time.time() - start_time
    print(f"Dashboard generation time: {dash_time:.4f}s")

if __name__ == "__main__":
    # Фиксируем seed для воспроизводимости
    random.seed(42)
    test_extreme_scale()
