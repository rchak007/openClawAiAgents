#!/usr/bin/env python3
"""
Todo Tree — Premium hierarchical todo manager
Deploy from: ~/github/openClawAiAgents/
Reads/writes: ~/.openclaw/workspace/todos.json
Access: http://100.77.66.80:8081?key=YOUR_KEY
"""

import json
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# ─── Config ───────────────────────────────────────────────────────────────────

TODO_FILE = os.environ.get(
    "TODO_FILE",
    os.path.expanduser("~/.openclaw/workspace/todos.json")
)

SECRET_KEY = os.environ.get("TODO_SECRET", "")
if not SECRET_KEY:
    key_file = os.path.expanduser("~/.openclaw/.todo-tree-secret")
    if os.path.exists(key_file):
        SECRET_KEY = open(key_file).read().strip()
    else:
        SECRET_KEY = secrets.token_urlsafe(32)
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, "w") as f:
            f.write(SECRET_KEY)
        print(f"[TodoTree] Generated new secret key: {SECRET_KEY}")

app = FastAPI(title="Todo Tree")

# ─── Auth ─────────────────────────────────────────────────────────────────────

async def verify_key(key: str = Query(default="")):
    if not key or key != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing access key")
    return key

# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_todos() -> dict:
    if not os.path.exists(TODO_FILE):
        return {"nodes": {}}
    with open(TODO_FILE, "r") as f:
        data = json.load(f)
    if "nodes" not in data and "categories" in data:
        data = {"nodes": data["categories"]}
    if "nodes" not in data:
        data = {"nodes": {}}
    return data

