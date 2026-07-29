#!/usr/bin/env python3
r"""
Codebase Memory — MCP Server for Graph Indexing
Indexes Rust and TypeScript source files into a knowledge graph.
"""
import sys, os, json, re, hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.resolve()
INDEX_FILE = PROJECT_ROOT / ".codebase_index.json"

SERVER_INFO = {"name": "codebase-memory", "version": "1.0.0"}

TOOLS = [
    {
        "name": "index_repository",
        "description": "Scan and index all source files (Rust .rs, TypeScript .ts, HTML) into a knowledge graph.",
        "inputSchema": {"type": "object", "properties": {"force": {"type": "boolean", "default": False}}}
    },
    {
        "name": "index_status",
        "description": "Show indexing status and statistics.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_graph",
        "description": "Search the indexed knowledge graph for functions, structs, IPC commands, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name_pattern": {"type": "string", "description": "Regex pattern for name search"},
                "label": {"type": "string", "description": "Node label: Function, Struct, Command, etc."},
                "relationship": {"type": "string", "description": "Edge type: CALLS, IMPORTS, etc."},
                "max_degree": {"type": "integer", "default": 0, "description": "Maximum number of edges"},
                "min_degree": {"type": "integer", "default": 0, "description": "Minimum number of edges"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "trace_path",
        "description": "Trace call chain from/to a function.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string"},
                "direction": {"type": "string", "default": "both", "description": "inbound, outbound, or both"},
                "depth": {"type": "integer", "default": 3}
            }
        }
    },
    {
        "name": "get_code_snippet",
        "description": "Get source code for a function by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "qualified_name": {"type": "string"}
            }
        }
    },
    {
        "name": "search_code",
        "description": "Full-text search across indexed source files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "file_pattern": {"type": "string", "default": "*.ts"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    }
]


def extract_symbols(file_path: Path, content: str) -> List[Dict]:
    symbols = []
    ext = file_path.suffix
    rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    if ext == ".rs":
        # Rust: pub fn, pub struct, #[tauri::command]
        for m in re.finditer(r'#\[tauri::command\]\s*\n\s*pub\s+fn\s+(\w+)', content):
            symbols.append({"name": m.group(1), "label": "Command", "file": rel, "line": content[:m.start()].count('\n') + 1})
        for m in re.finditer(r'pub\s+fn\s+(\w+)', content):
            name = m.group(1)
            if not any(s['name'] == name for s in symbols):
                symbols.append({"name": name, "label": "Function", "file": rel, "line": content[:m.start()].count('\n') + 1})
        for m in re.finditer(r'pub\s+struct\s+(\w+)', content):
            symbols.append({"name": m.group(1), "label": "Struct", "file": rel, "line": content[:m.start()].count('\n') + 1})

    elif ext == ".ts":
        # TypeScript: function, async function, interface, arrow functions
        for m in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', content):
            symbols.append({"name": m.group(1), "label": "Function", "file": rel, "line": content[:m.start()].count('\n') + 1})
        for m in re.finditer(r'interface\s+(\w+)', content):
            symbols.append({"name": m.group(1), "label": "Interface", "file": rel, "line": content[:m.start()].count('\n') + 1})
        for m in re.finditer(r'const\s+(\w+)\s*=\s*(?:async\s*)?\(', content):
            symbols.append({"name": m.group(1), "label": "Function", "file": rel, "line": content[:m.start()].count('\n') + 1})

    # Extract call edges
    if ext in (".rs", ".ts"):
        func_names = {s['name'] for s in symbols}
        for func_name in func_names:
            # Find the function body
            for m in re.finditer(rf'\b{re.escape(func_name)}\s*\(', content):
                symbols.append({
                    "from": func_name,
                    "to": "UNKNOWN",
                    "label": "CALLS",
                    "file": rel,
                    "line": content[:m.start()].count('\n') + 1
                })

    return symbols


