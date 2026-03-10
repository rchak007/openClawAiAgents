#!/usr/bin/env python3
"""
eternalquest-todo.py — Fluid unlimited-depth tree todo manager
Used by OpenClaw's eternalquest skill (EternalQuest_bot).

Data file: ~/.openclaw/workspace/eternalquest-todos.json
(Separate from the main todos.json and realestate data)

Commands:
  add   "node1/node2/node3"  "item text"   — add item, auto-create path
  list                                      — full tree with items
  tree                                      — just node names (no items)
  show  "node1/node2"                       — list subtree at path
  find  "TAG"  ["node1/node2"]              — search by tag, optional path filter
  done  "node1/node2"  <id>                 — mark item done
  undone "node1/node2" <id>                 — unmark item
  clear                                     — remove all done items
  delete "node1/node2"                      — delete node (and all children/items)
  move  "old/path"  "new/path"              — move a node
  rename "node1/node2"  "new name"          — rename last node in path
  dump                                      — pretty-print raw JSON
"""

import sys
import json
import re
from datetime import datetime
from pathlib import Path

DATA = Path.home() / ".openclaw" / "workspace" / "eternalquest-todos.json"
INDENT = "  "

# ── Data helpers ──────────────────────────────────────────────────

def load() -> dict:
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    d = {"nodes": {}}
    _save(d)
    return d

def _save(d: dict):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def parse_path(raw: str) -> list[str]:
    raw = raw.strip()
    if "/" in raw:
        parts = [p.strip() for p in raw.split("/")]
    elif " > " in raw:
        parts = [p.strip() for p in raw.split(" > ")]
    else:
        parts = [raw]
    return [p for p in parts if p]

def get_node(d: dict, parts: list[str], create: bool = False) -> dict | None:
    cur = d["nodes"]
    for part in parts:
        match = _fuzzy(cur, part)
        if match:
            node = cur[match]
        elif create:
            cur[part] = {}
            node = cur[part]
            match = part
        else:
            return None
        cur = node.setdefault("children", {})
    cur = d["nodes"]
    node = None
    for part in parts:
        match = _fuzzy(cur, part) or part
        node = cur[match]
        cur = node.setdefault("children", {})
    return node

def _fuzzy(d: dict, key: str) -> str | None:
    if key in d:
        return key
    key_l = key.lower()
    candidates = [k for k in d if key_l in k.lower()]
    if len(candidates) == 1:
        return candidates[0]
    exact = [k for k in d if k.lower() == key_l]
    if exact:
        return exact[0]
    return candidates[0] if candidates else None

def next_id(items: list) -> int:
    return max((i["id"] for i in items), default=0) + 1

def extract_tags(text: str) -> list[str]:
    return re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b', text)

def has_content(node: dict) -> bool:
    if node.get("items"):
        return True
    for child in node.get("children", {}).values():
        if has_content(child):
            return True
    return False

# ── Print helpers ─────────────────────────────────────────────────

def print_node(name: str, node: dict, depth: int = 0, show_items: bool = True):
    # Skip Archive nodes unless explicitly navigated to
    if name.lower() == "archive":
        return
    pad = INDENT * depth
    if not has_content(node) and show_items:
        return
    print(f"{pad}📂 {name}")
    if show_items:
        for item in node.get("items", []):
            tick = "✅" if item["done"] else "⬜"
            print(f"{pad}{INDENT}{tick} #{item['id']} {item['text']}")
    for child_name, child in node.get("children", {}).items():
        print_node(child_name, child, depth + 1, show_items)

def print_tree_only(name: str, node: dict, depth: int = 0):
    if name.lower() == "archive":
        return
    pad = INDENT * depth
    print(f"{pad}📂 {name}")
    for child_name, child in node.get("children", {}).items():
        print_tree_only(child_name, child, depth + 1)

# ── Commands ──────────────────────────────────────────────────────