def save_todos(data: dict):
    if os.path.exists(TODO_FILE):
        backup_dir = os.path.dirname(TODO_FILE)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"todos_backup_{ts}.json")
        shutil.copy2(TODO_FILE, backup_path)
        backups = sorted(Path(backup_dir).glob("todos_backup_*.json"))
        for old in backups[:-5]:
            old.unlink()
    with open(TODO_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_node_at_path(nodes: dict, path: list[str]) -> dict:
    current = nodes
    for i, segment in enumerate(path):
        if segment not in current:
            current[segment] = {}
        node = current[segment]
        if i < len(path) - 1:
            if "children" not in node:
                node["children"] = {}
            current = node["children"]
        else:
            return node
    return current

def get_next_id(node: dict) -> int:
    items = node.get("items", [])
    if not items:
        return 1
    return max(item.get("id", 0) for item in items) + 1

# ─── API Models ───────────────────────────────────────────────────────────────

class AddItemRequest(BaseModel):
    path: list[str]
    text: str

class EditItemRequest(BaseModel):
    path: list[str]
    item_id: int
    text: Optional[str] = None
    done: Optional[bool] = None

class DeleteItemRequest(BaseModel):
    path: list[str]
    item_id: int

class AddNodeRequest(BaseModel):
    path: list[str]
    name: str

class DeleteNodeRequest(BaseModel):
    path: list[str]

class RenameNodeRequest(BaseModel):
    path: list[str]
    new_name: str

class MoveItemRequest(BaseModel):
    from_path: list[str]
    item_id: int
    to_path: list[str]

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/todos")
async def get_todos(key: str = Depends(verify_key)):
    return load_todos()

@app.post("/api/item/add")
async def add_item(req: AddItemRequest, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    if "items" not in node:
        node["items"] = []
    new_id = get_next_id(node)
    item = {
        "id": new_id,
        "text": req.text,
        "done": False,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    node["items"].append(item)
    save_todos(data)
    return {"ok": True, "item": item}

@app.post("/api/item/edit")
async def edit_item(req: EditItemRequest, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    for item in node.get("items", []):
        if item["id"] == req.item_id:
            if req.text is not None:
                item["text"] = req.text
            if req.done is not None:
                item["done"] = req.done
            save_todos(data)
            return {"ok": True, "item": item}
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/api/item/delete")
async def delete_item(req: DeleteItemRequest, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    items = node.get("items", [])
    node["items"] = [i for i in items if i["id"] != req.item_id]
    save_todos(data)
    return {"ok": True}

@app.post("/api/item/move")
async def move_item(req: MoveItemRequest, key: str = Depends(verify_key)):
    data = load_todos()
    nodes = data["nodes"]
    src = get_node_at_path(nodes, req.from_path)
    items = src.get("items", [])
    moved = None
    for i, item in enumerate(items):
        if item["id"] == req.item_id:
            moved = items.pop(i)
            break
    if not moved:
        raise HTTPException(status_code=404, detail="Item not found")
    dst = get_node_at_path(nodes, req.to_path)
    if "items" not in dst:
        dst["items"] = []
    moved["id"] = get_next_id(dst)
    dst["items"].append(moved)
    save_todos(data)
    return {"ok": True, "item": moved}

@app.post("/api/node/add")
async def add_node(req: AddNodeRequest, key: str = Depends(verify_key)):
    data = load_todos()
    nodes = data["nodes"]
    if not req.path:
        if req.name not in nodes:
            nodes[req.name] = {}
    else:
        parent = get_node_at_path(nodes, req.path)
        if "children" not in parent:
            parent["children"] = {}
        if req.name not in parent["children"]:
            parent["children"][req.name] = {}
    save_todos(data)
    return {"ok": True}

@app.post("/api/node/delete")
async def delete_node(req: DeleteNodeRequest, key: str = Depends(verify_key)):
    data = load_todos()
    nodes = data["nodes"]
    if len(req.path) == 1:
        nodes.pop(req.path[0], None)
    else:
        parent = get_node_at_path(nodes, req.path[:-1])
        parent.get("children", {}).pop(req.path[-1], None)
    save_todos(data)
    return {"ok": True}

@app.post("/api/node/rename")
async def rename_node(req: RenameNodeRequest, key: str = Depends(verify_key)):
    data = load_todos()
    nodes = data["nodes"]
    old_name = req.path[-1]
    if len(req.path) == 1:
        if old_name in nodes:
            nodes[req.new_name] = nodes.pop(old_name)
    else:
        parent = get_node_at_path(nodes, req.path[:-1])
        children = parent.get("children", {})
        if old_name in children:
            children[req.new_name] = children.pop(old_name)
    save_todos(data)
    return {"ok": True}

# ─── Frontend ─────────────────────────────────────────────────────────────────

FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>TodoTree</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Source+Code+Pro:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg-base: #FAFAF8;
  --bg-surface: #FFFFFF;
  --bg-raised: #F5F4F0;
  --bg-hover: #EFEEE8;
  --bg-active: #E8E6DE;
  --bg-input: #FFFFFF;
  --border-subtle: #E5E3DB;
  --border-medium: #D4D1C7;
  --border-focus: #E07A3A;
  --text-primary: #1A1815;
  --text-secondary: #6B6560;
  --text-tertiary: #9C9790;
  --text-inverse: #FFFFFF;
  --accent: #E07A3A;
  --accent-hover: #CC6A2E;
  --accent-soft: rgba(224, 122, 58, 0.10);
  --accent-medium: rgba(224, 122, 58, 0.18);
  --green: #2D8A56;
  --green-soft: rgba(45, 138, 86, 0.10);
  --red: #D14343;
  --red-soft: rgba(209, 67, 67, 0.08);
  --blue: #3A7FCA;
  --blue-soft: rgba(58, 127, 202, 0.10);
  --purple: #7C5CBF;
  --purple-soft: rgba(124, 92, 191, 0.10);
  --amber: #B8860B;
  --amber-soft: rgba(184, 134, 11, 0.10);
  --teal: #1A8A7A;
  --teal-soft: rgba(26, 138, 122, 0.10);
  --shadow-sm: 0 1px 3px rgba(26,24,21,0.04), 0 1px 2px rgba(26,24,21,0.03);
  --shadow-md: 0 4px 16px rgba(26,24,21,0.06), 0 2px 6px rgba(26,24,21,0.04);
  --shadow-lg: 0 12px 40px rgba(26,24,21,0.10), 0 4px 12px rgba(26,24,21,0.05);
  --shadow-glow: 0 0 0 3px rgba(224, 122, 58, 0.15);
  --radius: 8px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --transition: 160ms cubic-bezier(0.25, 0.1, 0.25, 1);
  --font-display: 'Outfit', sans-serif;
  --font-mono: 'Source Code Pro', monospace;
  --grain-opacity: 0.025;
  --checkbox-border: var(--border-medium);
  --node-line: var(--border-subtle);
}

[data-theme="dark"] {
  --bg-base: #141210;
  --bg-surface: #1C1A17;
  --bg-raised: #242119;
  --bg-hover: #2C2820;
  --bg-active: #352F26;
  --bg-input: #1C1A17;
  --border-subtle: #2C2820;
  --border-medium: #3D3730;
  --border-focus: #E8924E;
  --text-primary: #EDE9E0;
  --text-secondary: #A09888;
  --text-tertiary: #6D6458;
  --text-inverse: #1A1815;
  --accent: #E8924E;
  --accent-hover: #F0A468;
  --accent-soft: rgba(232, 146, 78, 0.12);
  --accent-medium: rgba(232, 146, 78, 0.20);
  --green: #4ADE80;
  --green-soft: rgba(74, 222, 128, 0.10);
  --red: #F87171;
  --red-soft: rgba(248, 113, 113, 0.10);
  --blue: #60A5FA;
  --blue-soft: rgba(96, 165, 250, 0.10);
  --purple: #A78BFA;
  --purple-soft: rgba(167, 139, 250, 0.10);
  --amber: #FBBF24;
  --amber-soft: rgba(251, 191, 36, 0.10);
  --teal: #2DD4BF;
  --teal-soft: rgba(45, 212, 191, 0.10);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.2);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.25);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.35);
  --shadow-glow: 0 0 0 3px rgba(232, 146, 78, 0.20);
  --grain-opacity: 0.04;
  --checkbox-border: var(--text-tertiary);
  --node-line: var(--border-medium);
}

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-display);
  background: var(--bg-base);
  color: var(--text-primary);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  transition: background 300ms ease, color 300ms ease;
}

body::after {
  content: '';
  position: fixed; inset: 0;
  opacity: var(--grain-opacity);
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  pointer-events: none; z-index: 9999;
}

#app { position: relative; z-index: 1; }