def run_index_repository(args: Dict) -> str:
    force = args.get("force", False)
    if INDEX_FILE.exists() and not force:
        with open(INDEX_FILE, "r") as f:
            data = json.load(f)
        return f"Repository already indexed ({data.get('symbol_count', 0)} symbols, {data.get('file_count', 0)} files). Use force=true to reindex."

    extensions = {".rs", ".ts", ".html"}
    all_symbols = []
    file_count = 0
    files_seen = set()

    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "target", "dist", ".git", "__pycache__")]
        for filename in filenames:
            ext = os.path.splitext(filename)[1]
            if ext not in extensions:
                continue
            filepath = Path(root) / filename
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            syms = extract_symbols(filepath, content)
            all_symbols.extend(syms)
            files_seen.add(str(filepath))
            file_count += 1

    index_data = {
        "indexed_at": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "file_count": file_count,
        "symbol_count": len(all_symbols),
        "symbols": all_symbols
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    return f"Indexed {file_count} files, {len(all_symbols)} symbols."


def run_index_status(_args: Dict) -> str:
    if not INDEX_FILE.exists():
        return "Repository not indexed. Call index_repository first."
    with open(INDEX_FILE, "r") as f:
        data = json.load(f)
    labels = {}
    for s in data.get("symbols", []):
        lbl = s.get("label", "UNKNOWN")
        labels[lbl] = labels.get(lbl, 0) + 1
    return f"Indexed {data['file_count']} files, {data['symbol_count']} symbols. By type: {labels}"


def run_search_graph(args: Dict) -> str:
    if not INDEX_FILE.exists():
        return "Not indexed."
    with open(INDEX_FILE, "r") as f:
        data = json.load(f)

    pattern = args.get("name_pattern")
    label_filter = args.get("label")
    limit = args.get("limit", 20)
    min_degree = args.get("min_degree", 0)
    max_degree = args.get("max_degree", 0)
    relationship = args.get("relationship")

    results = []
    for s in data.get("symbols", []):
        if pattern and not re.search(pattern, s.get("name", "")):
            continue
        if label_filter and s.get("label") != label_filter and s.get("label") != relationship:
            continue
        results.append(s)

    if max_degree or min_degree:
        # Filter by call count (degree)
        name_counts = {}
        for s in results:
            if "from" in s:
                name_counts[s["from"]] = name_counts.get(s["from"], 0) + 1
        results = [s for s in results if s.get("name") and (
            (not max_degree or name_counts.get(s["name"], 0) <= max_degree) and
            (not min_degree or name_counts.get(s["name"], 0) >= min_degree)
        )]

    results = results[:limit]
    return json.dumps(results, ensure_ascii=False, indent=2)


def run_trace_path(args: Dict) -> str:
    if not INDEX_FILE.exists():
        return "Not indexed."
    func_name = args.get("function_name", "")
    direction = args.get("direction", "both")
    depth = args.get("depth", 3)

    with open(INDEX_FILE, "r") as f:
        data = json.load(f)

    # Find the target function
    target = None
    for s in data.get("symbols", []):
        if s.get("name") == func_name:
            target = s
            break

    if not target:
        return f"Function '{func_name}' not found."

    # Find all callers/callees
    edges = []
    for s in data.get("symbols", []):
        if "from" in s:
            if direction in ("both", "outbound") and s.get("from") == func_name:
                edges.append({"from": func_name, "to": "UNKNOWN", "file": s.get("file"), "line": s.get("line")})
            if direction in ("both", "inbound"):
                edges.append(s)

    return json.dumps({"target": target, "edges": edges[:50]}, ensure_ascii=False, indent=2)


def run_get_code_snippet(args: Dict) -> str:
    qualified_name = args.get("qualified_name", "")
    if not INDEX_FILE.exists():
        return "Not indexed."
    with open(INDEX_FILE, "r") as f:
        data = json.load(f)

    for s in data.get("symbols", []):
        if s.get("name") == qualified_name and "file" in s:
            filepath = PROJECT_ROOT / s["file"]
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
                start = max(0, s.get("line", 1) - 3)
                end = min(len(lines), s.get("line", 1) + 15)
                snippet = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[start:end], start=start))
                return f"// {s['file']} line {s.get('line')}\n{snippet}"
    return f"Snippet not found for '{qualified_name}'"


def run_search_code(args: Dict) -> str:
    query = args.get("query", "")
    file_pattern = args.get("file_pattern", "*.ts")
    limit = args.get("limit", 20)

    results = []
    for filepath in PROJECT_ROOT.rglob(file_pattern):
        if any(part in str(filepath) for part in ("node_modules", "target", "dist", ".git")):
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(content.split("\n"), 1):
            if query.lower() in line.lower():
                results.append({"file": str(filepath.relative_to(PROJECT_ROOT)).replace("\\", "/"), "line": i, "content": line.strip()[:200]})
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break
    return json.dumps(results, ensure_ascii=False, indent=2)


def handle_call_tool(name: str, arguments: Dict) -> Dict:
    try:
        if name == "index_repository":
            res = run_index_repository(arguments)
        elif name == "index_status":
            res = run_index_status(arguments)
        elif name == "search_graph":
            res = run_search_graph(arguments)
        elif name == "trace_path":
            res = run_trace_path(arguments)
        elif name == "get_code_snippet":
            res = run_get_code_snippet(arguments)
        elif name == "search_code":
            res = run_search_code(arguments)
        else:
            res = f"Unknown tool: {name}"
        return {"content": [{"type": "text", "text": res}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


def process_request(request: Dict) -> Optional[Dict]:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        return {"jsonrpc": "2.0", "id": req_id, "result": handle_call_tool(params.get("name", ""), params.get("arguments", {}))}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not found"}}


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
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