def cmd_add(path_str: str, text: str):
    parts = parse_path(path_str)
    d = load()
    node = get_node(d, parts, create=True)
    items = node.setdefault("items", [])
    item = {
        "id": next_id(items),
        "text": text,
        "done": False,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    items.append(item)
    _save(d)
    path_display = " › ".join(parts)
    tags = extract_tags(text)
    tag_str = f"  🏷 {' '.join(tags)}" if tags else ""
    print(f"✅ Added to {path_display}:\n   #{item['id']} {text}{tag_str}")

def cmd_list():
    d = load()
    if not d["nodes"]:
        print("📭 No goals yet."); return
    print("🌟 EternalQuest Tree\n")
    for name, node in d["nodes"].items():
        print_node(name, node, depth=0)

def cmd_tree():
    d = load()
    if not d["nodes"]:
        print("📭 No nodes yet."); return
    for name, node in d["nodes"].items():
        print_tree_only(name, node)

def cmd_show(path_str: str):
    parts = parse_path(path_str)
    d = load()
    node = get_node(d, parts)
    if node is None:
        print(f"❌ Path not found: {' › '.join(parts)}"); return
    print_node(parts[-1], node, depth=0)

def cmd_find(tag: str, path_str: str = ""):
    tag_up = tag.upper()
    d = load()
    results = []

    def search(node: dict, current_path: list[str]):
        for item in node.get("items", []):
            item_tags = extract_tags(item["text"])
            if tag_up and tag_up not in item_tags and tag_up.lower() not in item["text"].lower():
                continue
            results.append((list(current_path), item))
        for child_name, child in node.get("children", {}).items():
            search(child, current_path + [child_name])

    if path_str:
        parts = parse_path(path_str)
        start_node = get_node(d, parts)
        if start_node is None:
            print(f"❌ Path not found: {path_str}"); return
        search(start_node, parts)
    else:
        for name, node in d["nodes"].items():
            search(node, [name])

    if not results:
        scope = f" in {path_str}" if path_str else ""
        print(f"🔍 No results for '{tag}'{scope}"); return

    print(f"🔍 {len(results)} result(s) for '{tag}':\n")
    for path_parts, item in results:
        tick = "✅" if item["done"] else "⬜"
        print(f"{tick}  {' › '.join(path_parts)}")
        print(f"    #{item['id']} {item['text']}\n")

def cmd_done(path_str: str, item_id: int, mark: bool = True):
    parts = parse_path(path_str)
    d = load()
    node = get_node(d, parts)
    if node is None:
        print(f"❌ Path not found: {' › '.join(parts)}"); return
    for item in node.get("items", []):
        if item["id"] == item_id:
            item["done"] = mark
            _save(d)
            state = "✅ Done" if mark else "↩️ Undone"
            print(f"{state}: {item['text']}"); return
    print(f"❌ Item #{item_id} not found at {' › '.join(parts)}")

def cmd_clear():
    d = load()
    n = [0]

    def clear_node(node: dict):
        before = len(node.get("items", []))
        node["items"] = [i for i in node.get("items", []) if not i["done"]]
        n[0] += before - len(node["items"])
        for child in node.get("children", {}).values():
            clear_node(child)

    for node in d["nodes"].values():
        clear_node(node)
    _save(d)
    print(f"🗑️ Cleared {n[0]} completed item(s).")

def cmd_delete(path_str: str):
    parts = parse_path(path_str)
    d = load()
    if len(parts) == 1:
        key = _fuzzy(d["nodes"], parts[0])
        if key:
            del d["nodes"][key]
            _save(d)
            print(f"🗑️ Deleted: {parts[0]}")
        else:
            print(f"❌ Not found: {parts[0]}")
        return
    parent_node = get_node(d, parts[:-1])
    if parent_node is None:
        print(f"❌ Parent path not found"); return
    children = parent_node.get("children", {})
    key = _fuzzy(children, parts[-1])
    if key:
        del children[key]
        _save(d)
        print(f"🗑️ Deleted: {' › '.join(parts)}")
    else:
        print(f"❌ Node not found: {parts[-1]}")

def cmd_rename(path_str: str, new_name: str):
    parts = parse_path(path_str)
    d = load()
    if len(parts) == 1:
        container = d["nodes"]
    else:
        parent = get_node(d, parts[:-1])
        if parent is None:
            print(f"❌ Parent not found"); return
        container = parent.setdefault("children", {})
    old_key = _fuzzy(container, parts[-1])
    if not old_key:
        print(f"❌ Not found: {parts[-1]}"); return
    container[new_name] = container.pop(old_key)
    _save(d)
    print(f"✏️ Renamed '{old_key}' → '{new_name}'")

def cmd_move(src_str: str, dst_str: str):
    src_parts = parse_path(src_str)
    dst_parts = parse_path(dst_str)
    d = load()

    if len(src_parts) == 1:
        src_container = d["nodes"]
    else:
        src_parent = get_node(d, src_parts[:-1])
        if src_parent is None:
            print(f"❌ Source parent not found"); return
        src_container = src_parent.setdefault("children", {})
    src_key = _fuzzy(src_container, src_parts[-1])
    if not src_key:
        print(f"❌ Source not found: {src_parts[-1]}"); return
    node_data = src_container.pop(src_key)

    dst_node = get_node(d, dst_parts, create=True)
    dst_node.setdefault("children", {})[src_parts[-1]] = node_data
    _save(d)
    print(f"📦 Moved '{' › '.join(src_parts)}' → '{' › '.join(dst_parts)} › {src_parts[-1]}'")

def cmd_dump():
    print(json.dumps(load(), indent=2, ensure_ascii=False))

# ── Main ──────────────────────────────────────────────────────────

def usage():
    print(__doc__)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        usage(); sys.exit(1)

    cmd = args[0]
    try:
        if cmd == "add":        cmd_add(args[1], args[2])
        elif cmd == "list":     cmd_list()
        elif cmd == "tree":     cmd_tree()
        elif cmd == "show":     cmd_show(args[1])
        elif cmd == "find":     cmd_find(args[1], args[2] if len(args) > 2 else "")
        elif cmd == "done":     cmd_done(args[1], int(args[2]))
        elif cmd == "undone":   cmd_done(args[1], int(args[2]), mark=False)
        elif cmd == "clear":    cmd_clear()
        elif cmd == "delete":   cmd_delete(args[1])
        elif cmd == "rename":   cmd_rename(args[1], args[2])
        elif cmd == "move":     cmd_move(args[1], args[2])
        elif cmd == "dump":     cmd_dump()
        else:
            print(f"Unknown command: {cmd}"); usage(); sys.exit(1)
    except IndexError as e:
        print(f"❌ Missing argument: {e}"); usage(); sys.exit(1)