.header {
  position: sticky; top: 0; z-index: 100;
  padding: 12px 28px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: flex; align-items: center; justify-content: space-between;
  backdrop-filter: blur(16px);
  transition: background 300ms ease, border 300ms ease;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.logo-mark {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, var(--accent) 0%, #D45A1A 100%);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  box-shadow: 0 2px 8px rgba(224, 122, 58, 0.25);
  transition: transform var(--transition);
}
.logo-mark:hover { transform: scale(1.08) rotate(-4deg); }
.logo-text { font-size: 22px; font-weight: 800; letter-spacing: -0.8px; }
.stat-pills { display: flex; gap: 6px; margin-left: 8px; }
.stat-pill {
  font-family: var(--font-mono); font-size: 11px; font-weight: 500;
  padding: 3px 10px; border-radius: 100px;
  display: flex; align-items: center; gap: 5px;
}
.stat-pill .dot { width: 6px; height: 6px; border-radius: 50%; }
.stat-pending { background: var(--accent-soft); color: var(--accent); }
.stat-pending .dot { background: var(--accent); }
.stat-done { background: var(--green-soft); color: var(--green); }
.stat-done .dot { background: var(--green); }
.stat-folders { background: var(--blue-soft); color: var(--blue); }
.stat-folders .dot { background: var(--blue); }
.header-right { display: flex; align-items: center; gap: 6px; }

.theme-toggle {
  width: 52px; height: 28px;
  background: var(--bg-raised); border: 1px solid var(--border-subtle);
  border-radius: 100px; cursor: pointer; position: relative;
  transition: all var(--transition);
}
.theme-toggle:hover { border-color: var(--border-medium); }
.theme-toggle::after {
  content: '☀️'; font-size: 14px;
  position: absolute; top: 3px; left: 4px;
  width: 20px; height: 20px;
  background: var(--bg-surface); border-radius: 50%;
  box-shadow: var(--shadow-sm);
  transition: transform 300ms cubic-bezier(0.68, -0.3, 0.32, 1.3);
  display: flex; align-items: center; justify-content: center; line-height: 1;
}
[data-theme="dark"] .theme-toggle::after { content: '🌙'; transform: translateX(23px); }

.btn {
  font-family: var(--font-display); font-size: 13px; font-weight: 600;
  padding: 7px 14px; border-radius: var(--radius);
  border: 1px solid var(--border-subtle); background: var(--bg-surface);
  color: var(--text-secondary); cursor: pointer;
  transition: all var(--transition);
  display: inline-flex; align-items: center; gap: 5px;
  white-space: nowrap; user-select: none;
}
.btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--border-medium); }
.btn:active { transform: scale(0.97); }
.btn-primary { background: var(--accent); border-color: var(--accent); color: var(--text-inverse); box-shadow: 0 1px 4px rgba(224,122,58,0.25); }
.btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); color: var(--text-inverse); }
.btn-ghost { border: none; background: transparent; padding: 6px 8px; color: var(--text-tertiary); }
.btn-ghost:hover { color: var(--text-primary); background: var(--bg-hover); border: none; }
.btn-danger { color: var(--red); }
.btn-danger:hover { background: var(--red-soft); border-color: transparent; }
.btn-icon {
  width: 28px; height: 28px; padding: 0;
  border: none; background: transparent; color: var(--text-tertiary);
  cursor: pointer; border-radius: 6px;
  transition: all var(--transition); font-size: 14px;
  display: inline-flex; align-items: center; justify-content: center;
}
.btn-icon:hover { color: var(--text-primary); background: var(--bg-hover); }
.btn-icon.danger:hover { color: var(--red); background: var(--red-soft); }

.toolbar {
  padding: 10px 28px; display: flex; align-items: center; gap: 8px;
  background: var(--bg-surface); border-bottom: 1px solid var(--border-subtle);
}
.search-wrap { flex: 1; max-width: 420px; position: relative; }
.search-wrap .si {
  position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
  color: var(--text-tertiary); pointer-events: none; font-size: 14px;
}
.search-wrap input {
  width: 100%; padding: 9px 12px 9px 36px;
  background: var(--bg-raised); border: 1px solid transparent;
  border-radius: var(--radius); color: var(--text-primary);
  font-family: var(--font-display); font-size: 14px;
  outline: none; transition: all var(--transition);
}
.search-wrap input::placeholder { color: var(--text-tertiary); }
.search-wrap input:focus { background: var(--bg-input); border-color: var(--border-focus); box-shadow: var(--shadow-glow); }

.tree-container { padding: 20px 28px 140px; max-width: 860px; margin: 0 auto; }
.tree-node { margin-bottom: 1px; }
.node-header {
  display: flex; align-items: center; gap: 2px;
  padding: 7px 10px; border-radius: var(--radius);
  cursor: pointer; transition: all var(--transition); user-select: none;
}
.node-header:hover { background: var(--bg-hover); }
.node-header:hover .node-actions { opacity: 1; pointer-events: auto; }
.node-chevron {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary); transition: transform var(--transition), background var(--transition), color var(--transition);
  flex-shrink: 0; font-size: 16px; font-weight: 700; border-radius: 6px;
}
.node-chevron:hover { background: var(--accent-soft); color: var(--accent); }
.node-chevron.open { transform: rotate(90deg); }
.node-icon { font-size: 16px; flex-shrink: 0; margin-right: 4px; }
.node-label { font-size: 14px; font-weight: 600; flex: 1; letter-spacing: -0.2px; }
.node-badge {
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 100px;
  background: var(--bg-raised); color: var(--text-tertiary); border: 1px solid var(--border-subtle);
}
.node-actions { display: flex; gap: 1px; opacity: 0; pointer-events: none; transition: opacity var(--transition); }
.node-children {
  margin-left: 16px; padding-left: 14px;
  border-left: 1.5px solid var(--node-line);
}

