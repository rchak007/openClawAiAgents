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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# ─── Config ───────────────────────────────────────────────────────────────────

TODO_FILE = os.environ.get("TODO_FILE", os.path.expanduser("~/.openclaw/workspace/todos.json"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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
        shutil.copy2(TODO_FILE, os.path.join(backup_dir, f"todos_backup_{ts}.json"))
        for old in sorted(Path(backup_dir).glob("todos_backup_*.json"))[:-5]:
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
    return max((item.get("id", 0) for item in items), default=0) + 1

# ─── API Models ───────────────────────────────────────────────────────────────

class AddItemReq(BaseModel):
    path: list[str]
    text: str

class EditItemReq(BaseModel):
    path: list[str]
    item_id: int
    text: Optional[str] = None
    done: Optional[bool] = None

class DeleteItemReq(BaseModel):
    path: list[str]
    item_id: int

class AddNodeReq(BaseModel):
    path: list[str]
    name: str

class DeleteNodeReq(BaseModel):
    path: list[str]

class RenameNodeReq(BaseModel):
    path: list[str]
    new_name: str

class MoveItemReq(BaseModel):
    from_path: list[str]
    item_id: int
    to_path: list[str]

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/todos")
async def api_get_todos(key: str = Depends(verify_key)):
    return load_todos()

@app.post("/api/item/add")
async def api_add_item(req: AddItemReq, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    if "items" not in node: node["items"] = []
    item = {"id": get_next_id(node), "text": req.text, "done": False, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    node["items"].append(item)
    save_todos(data)
    return {"ok": True, "item": item}

@app.post("/api/item/edit")
async def api_edit_item(req: EditItemReq, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    for item in node.get("items", []):
        if item["id"] == req.item_id:
            if req.text is not None: item["text"] = req.text
            if req.done is not None: item["done"] = req.done
            save_todos(data)
            return {"ok": True, "item": item}
    raise HTTPException(404, "Item not found")

@app.post("/api/item/delete")
async def api_delete_item(req: DeleteItemReq, key: str = Depends(verify_key)):
    data = load_todos()
    node = get_node_at_path(data["nodes"], req.path)
    node["items"] = [i for i in node.get("items", []) if i["id"] != req.item_id]
    save_todos(data)
    return {"ok": True}

@app.post("/api/item/move")
async def api_move_item(req: MoveItemReq, key: str = Depends(verify_key)):
    data = load_todos()
    src = get_node_at_path(data["nodes"], req.from_path)
    moved = None
    for i, item in enumerate(src.get("items", [])):
        if item["id"] == req.item_id:
            moved = src["items"].pop(i)
            break
    if not moved: raise HTTPException(404, "Item not found")
    dst = get_node_at_path(data["nodes"], req.to_path)
    if "items" not in dst: dst["items"] = []
    moved["id"] = get_next_id(dst)
    dst["items"].append(moved)
    save_todos(data)
    return {"ok": True, "item": moved}

@app.post("/api/node/add")
async def api_add_node(req: AddNodeReq, key: str = Depends(verify_key)):
    data = load_todos()
    if not req.path:
        data["nodes"].setdefault(req.name, {})
    else:
        parent = get_node_at_path(data["nodes"], req.path)
        parent.setdefault("children", {}).setdefault(req.name, {})
    save_todos(data)
    return {"ok": True}

@app.post("/api/node/delete")
async def api_delete_node(req: DeleteNodeReq, key: str = Depends(verify_key)):
    data = load_todos()
    if len(req.path) == 1:
        data["nodes"].pop(req.path[0], None)
    else:
        parent = get_node_at_path(data["nodes"], req.path[:-1])
        parent.get("children", {}).pop(req.path[-1], None)
    save_todos(data)
    return {"ok": True}

@app.post("/api/node/rename")
async def api_rename_node(req: RenameNodeReq, key: str = Depends(verify_key)):
    data = load_todos()
    old = req.path[-1]
    if len(req.path) == 1:
        if old in data["nodes"]: data["nodes"][req.new_name] = data["nodes"].pop(old)
    else:
        parent = get_node_at_path(data["nodes"], req.path[:-1])
        ch = parent.get("children", {})
        if old in ch: ch[req.new_name] = ch.pop(old)
    save_todos(data)
    return {"ok": True}

# ─── Frontend ─────────────────────────────────────────────────────────────────

LOGIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TodoTree</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#FAFAF8;color:#1A1815}
@media(prefers-color-scheme:dark){body{background:#141210;color:#EDE9E0}.card{background:#1C1A17;border-color:#2C2820}input{background:#242119;border-color:#3D3730;color:#EDE9E0}input:focus{border-color:#E8924E;box-shadow:0 0 0 3px rgba(232,146,78,0.2)}button{background:#E8924E}button:hover{background:#F0A468}.sub{color:#6D6458}}
.card{background:#fff;border:1px solid #E5E3DB;border-radius:20px;padding:44px;width:380px;text-align:center;box-shadow:0 12px 40px rgba(26,24,21,0.06)}
.icon{font-size:44px;margin-bottom:16px}h1{font-size:24px;font-weight:800;letter-spacing:-0.8px;margin-bottom:6px}
.sub{color:#9C9790;font-size:14px;margin-bottom:28px}
input{width:100%;padding:13px 16px;border:1.5px solid #E5E3DB;border-radius:10px;font-family:'Outfit';font-size:15px;outline:none;margin-bottom:14px;text-align:center;letter-spacing:2px}
input:focus{border-color:#E07A3A;box-shadow:0 0 0 3px rgba(224,122,58,0.15)}
button{width:100%;padding:13px;background:#E07A3A;border:none;border-radius:10px;color:white;font-family:'Outfit';font-size:15px;font-weight:600;cursor:pointer}
button:hover{background:#CC6A2E;transform:translateY(-1px)}</style></head><body>
<div class="card"><div class="icon">🔐</div><h1>TodoTree</h1><p class="sub">Enter your access key</p>
<input id="k" type="password" placeholder="••••••••" autofocus onkeydown="if(event.key==='Enter')go()">
<button onclick="go()">Unlock</button></div>
<script>function go(){var k=document.getElementById('k').value;if(k)location.href='/?key='+encodeURIComponent(k);}</script>
</body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index(key: str = Query(default="")):
    if not key or key != SECRET_KEY:
        return HTMLResponse(content=LOGIN_PAGE)
    html_path = os.path.join(SCRIPT_DIR, "todo_tree.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    port = int(os.environ.get("TODO_PORT", "8081"))
    print(f"\n  🌳 TodoTree")
    print(f"  ───────────────────────────")
    print(f"  File:   {TODO_FILE}")
    print(f"  Port:   {port}")
    print(f"  URL:    http://100.77.66.80:{port}?key={SECRET_KEY}")
    print(f"  ───────────────────────────\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")