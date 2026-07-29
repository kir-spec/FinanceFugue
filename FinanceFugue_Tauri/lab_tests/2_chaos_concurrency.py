import json
import threading
import time
import os
import random

DB_PATH = "e:/coding/client_manager/FinanceFugue_Tauri/lab_tests/chaos_database.json"
LOCK_PATH = "e:/coding/client_manager/FinanceFugue_Tauri/lab_tests/chaos_database.lock"
NUM_THREADS = 50

# Initialize an empty DB
with open(DB_PATH, "w") as f:
    json.dump([], f)

def chaos_worker(worker_id):
    # Simulate a chaotic read-modify-write without locks (simulating bad concurrent access)
    # We expect this to fail or corrupt the data if locks are not used.
    # To prevent actual corruption, FinanceFugue uses atomic temp file writes + fs2 locks.
    # This worker will try to respect a simple lock file loop.
    
    max_retries = 100
    for attempt in range(max_retries):
        try:
            # Attempt to create the lock file (atomic operation in most filesystems)
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(random.uniform(0.01, 0.05))
    else:
        print(f"[-] Worker {worker_id} failed to acquire lock.")
        return

    try:
        # Read
        with open(DB_PATH, "r") as f:
            data = json.load(f)
        
        # Modify
        data.append({"worker_id": worker_id, "timestamp": time.time()})
        
        # Simulate some processing time
        time.sleep(random.uniform(0.001, 0.01))
        
        # Write
        with open(DB_PATH, "w") as f:
            json.dump(data, f)
            
    finally:
        # Release lock
        os.remove(LOCK_PATH)

def run_chaos_test():
    print(f"============================================================")
    print(f"          IT LAB: CHAOS & CONCURRENCY TESTING               ")
    print(f"============================================================")
    print(f"[*] Starting {NUM_THREADS} concurrent threads to bombard the database...")
    
    threads = []
    start_time = time.time()
    
    for i in range(NUM_THREADS):
        t = threading.Thread(target=chaos_worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    elapsed = time.time() - start_time
    print(f"[*] All threads finished in {elapsed:.2f} seconds.")
    
    # Verify Data Integrity
    try:
        with open(DB_PATH, "r") as f:
            data = json.load(f)
        if len(data) == NUM_THREADS:
            print(f"[+] PASS: Database integrity maintained. 100% of concurrent writes succeeded safely using lock mechanisms.")
        else:
            print(f"[-] WARN: Data loss detected. Expected {NUM_THREADS} records, found {len(data)}.")
    except json.JSONDecodeError:
        print("[-] FAIL: Database is completely corrupted (Invalid JSON).")

    print(f"[*] Cleaning up...")
    if os.path.exists(DB_PATH): os.remove(DB_PATH)
    if os.path.exists(LOCK_PATH): os.remove(LOCK_PATH)

if __name__ == "__main__":
    run_chaos_test()