.item-list { margin-left: 4px; }
.item {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; border-radius: var(--radius);
  transition: all var(--transition); margin: 1px 0;
}
.item:hover { background: var(--bg-hover); }
.item:hover .item-actions { opacity: 1; pointer-events: auto; }
.checkbox {
  width: 18px; height: 18px;
  border: 2px solid var(--checkbox-border); border-radius: 5px;
  cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  transition: all var(--transition);
}
.checkbox:hover { border-color: var(--accent); }
.checkbox.checked { background: var(--green); border-color: var(--green); }
.checkbox.checked::after {
  content: ''; width: 5px; height: 9px;
  border: solid white; border-width: 0 2px 2px 0;
  transform: rotate(45deg); margin-top: -2px;
}
.item-id { font-family: var(--font-mono); font-size: 10px; color: var(--text-tertiary); min-width: 20px; }
.item-text { font-size: 14px; flex: 1; color: var(--text-primary); line-height: 1.45; }
.item.done .item-text { text-decoration: line-through; text-decoration-color: var(--text-tertiary); color: var(--text-tertiary); }
.item-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag { font-family: var(--font-mono); font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 5px; letter-spacing: 0.4px; }
.tag-URGENT, .tag-ASAP, .tag-CRITICAL { background: var(--red-soft); color: var(--red); }
.tag-HABIT, .tag-WEEKLY, .tag-DAILY { background: var(--teal-soft); color: var(--teal); }
.tag-GOAL, .tag-MILESTONE { background: var(--purple-soft); color: var(--purple); }
.tag-default { background: var(--amber-soft); color: var(--amber); }
mark.hl { background: var(--accent-medium); color: var(--accent); padding: 1px 3px; border-radius: 3px; font-weight: 600; }
.search-hit { scroll-margin-top: 120px; }
.search-hit.active { background: var(--accent-soft); outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius); }
.search-nav { display: flex; align-items: center; gap: 4px; font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); }
.search-nav .count { min-width: 60px; text-align: center; padding: 0 6px; }
.item-actions { display: flex; gap: 1px; opacity: 0; pointer-events: none; transition: opacity var(--transition); }

.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(26,24,21,0.4); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; animation: fadeIn 120ms ease;
}
[data-theme="dark"] .modal-overlay { background: rgba(0,0,0,0.55); }
.modal {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl); padding: 28px;
  min-width: 420px; max-width: 520px; box-shadow: var(--shadow-lg);
  animation: modalIn 250ms cubic-bezier(0.34,1.56,0.64,1);
}
.modal-title { font-size: 17px; font-weight: 700; margin-bottom: 18px; letter-spacing: -0.3px; display: flex; align-items: center; gap: 8px; }
.modal-path { font-family: var(--font-mono); font-size: 12px; font-weight: 500; color: var(--accent); padding: 8px 12px; background: var(--accent-soft); border-radius: var(--radius); margin-bottom: 16px; }
.modal label { font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; display: block; letter-spacing: 0.3px; text-transform: uppercase; }
.modal input, .modal select {
  width: 100%; padding: 11px 14px;
  background: var(--bg-raised); border: 1.5px solid var(--border-subtle);
  border-radius: var(--radius); color: var(--text-primary);
  font-family: var(--font-display); font-size: 14px;
  outline: none; margin-bottom: 14px;
}
.modal input:focus, .modal select:focus { border-color: var(--border-focus); box-shadow: var(--shadow-glow); background: var(--bg-input); }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
.confirm-msg { font-size: 14px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.6; }

