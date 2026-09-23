import json
import os
import shutil

def main():
    db_path = "pro_database.json"
    if not os.path.exists(db_path):
        print("pro_database.json не найден!")
        return

    backup_path = "pro_database.bak"
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}")

    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "clients" in data:
        clients = data["clients"]
    elif isinstance(data, list):
        clients = data
        data = {"schema_version": 1, "clients": clients}
    else:
        print("Неверный формат!")
        return

    for c in clients:
        for o in c.get("orders", []):
            if "price" in o and "price_cents" not in o:
                o["price_cents"] = int(round(float(o.get("price", 0)) * 100))
            if "advance" in o and "advance_cents" not in o:
                o["advance_cents"] = int(round(float(o.get("advance", 0)) * 100))
            for p in o.get("payments", []):
                if "amount" in p and "amount_cents" not in p:
                    p["amount_cents"] = int(round(float(p.get("amount", 0)) * 100))
                    
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"Миграция {len(clients)} клиентов успешно завершена!")

if __name__ == "__main__":
    main()
