import json
import time
import uuid
import os

DB_PATH = "e:/coding/client_manager/FinanceFugue_Tauri/lab_tests/stress_database.json"
NUM_CLIENTS = 100000
ORDERS_PER_CLIENT = 5
PAYMENTS_PER_ORDER = 2

def generate_stress_db():
    print(f"============================================================")
    print(f"          IT LAB: STRESS & PERFORMANCE TESTING              ")
    print(f"============================================================")
    print(f"[*] Generating {NUM_CLIENTS} clients with {ORDERS_PER_CLIENT} orders each...")
    start_time = time.time()
    
    clients = []
    for i in range(NUM_CLIENTS):
        client = {
            "id": str(uuid.uuid4()),
            "name": f"Stress Test Client {i}",
            "phone": "+1234567890",
            "email": f"client{i}@stresstest.com",
            "social_link": "",
            "notes": "Generated for stress testing to evaluate JSON parser and memory overhead.",
            "created_at": "2026-07-29T12:00:00Z",
            "orders": []
        }
        
        for j in range(ORDERS_PER_CLIENT):
            order = {
                "id": str(uuid.uuid4()),
                "description": f"Bulk Order {j}",
                "status": "pending",
                "created_at": "2026-07-29T12:00:00Z",
                "deadline": "2026-08-29T12:00:00Z",
                "total_price": 500.50,
                "payments": [],
                "expenses": []
            }
            
            for k in range(PAYMENTS_PER_ORDER):
                order["payments"].append({
                    "id": str(uuid.uuid4()),
                    "amount": 100.0,
                    "date": "2026-07-29T12:00:00Z",
                    "method": "bank_transfer",
                    "is_prepayment": k == 0
                })
            
            client["orders"].append(order)
            
        clients.append(client)
        
    print(f"[*] Generation done in {time.time() - start_time:.2f} seconds.")
    
    print(f"[*] Serializing and writing to {DB_PATH}...")
    start_time = time.time()
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(clients, f, separators=(',', ':'))
    
    write_time = time.time() - start_time
    file_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    
    print(f"[*] Write done in {write_time:.2f} seconds. File size: {file_size_mb:.2f} MB")
    
    print("[*] Testing read performance...")
    start_time = time.time()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    read_time = time.time() - start_time
    
    print(f"[*] Read and deserialized {len(loaded)} clients in {read_time:.2f} seconds.")
    
    if read_time < 5.0:
        print("[+] PASS: Read time is highly optimized (< 5s). System is resilient to huge data volumes.")
    else:
        print("[-] WARN: Read time is slow (> 5s). Consider using streaming JSON parsers or pagination.")

    print(f"[*] Cleaning up {DB_PATH}...")
    os.remove(DB_PATH)
    print(f"[+] Cleanup complete.")

if __name__ == "__main__":
    generate_stress_db()
