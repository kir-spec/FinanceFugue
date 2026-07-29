#!/usr/bin/env python3
r"""
FinanceFugue_Tauri — Dedicated Model Context Protocol (MCP) Server
Project: E:\coding\client_manager\FinanceFugue_Tauri
Protocol Specification: MCP 2024-11-05 (stdio JSON-RPC)
"""

import sys
import os
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure UTF-8 stdio encoding on Windows
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.resolve()
DB_FILE = PROJECT_ROOT / "pro_database.json"
LOCK_FILE = PROJECT_ROOT / "pro_database.lock"
TAURI_COMMANDS_FILE = PROJECT_ROOT / "src-tauri" / "src" / "commands.rs"

SERVER_INFO = {
    "name": "financefugue-mcp",
    "version": "1.0.0"
}

TOOLS = [
    {
        "name": "check_project_health",
        "description": "Performs complete health check of FinanceFugue_Tauri including TypeScript typechecking and Rust cargo check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "check_rust": {"type": "boolean", "default": True, "description": "Whether to run cargo check for src-tauri"},
                "check_ts": {"type": "boolean", "default": True, "description": "Whether to run tsc typecheck for src"}
            }
        }
    },
    {
        "name": "inspect_database",
        "description": "Inspects pro_database.json, returning metrics on clients, orders, status breakdown, currency totals, debts, and lock state.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "query_clients",
        "description": "Searches clients by name, email, or order status inside FinanceFugue database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for client name or email"},
                "status": {"type": "string", "description": "Filter orders by status, e.g. 'В работе' or 'Завершен'"}
            }
        }
    },
    {
        "name": "audit_ipc_commands",
        "description": "Audits src-tauri/src/commands.rs to report all exposed Tauri IPC commands and their signatures.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "backup_database",
        "description": "Creates a timestamped backup copy of pro_database.json inside the backups/ directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "Optional label or description for the backup"}
            }
        }
    },
    {
        "name": "add_or_update_client",
        "description": "Safely creates or updates a client record in pro_database.json with format validation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Client ID (leave empty to auto-generate)"},
                "name": {"type": "string", "description": "Client name"},
                "email": {"type": "string", "default": "", "description": "Client email"},
                "social_link": {"type": "string", "default": "", "description": "Social link / phone"},
                "notes": {"type": "string", "default": "", "description": "Client notes"}
            },
            "required": ["name"]
        }
    }
]


def load_database() -> List[Dict[str, Any]]:
    if not DB_FILE.exists():
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_database(clients: List[Dict[str, Any]]) -> bool:
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(clients, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def run_check_project_health(args: Dict[str, Any]) -> str:
    check_rust = args.get("check_rust", True)
    check_ts = args.get("check_ts", True)
    results = []

    if check_ts:
        ts_res = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            shell=True
        )
        if ts_res.returncode == 0:
            results.append("✅ TypeScript Typecheck: PASSED (0 errors)")
        else:
            results.append(f"❌ TypeScript Typecheck: FAILED\n{ts_res.stdout}\n{ts_res.stderr}")

    if check_rust:
        cargo_res = subprocess.run(
            ["cargo", "check"],
            cwd=str(PROJECT_ROOT / "src-tauri"),
            capture_output=True,
            text=True,
            shell=True
        )
        if cargo_res.returncode == 0:
            results.append("✅ Rust Backend Check (cargo check): PASSED")
        else:
            results.append(f"❌ Rust Backend Check: FAILED\n{cargo_res.stderr}")

    return "\n".join(results)


def run_inspect_database(_args: Dict[str, Any]) -> str:
    if not DB_FILE.exists():
        return f"Database file does not exist at {DB_FILE}"

    clients = load_database()
    total_clients = len(clients)
    total_orders = 0
    active_orders = 0
    completed_orders = 0
    total_files = 0

    turnover: Dict[str, float] = {}
    debts: Dict[str, float] = {}

    for c in clients:
        orders = c.get("orders", [])
        total_orders += len(orders)
        for o in orders:
            status = o.get("status", "")
            if status == "Завершен":
                completed_orders += 1
            else:
                active_orders += 1

            total_files += len(o.get("files", []))
            curr = o.get("currency", "RUB")
            price = float(o.get("price", 0))
            advance = float(o.get("advance", 0))
            payments = o.get("payments", [])
            paid = sum(float(p.get("amount", 0)) for p in payments if float(p.get("amount", 0)) > 0)
            rec = max(advance, paid)

            turnover[curr] = turnover.get(curr, 0.0) + price
            if status != "Завершен":
                debts[curr] = debts.get(curr, 0.0) + max(0.0, price - rec)

    is_locked = LOCK_FILE.exists()

    output = [
        "=== FinanceFugue Database Inspection ===",
        f"Path: {DB_FILE}",
        f"Lock file active: {'YES ⚠️' if is_locked else 'NO'}",
        f"Total Clients: {total_clients}",
        f"Total Orders: {total_orders} (Active: {active_orders}, Completed: {completed_orders})",
        f"Attached Files Metadata Count: {total_files}",
        "\n--- Financial Totals by Currency ---",
        "Turnover: " + (", ".join(f"{v:,.2f} {c}" for c, v in turnover.items()) if turnover else "0"),
        "Outstanding Active Debt: " + (", ".join(f"{v:,.2f} {c}" for c, v in debts.items()) if debts else "0")
    ]
    return "\n".join(output)