.empty { text-align: center; padding: 100px 20px 60px; }
.empty-icon { font-size: 56px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
.empty h3 { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
.empty p { color: var(--text-tertiary); font-size: 15px; margin-bottom: 24px; }

.toast-wrap { position: fixed; bottom: 28px; right: 28px; z-index: 2000; display: flex; flex-direction: column; gap: 8px; }
.toast { padding: 11px 18px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); font-size: 13px; font-weight: 500; box-shadow: var(--shadow-md); animation: toastIn 300ms cubic-bezier(0.34,1.56,0.64,1); display: flex; align-items: center; gap: 8px; }
.toast.success { border-left: 3px solid var(--green); }
.toast.error { border-left: 3px solid var(--red); }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes modalIn { from { transform: translateY(12px) scale(0.96); opacity: 0; } to { transform: translateY(0) scale(1); opacity: 1; } }
@keyframes toastIn { from { transform: translateX(30px) scale(0.9); opacity: 0; } to { transform: translateX(0) scale(1); opacity: 1; } }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes stagger-in { from { transform: translateY(8px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.tree-node { animation: stagger-in 200ms ease both; }

@media (max-width: 640px) {
  .header { padding: 10px 16px; }
  .toolbar { padding: 8px 16px; }
  .tree-container { padding: 14px 14px 120px; }
  .stat-pills { display: none; }
  .modal { min-width: auto; margin: 16px; }
  .node-actions, .item-actions { opacity: 1; pointer-events: auto; }
}
</style>
</head>
<body>
<div id="app"></div>
<script>
const API_KEY = new URLSearchParams(location.search).get('key') || '';
let todoData = { nodes: {} };
let expandedNodes = new Set();
let searchQuery = '';
let searchIndex = 0;
let modal = null;
let toasts = [];
let toastId = 0;
let theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
const saved = window.name;
if (saved === 'dark' || saved === 'light') theme = saved;
document.documentElement.setAttribute('data-theme', theme);

function toggleTheme() {
  theme = theme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  window.name = theme;
  render();
}

async function api(endpoint, body = null) {
  const opts = { headers: { 'Content-Type': 'application/json' } };
  if (body) { opts.method = 'POST'; opts.body = JSON.stringify(body); }
  const sep = endpoint.includes('?') ? '&' : '?';
  const res = await fetch(endpoint + sep + 'key=' + encodeURIComponent(API_KEY), opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

async function loadTodos() {
  try { todoData = await api('/api/todos'); render(); }
  catch (e) { toast('Failed to load: ' + e.message, 'error'); }
}

function toast(msg, type) {
  type = type || 'success';
  const id = ++toastId;
  toasts.push({ id: id, msg: msg, type: type }); render();
  setTimeout(function() { toasts = toasts.filter(function(t) { return t.id !== id; }); render(); }, 3000);
}

function countItems(node) {
  var total = 0, done = 0;
  (node.items || []).forEach(function(i) { total++; if (i.done) done++; });
  var kids = node.children || {};
  Object.keys(kids).forEach(function(k) {
    var r = countItems(kids[k]); total += r.total; done += r.done;
  });
  return { total: total, done: done };
}

function getTotalStats() {
  var total = 0, done = 0, nodes = 0;
  function walk(obj) {
    Object.keys(obj).forEach(function(k) {
      var node = obj[k];
      nodes++;
      (node.items || []).forEach(function(i) { total++; if (i.done) done++; });
      if (node.children) walk(node.children);
    });
  }
  walk(todoData.nodes || {});
  return { total: total, done: done, pending: total - done, nodes: nodes };
}

function extractTags(text) { return text.match(/\b[A-Z][A-Z0-9]{1,9}\b/g) || []; }
function matchesSearch(text) { return !searchQuery || text.toLowerCase().indexOf(searchQuery.toLowerCase()) !== -1; }
function nodeMatchesSearch(node, name) {
  if (matchesSearch(name)) return true;
  if ((node.items || []).some(function(i) { return matchesSearch(i.text); })) return true;
  var kids = node.children || {};
  return Object.keys(kids).some(function(n) { return nodeMatchesSearch(kids[n], n); });
}
function highlightMatch(text) {
  if (!searchQuery) return esc(text);
  var escaped = esc(text);
  var q = esc(searchQuery).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(new RegExp('(' + q + ')', 'gi'), '<mark class="hl">$1</mark>');
}
function autoExpandForSearch() {
  if (!searchQuery) return;
  function walk(nodes, path) {
    Object.keys(nodes).forEach(function(name) {
      var node = nodes[name];
      var p = path.concat([name]);
      if (nodeMatchesSearch(node, name)) {
        for (var i = 1; i <= p.length; i++) {
          expandedNodes.add(pathKey(p.slice(0, i)));
        }
      }
      if (node.children) walk(node.children, p);
    });
  }
  walk(todoData.nodes || {}, []);
}

function scrollToHit(idx) {
  var hits = document.querySelectorAll('.search-hit');
  if (!hits.length) return;
  hits.forEach(function(h) { h.classList.remove('active'); });
  searchIndex = ((idx % hits.length) + hits.length) % hits.length;
  var el = hits[searchIndex];
  el.classList.add('active');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  var counter = document.getElementById('search-counter');
  if (counter) counter.textContent = (searchIndex + 1) + ' / ' + hits.length;
}
function findNext() { scrollToHit(searchIndex + 1); }
function findPrev() { scrollToHit(searchIndex - 1); }
function onSearchInput(val) {
  searchQuery = val;
  searchIndex = 0;
  render();
  setTimeout(function() { if (searchQuery) scrollToHit(0); }, 50);
}
function pathKey(p) { return p.join('\x00'); }

function toggleNode(path) {
  var k = pathKey(path);
  if (expandedNodes.has(k)) expandedNodes.delete(k);
  else expandedNodes.add(k);
  render();
}

function expandAll() {
  function walk(nodes, path) {
    Object.keys(nodes).forEach(function(name) {
      var node = nodes[name];
      var p = path.concat([name]);
      expandedNodes.add(pathKey(p));
      if (node.children) walk(node.children, p);
    });
  }
  walk(todoData.nodes || {}, []);
  render();
}

function collapseAll() { expandedNodes.clear(); render(); }

function expandBranch(path) {
  console.log('[TodoTree] expandBranch', JSON.stringify(path));
  function walkFrom(nodes, curPath) {
    Object.keys(nodes).forEach(function(name) {
      var node = nodes[name];
      var p = curPath.concat([name]);
      expandedNodes.add(pathKey(p));
      if (node.children) walkFrom(node.children, p);
    });
  }
  // Add this node
  expandedNodes.add(pathKey(path));
  // Navigate to the target node
  var current = todoData.nodes;
  var node = null;
  for (var i = 0; i < path.length; i++) {
    node = current[path[i]];
    if (!node) { console.log('[TodoTree] node not found at', path[i]); break; }
    if (i < path.length - 1) {
      current = node.children || {};
    }
  }
  // Expand all children
  if (node && node.children) walkFrom(node.children, path);
  console.log('[TodoTree] expanded set size:', expandedNodes.size);
  render();
}

function collapseBranch(path) {
  console.log('[TodoTree] collapseBranch', JSON.stringify(path));
  var prefix = pathKey(path);
  var toRemove = [];
  expandedNodes.forEach(function(k) {
    if (k === prefix || k.indexOf(prefix + '\x00') === 0) toRemove.push(k);
  });
  toRemove.forEach(function(k) { expandedNodes.delete(k); });
  console.log('[TodoTree] expanded set size after collapse:', expandedNodes.size);
  render();
}

async function addItem(path, text) {
  if (!text.trim()) return;
  try { await api('/api/item/add', { path: path, text: text.trim() }); toast('Item added'); expandedNodes.add(pathKey(path)); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function editItem(path, itemId, updates) {
  try { await api('/api/item/edit', Object.assign({ path: path, item_id: itemId }, updates)); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function deleteItem(path, itemId) {
  try { await api('/api/item/delete', { path: path, item_id: itemId }); toast('Deleted'); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function toggleDone(path, item) { await editItem(path, item.id, { done: !item.done }); }
async function addNode(parentPath, name) {
  if (!name.trim()) return;
  try { await api('/api/node/add', { path: parentPath, name: name.trim() }); toast('Folder created'); if (parentPath.length) expandedNodes.add(pathKey(parentPath)); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function deleteNode(path) {
  try { await api('/api/node/delete', { path: path }); toast('Folder deleted'); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function renameNode(path, newName) {
  if (!newName.trim()) return;
  try { await api('/api/node/rename', { path: path, new_name: newName.trim() }); toast('Renamed'); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}
async function moveItem(fromPath, itemId, toPath) {
  try { await api('/api/item/move', { from_path: fromPath, item_id: itemId, to_path: toPath }); toast('Moved'); await loadTodos(); }
  catch (e) { toast(e.message, 'error'); }
}

function showModal(type, props) {
  modal = { type: type, props: props || {} }; render();
  setTimeout(function() { var el = document.querySelector('.modal input, .modal select'); if (el) el.focus(); }, 60);
}
function closeModal() { modal = null; render(); }

function downloadBackup() {
  var json = JSON.stringify(todoData, null, 2);
  var blob = new Blob([json], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'todos-backup-' + new Date().toISOString().slice(0,10) + '.json';
  a.click();
  URL.revokeObjectURL(url);
  toast('Backup downloaded');
}

function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function renderTags(text) {
  var tags = extractTags(text);
  if (!tags.length) return '';
  return '<div class="item-tags">' + tags.map(function(t) {
    var special = ['URGENT','ASAP','CRITICAL','HABIT','WEEKLY','DAILY','GOAL','MILESTONE'].indexOf(t) !== -1;
    return '<span class="tag ' + (special ? 'tag-'+t : 'tag-default') + '">' + t + '</span>';
  }).join('') + '</div>';
}

function renderItem(item, path) {
  var jp = JSON.stringify(path), ji = JSON.stringify(item);
  var isHit = searchQuery && matchesSearch(item.text);
  return '<div class="item ' + (item.done?'done':'') + ' ' + (isHit?'search-hit':'') + '">' +
    '<div class="checkbox ' + (item.done?'checked':'') + '" onclick="event.stopPropagation();toggleDone(' + jp + ',' + ji + ')"></div>' +
    '<span class="item-id">#' + item.id + '</span>' +
    '<span class="item-text">' + highlightMatch(item.text) + '</span>' +
    renderTags(item.text) +
    '<div class="item-actions">' +
      '<button class="btn-icon" onclick="event.stopPropagation();showModal(\'editItem\',{path:' + jp + ',item:' + ji + '})" title="Edit">✎</button>' +
      '<button class="btn-icon" onclick="event.stopPropagation();showModal(\'moveItem\',{path:' + jp + ',item:' + ji + '})" title="Move">↗</button>' +
      '<button class="btn-icon danger" onclick="event.stopPropagation();showModal(\'confirm\',{msg:\'Delete item #' + item.id + '?\',action:\'deleteItem\',args:[' + jp + ',' + item.id + ']})" title="Delete">×</button>' +
    '</div>' +
  '</div>';
}

function renderNode(name, node, parentPath) {
  var path = parentPath.concat([name]);
  var pk = pathKey(path);
  var isOpen = expandedNodes.has(pk);
  var ci = countItems(node);
  var total = ci.total, done = ci.done;
  var hasKids = node.children && Object.keys(node.children).length > 0;
  var hasItems = node.items && node.items.length > 0;
  var hasContent = hasKids || hasItems;

  if (searchQuery && !nodeMatchesSearch(node, name)) return '';

  var jp = JSON.stringify(path);
  var childKeys = Object.keys(node.children || {}).sort();
  var children = childKeys.map(function(n) { return renderNode(n, node.children[n], path); }).join('');
  var filteredItems = (node.items || []).filter(function(i) { return !searchQuery || matchesSearch(i.text); });
  var items = filteredItems.map(function(i) { return renderItem(i, path); }).join('');
  var nameIsHit = searchQuery && matchesSearch(name);

  // Key fix: each action button gets its own event.stopPropagation()
  var expandBtn = '';
  if (hasContent) {
    if (isOpen) {
      expandBtn = '<button class="btn-icon" onclick="event.stopPropagation();collapseBranch(' + jp + ')" title="Collapse branch">⊟</button>';
    } else {
      expandBtn = '<button class="btn-icon" onclick="event.stopPropagation();expandBranch(' + jp + ')" title="Expand branch">⊞</button>';
    }
  }

  var html = '<div class="tree-node">' +
    '<div class="node-header ' + (nameIsHit ? 'search-hit' : '') + '" onclick="toggleNode(' + jp + ')">' +
      '<div class="node-chevron ' + (isOpen ? 'open' : '') + '">▸</div>' +
      '<span class="node-icon">' + (hasContent ? (isOpen ? '📂' : '📁') : '📄') + '</span>' +
      '<span class="node-label">' + highlightMatch(name) + '</span>' +
      (total > 0 ? '<span class="node-badge">' + done + '/' + total + '</span>' : '') +
      '<div class="node-actions" onclick="event.stopPropagation()">' +
        expandBtn +
        '<button class="btn-icon" onclick="event.stopPropagation();showModal(\'addItem\',{path:' + jp + '})" title="Add item">+</button>' +
        '<button class="btn-icon" onclick="event.stopPropagation();showModal(\'addFolder\',{path:' + jp + '})" title="Subfolder">📁</button>' +
        '<button class="btn-icon" onclick="event.stopPropagation();showModal(\'renameNode\',{path:' + jp + ',name:\'' + esc(name).replace(/'/g, "\\'") + '\'})" title="Rename">✎</button>' +
        '<button class="btn-icon danger" onclick="event.stopPropagation();showModal(\'confirm\',{msg:\'Delete \\x27' + esc(name).replace(/'/g, "\\'") + '\\x27 and all contents?\',action:\'deleteNode\',args:[' + jp + ']})" title="Delete">×</button>' +
      '</div>' +
    '</div>' +
    (isOpen ? '<div class="node-children"><div class="item-list">' + items + '</div>' + children + '</div>' : '') +
  '</div>';

  return html;
}

function renderModal() {
  if (!modal) return '';
  var type = modal.type, props = modal.props;
  if (type === 'addItem') {
    var jp = JSON.stringify(props.path);
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">✦ New Item</div>' +
      '<div class="modal-path">📍 ' + esc(props.path.join(' › ')) + '</div>' +
      '<label>Description</label>' +
      '<input id="mi" placeholder="e.g. URGENT review PR #42" onkeydown="if(event.key===\'Enter\'){addItem(' + jp + ',this.value);closeModal();}">' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="addItem(' + jp + ',document.getElementById(\'mi\').value);closeModal();">Add Item</button></div>' +
    '</div></div>';
  }
  if (type === 'editItem') {
    var jp = JSON.stringify(props.path);
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">✎ Edit Item</div>' +
      '<div class="modal-path">📍 ' + esc(props.path.join(' › ')) + '</div>' +
      '<label>Description</label>' +
      '<input id="mi" value="' + esc(props.item.text) + '" onkeydown="if(event.key===\'Enter\'){editItem(' + jp + ',' + props.item.id + ',{text:this.value});closeModal();}">' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="editItem(' + jp + ',' + props.item.id + ',{text:document.getElementById(\'mi\').value});closeModal();">Save</button></div>' +
    '</div></div>';
  }
  if (type === 'addFolder') {
    var jp = JSON.stringify(props.path);
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">📁 New Folder</div>' +
      '<div class="modal-path">📍 ' + (props.path.length ? esc(props.path.join(' › ')) : 'Root level') + '</div>' +
      '<label>Folder name</label>' +
      '<input id="mi" placeholder="e.g. Finance" onkeydown="if(event.key===\'Enter\'){addNode(' + jp + ',this.value);closeModal();}">' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="addNode(' + jp + ',document.getElementById(\'mi\').value);closeModal();">Create</button></div>' +
    '</div></div>';
  }
  if (type === 'addRootFolder') {
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">📁 New Root Folder</div>' +
      '<label>Folder name</label>' +
      '<input id="mi" placeholder="e.g. Personal" onkeydown="if(event.key===\'Enter\'){addNode([],this.value);closeModal();}">' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="addNode([],document.getElementById(\'mi\').value);closeModal();">Create</button></div>' +
    '</div></div>';
  }
  if (type === 'renameNode') {
    var jp = JSON.stringify(props.path);
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">✎ Rename Folder</div>' +
      '<label>New name</label>' +
      '<input id="mi" value="' + esc(props.name) + '" onkeydown="if(event.key===\'Enter\'){renameNode(' + jp + ',this.value);closeModal();}">' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="renameNode(' + jp + ',document.getElementById(\'mi\').value);closeModal();">Rename</button></div>' +
    '</div></div>';
  }
  if (type === 'moveItem') {
    var paths = [];
    function collect(nodes, p) {
      Object.keys(nodes).forEach(function(name) {
        var fp = p.concat([name]); paths.push(fp);
        if (nodes[name].children) collect(nodes[name].children, fp);
      });
    }
    collect(todoData.nodes || {}, []);
    var jp = JSON.stringify(props.path);
    var opts = paths.map(function(p) {
      return '<option value=\'' + JSON.stringify(p) + '\'' + (pathKey(p)===pathKey(props.path) ? ' selected' : '') + '>' + esc(p.join(' › ')) + '</option>';
    }).join('');
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">↗ Move Item</div>' +
      '<p style="font-size:13px;color:var(--text-secondary);margin-bottom:14px;">Moving: "' + esc(props.item.text) + '"</p>' +
      '<label>Destination</label>' +
      '<select id="md">' + opts + '</select>' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="moveItem(' + jp + ',' + props.item.id + ',JSON.parse(document.getElementById(\'md\').value));closeModal();">Move</button></div>' +
    '</div></div>';
  }
  if (type === 'confirm') {
    return '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal">' +
      '<div class="modal-title">⚠ Confirm</div>' +
      '<p class="confirm-msg">' + esc(props.msg) + '</p>' +
      '<div class="modal-footer"><button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-danger" onclick="' + props.action + '(' + props.args.map(function(a) { return JSON.stringify(a); }).join(',') + ');closeModal();">Delete</button></div>' +
    '</div></div>';
  }
  return '';
}

function render() {
  autoExpandForSearch();
  var s = getTotalStats();
  var nodeKeys = Object.keys(todoData.nodes || {}).sort();
  var tree = nodeKeys.map(function(n) { return renderNode(n, todoData.nodes[n], []); }).join('');

  document.getElementById('app').innerHTML =
    '<div class="header">' +
      '<div class="header-left">' +
        '<div class="logo-mark">🌳</div>' +
        '<span class="logo-text">TodoTree</span>' +
        '<div class="stat-pills">' +
          '<span class="stat-pill stat-pending"><span class="dot"></span>' + s.pending + ' open</span>' +
          '<span class="stat-pill stat-done"><span class="dot"></span>' + s.done + ' done</span>' +
          '<span class="stat-pill stat-folders"><span class="dot"></span>' + s.nodes + ' folders</span>' +
        '</div>' +
      '</div>' +
      '<div class="header-right">' +
        '<div class="theme-toggle" onclick="toggleTheme()" title="Toggle theme"></div>' +
        '<button class="btn" onclick="downloadBackup()" title="Download backup">⬇ Backup</button>' +
        '<button class="btn" onclick="expandAll()">⊞ Expand</button>' +
        '<button class="btn" onclick="collapseAll()">⊟ Collapse</button>' +
        '<button class="btn btn-primary" onclick="showModal(\'addRootFolder\')">+ Folder</button>' +
      '</div>' +
    '</div>' +
    '<div class="toolbar">' +
      '<div class="search-wrap">' +
        '<span class="si">🔍</span>' +
        '<input placeholder="Search items and folders..." value="' + esc(searchQuery) + '" oninput="onSearchInput(this.value)" onkeydown="if(event.key===\'Enter\'){event.shiftKey?findPrev():findNext();}">' +
      '</div>' +
      (searchQuery ? '<div class="search-nav">' +
        '<button class="btn btn-ghost" onclick="findPrev()" title="Previous">▲</button>' +
        '<span class="count" id="search-counter">–</span>' +
        '<button class="btn btn-ghost" onclick="findNext()" title="Next">▼</button>' +
      '</div>' : '') +
      '<button class="btn btn-ghost" onclick="loadTodos()">↻ Refresh</button>' +
    '</div>' +
    '<div class="tree-container">' +
      (tree || '<div class="empty"><div class="empty-icon">🌱</div><h3>Your tree is empty</h3><p>Create a root folder to start organizing</p><button class="btn btn-primary" onclick="showModal(\'addRootFolder\')">+ Create Folder</button></div>') +
    '</div>' +
    renderModal() +
    '<div class="toast-wrap">' + toasts.map(function(t) { return '<div class="toast ' + t.type + '">' + (t.type==='success'?'✓':'✗') + ' ' + esc(t.msg) + '</div>'; }).join('') + '</div>';

  if (searchQuery) {
    var inp = document.querySelector('.search-wrap input');
    if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
    var hits = document.querySelectorAll('.search-hit');
    var counter = document.getElementById('search-counter');
    if (counter) counter.textContent = hits.length ? (Math.min(searchIndex+1, hits.length) + ' / ' + hits.length) : '0';
  }
}

loadTodos();
</script>
</body>
</html>""";

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TodoTree</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Outfit', sans-serif; min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #FAFAF8; color: #1A1815;
}
@media (prefers-color-scheme: dark) {
  body { background: #141210; color: #EDE9E0; }
  .card { background: #1C1A17; border-color: #2C2820; }
  input { background: #242119; border-color: #3D3730; color: #EDE9E0; }
  input:focus { border-color: #E8924E; box-shadow: 0 0 0 3px rgba(232,146,78,0.2); }
  button { background: #E8924E; }
  button:hover { background: #F0A468; }
  .sub { color: #6D6458; }
}
.card {
  background: #fff; border: 1px solid #E5E3DB; border-radius: 20px;
  padding: 44px; width: 380px; text-align: center;
  box-shadow: 0 12px 40px rgba(26,24,21,0.06);
}
.icon { font-size: 44px; margin-bottom: 16px; }
h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.8px; margin-bottom: 6px; }
.sub { color: #9C9790; font-size: 14px; margin-bottom: 28px; }
input {
  width: 100%; padding: 13px 16px; border: 1.5px solid #E5E3DB;
  border-radius: 10px; font-family: 'Outfit'; font-size: 15px;
  outline: none; margin-bottom: 14px; transition: all 160ms ease;
  text-align: center; letter-spacing: 2px;
}
input:focus { border-color: #E07A3A; box-shadow: 0 0 0 3px rgba(224,122,58,0.15); }
button {
  width: 100%; padding: 13px; background: #E07A3A; border: none;
  border-radius: 10px; color: white; font-family: 'Outfit';
  font-size: 15px; font-weight: 600; cursor: pointer; transition: all 160ms ease;
}
button:hover { background: #CC6A2E; transform: translateY(-1px); }
button:active { transform: scale(0.98); }
</style></head><body>
<div class="card">
  <div class="icon">🔐</div>
  <h1>TodoTree</h1>
  <p class="sub">Enter your access key to continue</p>
  <input id="k" type="password" placeholder="••••••••" autofocus onkeydown="if(event.key==='Enter')go()">
  <button onclick="go()">Unlock</button>
</div>
<script>function go(){var k=document.getElementById('k').value;if(k)location.href='/?key='+encodeURIComponent(k);}</script>
</body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index(key: str = Query(default="")):
    if not key or key != SECRET_KEY:
        return HTMLResponse(content=LOGIN_HTML)
    return HTMLResponse(content=FRONTEND_HTML)


if __name__ == "__main__":
    port = int(os.environ.get("TODO_PORT", "8081"))
    print(f"\n  🌳 TodoTree")
    print(f"  ───────────────────────────")
    print(f"  File:   {TODO_FILE}")
    print(f"  Port:   {port}")
    print(f"  URL:    http://100.77.66.80:{port}?key={SECRET_KEY}")
    print(f"  ───────────────────────────\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")