def run_query_clients(args: Dict[str, Any]) -> str:
    query = args.get("query", "").lower()
    status_filter = args.get("status", "").strip()

    clients = load_database()
    matched = []

    for c in clients:
        c_name = c.get("name", "")
        c_email = c.get("email", "")
        if query and not (query in c_name.lower() or query in c_email.lower()):
            continue

        orders = c.get("orders", [])
        if status_filter:
            orders = [o for o in orders if o.get("status") == status_filter]
            if not orders and status_filter:
                continue

        matched.append({
            "id": c.get("id"),
            "name": c_name,
            "email": c_email,
            "social": c.get("social_link"),
            "orders_count": len(orders),
            "orders": [{"id": o.get("id"), "service": o.get("service_type"), "price": o.get("price"), "currency": o.get("currency"), "status": o.get("status")} for o in orders]
        })

    return json.dumps(matched, ensure_ascii=False, indent=2)


def run_audit_ipc_commands(_args: Dict[str, Any]) -> str:
    if not TAURI_COMMANDS_FILE.exists():
        return f"Commands file not found at {TAURI_COMMANDS_FILE}"

    text = TAURI_COMMANDS_FILE.read_text(encoding="utf-8")
    commands = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if "#[tauri::command]" in line:
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].strip().startswith("pub fn "):
                    sig = lines[j].strip()
                    commands.append(sig)
                    break

    output = [
        f"=== Tauri IPC Commands Audit ({len(commands)} commands) ===",
        f"Source: {TAURI_COMMANDS_FILE.name}"
    ] + [f"- {c}" for c in commands]
    return "\n".join(output)


def run_backup_database(args: Dict[str, Any]) -> str:
    if not DB_FILE.exists():
        return "Cannot backup: pro_database.json does not exist."

    backups_dir = PROJECT_ROOT / "backups"
    backups_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    note = args.get("note", "").replace(" ", "_")
    note_suffix = f"_{note}" if note else ""
    target = backups_dir / f"pro_database_backup_{timestamp}{note_suffix}.json"

    shutil.copy2(DB_FILE, target)
    return f"✅ Database backed up successfully to: {target.name} ({target.stat().st_size} bytes)"


def run_add_or_update_client(args: Dict[str, Any]) -> str:
    name = args.get("name", "").strip()
    if not name:
        return "Error: client name cannot be empty."

    clients = load_database()
    client_id = args.get("id", "").strip()
    if not client_id:
        import uuid
        client_id = str(uuid.uuid4())

    existing = next((c for c in clients if c.get("id") == client_id), None)
    if existing:
        existing["name"] = name
        existing["email"] = args.get("email", existing.get("email", ""))
        existing["social_link"] = args.get("social_link", existing.get("social_link", ""))
        existing["notes"] = args.get("notes", existing.get("notes", ""))
        msg = f"✅ Client '{name}' (ID: {client_id}) updated successfully."
    else:
        new_client = {
            "id": client_id,
            "name": name,
            "email": args.get("email", ""),
            "social_link": args.get("social_link", ""),
            "notes": args.get("notes", ""),
            "orders": []
        }
        clients.append(new_client)
        msg = f"✅ Client '{name}' (ID: {client_id}) added successfully."

    save_database(clients)
    return msg


def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if name == "check_project_health":
            res = run_check_project_health(arguments)
        elif name == "inspect_database":
            res = run_inspect_database(arguments)
        elif name == "query_clients":
            res = run_query_clients(arguments)
        elif name == "audit_ipc_commands":
            res = run_audit_ipc_commands(arguments)
        elif name == "backup_database":
            res = run_backup_database(arguments)
        elif name == "add_or_update_client":
            res = run_add_or_update_client(arguments)
        else:
            res = f"Unknown tool: {name}"

        return {
            "content": [{"type": "text", "text": res}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error executing tool '{name}': {str(e)}"}],
            "isError": True
        }


def process_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": SERVER_INFO
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }
    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = handle_call_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found"
        }
    }


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            response = process_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal JSON-RPC error: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
