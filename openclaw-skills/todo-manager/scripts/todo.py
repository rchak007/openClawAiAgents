#!/usr/bin/env python3
"""
todo.py — Personal todo tree manager for OpenClaw agent

** SCHEMA: matches todo_tree_server.py exactly **
  Root:  {"nodes": { <name>: <node>, ... }}
  Node:  {"children": { <name>: <node>, ... }, "items": [ <item>, ... ]}
  Item:  {"id": int, "text": str, "done": bool, "created": "YYYY-MM-DD HH:MM"}

  Tags are DERIVED from item text at display time (uppercase tokens), never
  stored, so the web UI and this script never disagree about the file.

Commands:
  list                          — show full todo tree
  tree                          — show node names only (no items)
  show "path"                   — show items under a path
  find "TAG" ["path"]           — find items by tag/text, optionally scoped
  add "path" "text"             — add item (auto-creates nodes)
  done "path" id                — mark item done (by item id)
  undone "path" id              — mark item not done (by item id)
  clear                         — remove all completed items
  delete "path"                 — delete a node and all children
  rename "path" "new name"      — rename a node
  move "src" "dst"              — move a node to a new parent
  dump                          — print raw JSON
  email "subject" "body" "to"   — send email via Gmail SMTP
  email-todos "to"              — email full todo list
  email-filtered "filter" "to"  — email filtered items (past-due, A1000, Monday, etc.)
  config-show                   — show email config
  config-set key value          — set config value
"""

import sys
import json
import re
import smtplib
import os
from datetime import datetime, date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Paths ─────────────────────────────────────────────────────────
WORKSPACE = Path.home() / ".openclaw" / "workspace"
DATA      = WORKSPACE / "todos.json"
CONFIG    = WORKSPACE / "config.json"

# ── Data helpers ──────────────────────────────────────────────────
def load_data():
    """Return {"nodes": {...}}, normalizing any legacy shapes."""
    if not DATA.exists():
        return {"nodes": {}}
    data = json.loads(DATA.read_text())
    # Legacy: {"categories": {...}}
    if isinstance(data, dict) and "nodes" not in data and "categories" in data:
        data = {"nodes": data["categories"]}
    if not isinstance(data, dict) or "nodes" not in data:
        data = {"nodes": {}}
    # Defensive: if an old list-style "children" block ever lingers at the
    # root, fold it into nodes{} so we never lose items (one-way safety net).
    if isinstance(data.get("children"), list):
        _absorb_list_children(data["nodes"], data["children"])
        data.pop("children", None)
    return data

def save_data(data):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, indent=2))

def _absorb_list_children(nodes: dict, children_list: list):
    """Fold a legacy list-style [{name, children[], items[]}] tree into nodes{}."""
    for entry in children_list or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        if name not in nodes:
            nodes[name] = {"children": {}, "items": []}
        node = nodes[name]
        node.setdefault("children", {})
        node.setdefault("items", [])
        nid = max([it.get("id", 0) for it in node["items"]], default=0)
        for it in entry.get("items", []):
            nid += 1
            node["items"].append({
                "id": it.get("id", nid),
                "text": it.get("text", ""),
                "done": it.get("done", False),
                "created": it.get("created", datetime.now().strftime("%Y-%m-%d %H:%M")),
            })
        if entry.get("children"):
            _absorb_list_children(node["children"], entry["children"])

def load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {}

def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))

# ── Path resolution (dict schema) ─────────────────────────────────
def parse_path(path_str):
    path_str = path_str.replace(" > ", "/")
    return [p.strip() for p in path_str.split("/") if p.strip()]

def find_node(data, parts, create=False):
    """
    Walk the nodes{} dict. Returns the node dict at the path, or None.
    A node is {"children": {...}, "items": [...]}.
    Matching is case-insensitive with substring fallback (preserves the old
    agent behaviour where 'lausd' matches 'LAUSD').
    """
    current = data["nodes"]
    node = None
    for part in parts:
        # exact (case-insensitive) match, then substring fallback
        match_key = None
        for key in current.keys():
            if key.lower() == part.lower():
                match_key = key
                break
        if match_key is None:
            for key in current.keys():
                if part.lower() in key.lower():
                    match_key = key
                    break
        if match_key is None:
            if create:
                current[part] = {"children": {}, "items": []}
                match_key = part
            else:
                return None
        node = current[match_key]
        node.setdefault("children", {})
        node.setdefault("items", [])
        current = node["children"]
    return node

def get_next_id(node):
    items = node.get("items", [])
    if not items:
        return 1
    return max(it.get("id", 0) for it in items) + 1

# ── Tag extraction (display only — never stored) ──────────────────
def extract_tags(text):
    return re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b', text or "")

def extract_deadline(text):
    """Pull a (due: M/D/YY) or DEADLINE:YYYY-MM-DD style date out of text for display."""
    m = re.search(r'DEADLINE:(\d{4}-\d{2}-\d{2})', text or "")
    if m:
        return m.group(1)
    m = re.search(r'due:?\s*(\d{1,2}/\d{1,2}/\d{2,4})', text or "", re.IGNORECASE)
    if m:
        return m.group(1)
    return ""

# ── Display helpers ───────────────────────────────────────────────
def fmt_item(item):
    check = "✅" if item.get("done") else "⬜"
    tags = extract_tags(item.get("text", ""))
    tag_str = f" [{', '.join(tags)}]" if tags else ""
    return f"  {check} #{item.get('id','?')} {item.get('text','')}{tag_str}"

def print_tree(nodes, indent=0, items=True):
    for name in sorted(nodes.keys()):
        node = nodes[name]
        print(f"{'  ' * indent}📂 {name}")
        if items:
            for item in node.get("items", []):
                print(f"{'  ' * indent}{fmt_item(item)}")
        if node.get("children"):
            print_tree(node["children"], indent + 1, items)

def tree_to_text(nodes, indent=0, items=True):
    lines = []
    for name in sorted(nodes.keys()):
        node = nodes[name]
        lines.append(f"{'  ' * indent}📂 {name}")
        if items:
            for item in node.get("items", []):
                lines.append(f"{'  ' * indent}{fmt_item(item)}")
        if node.get("children"):
            lines.append(tree_to_text(node["children"], indent + 1, items))
    return "\n".join(lines)

# ── Collect all items recursively ─────────────────────────────────
def collect_items(nodes, path=""):
    """Yield (full_path, item) for every item in the tree."""
    for name in sorted(nodes.keys()):
        node = nodes[name]
        cur = f"{path}/{name}".lstrip("/")
        for item in node.get("items", []):
            yield (cur, item)
        if node.get("children"):
            yield from collect_items(node["children"], cur)

# ── Email ─────────────────────────────────────────────────────────
def send_email(subject, body, to_addrs):
    cfg = load_config()
    gmail_address = cfg.get("gmail_address", os.environ.get("GMAIL_ADDRESS", "selfrealizationpy@gmail.com"))
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD not set. Run: export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        sys.exit(1)
    app_password = app_password.replace(" ", "")
    if isinstance(to_addrs, str):
        to_addrs = [a.strip() for a in to_addrs.split(",")]
    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_address, app_password)
            server.sendmail(gmail_address, to_addrs, msg.as_string())
        print(f"✅ Email sent to {', '.join(to_addrs)}")
        print(f"   Subject: {subject}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        sys.exit(1)

# ── Filter logic ──────────────────────────────────────────────────
def filter_items(data, filter_type):
    today = date.today()
    results = []
    for path, item in collect_items(data["nodes"]):
        text = item.get("text", "")
        tags = [t.upper() for t in extract_tags(text)]
        text_upper = text.upper()

        if filter_type == "all":
            results.append((path, item))
        elif filter_type == "past-due":
            dl = extract_deadline(text)
            if dl:
                parsed = None
                for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
                    try:
                        parsed = datetime.strptime(dl, fmt).date()
                        break
                    except ValueError:
                        continue
                if parsed and parsed < today and not item.get("done"):
                    results.append((path, item))
        elif filter_type.upper() == "WEEKEND":
            weekend = {"SATURDAY", "SUNDAY", "WEEKEND"}
            if weekend.intersection(set(tags)) or any(w in text_upper for w in weekend):
                results.append((path, item))
        else:
            search = filter_type.upper()
            if search in tags or search in text_upper:
                results.append((path, item))
    return results

def format_filtered_items(items, filter_label):
    if not items:
        return f"No items matching '{filter_label}' found.\n"
    lines = [f"📋 Todo Items — {filter_label}",
             f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    by_path = {}
    for path, item in items:
        by_path.setdefault(path or "Root", []).append(item)
    for path, path_items in sorted(by_path.items()):
        lines.append(f"📂 {path.replace('/', ' › ')}")
        for item in path_items:
            check = "✅" if item.get("done") else "⬜"
            tags = extract_tags(item.get("text", ""))
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"  {check} #{item.get('id','?')} {item.get('text','')}{tag_str}")
        lines.append("")
    lines.append("— Yukteshwar (Todo Agent)")
    return "\n".join(lines)

# ── Commands ──────────────────────────────────────────────────────
def cmd_add(path_str, text):
    data = load_data()
    parts = parse_path(path_str)
    node = find_node(data, parts, create=True)
    item = {
        "id": get_next_id(node),
        "text": text,
        "done": False,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    node.setdefault("items", []).append(item)
    save_data(data)
    print(f"✅ Added to {' › '.join(parts)}: \"{text}\" (#{item['id']})")
    tags = extract_tags(text)
    if tags:
        print(f"   Tags: {', '.join(tags)}")

def cmd_list():
    data = load_data()
    print("📋 Todo Tree\n")
    print_tree(data["nodes"])

def cmd_tree():
    data = load_data()
    print("🌳 Tree Structure\n")
    print_tree(data["nodes"], items=False)

def cmd_show(path_str):
    data = load_data()
    node = find_node(data, parse_path(path_str))
    if node is None:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    # Show this node's items + its subtree
    for item in node.get("items", []):
        print(fmt_item(item))
    if node.get("children"):
        print_tree(node["children"])

def cmd_find(tag, path_str=""):
    data = load_data()
    if path_str:
        node = find_node(data, parse_path(path_str))
        if node is None:
            print(f"❌ Path not found: {path_str}")
            sys.exit(1)
        scope = {"_": node}  # wrap so collect_items can iterate
        pairs = []
        base = path_str.replace(" > ", "/")
        for item in node.get("items", []):
            pairs.append((base, item))
        if node.get("children"):
            pairs.extend(collect_items(node["children"], base))
    else:
        pairs = list(collect_items(data["nodes"]))

    needle = tag.upper()
    results = [(p, it) for p, it in pairs
               if needle in [t.upper() for t in extract_tags(it.get("text", ""))]
               or needle in it.get("text", "").upper()]
    if not results:
        print(f"🔍 No items matching '{tag}'")
        return
    print(f"🔍 Found {len(results)} item(s) matching '{tag}':\n")
    for path, item in results:
        print(f"  📂 {path.replace('/', ' › ')}")
        print(f"  {fmt_item(item)}\n")

def cmd_done(path_str, item_id, mark=True):
    data = load_data()
    node = find_node(data, parse_path(path_str))
    if node is None:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    for item in node.get("items", []):
        if item.get("id") == item_id:
            item["done"] = mark
            save_data(data)
            status = "done" if mark else "not done"
            print(f"✅ Marked #{item_id} as {status}: \"{item['text']}\"")
            return
    print(f"❌ Item #{item_id} not found at {path_str}")
    sys.exit(1)

def cmd_clear():
    data = load_data()
    count = 0
    def clear_done(nodes):
        nonlocal count
        for node in nodes.values():
            before = len(node.get("items", []))
            node["items"] = [i for i in node.get("items", []) if not i.get("done")]
            count += before - len(node["items"])
            if node.get("children"):
                clear_done(node["children"])
    clear_done(data["nodes"])
    save_data(data)
    print(f"🧹 Cleared {count} completed item(s)")

def cmd_delete(path_str):
    data = load_data()
    parts = parse_path(path_str)
    if not parts:
        print("❌ Cannot delete root")
        sys.exit(1)
    if len(parts) == 1:
        parent_children = data["nodes"]
    else:
        parent = find_node(data, parts[:-1])
        if parent is None:
            print("❌ Parent path not found")
            sys.exit(1)
        parent_children = parent.setdefault("children", {})
    # case-insensitive / substring match on the leaf name
    target = parts[-1].lower()
    key = None
    for k in parent_children.keys():
        if k.lower() == target or target in k.lower():
            key = k
            break
    if key is None:
        print(f"❌ Node not found: {parts[-1]}")
        sys.exit(1)
    parent_children.pop(key)
    save_data(data)
    print(f"🗑️ Deleted: {key}")

def cmd_rename(path_str, new_name):
    data = load_data()
    parts = parse_path(path_str)
    if not parts:
        print("❌ Cannot rename root")
        sys.exit(1)
    container = data["nodes"] if len(parts) == 1 else (find_node(data, parts[:-1]) or {}).get("children", {})
    target = parts[-1].lower()
    key = None
    for k in container.keys():
        if k.lower() == target or target in k.lower():
            key = k
            break
    if key is None:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    container[new_name] = container.pop(key)
    save_data(data)
    print(f"✏️ Renamed: {key} → {new_name}")

def cmd_move(src_str, dst_str):
    data = load_data()
    src_parts = parse_path(src_str)
    if not src_parts:
        print("❌ Cannot move root")
        sys.exit(1)
    src_container = data["nodes"] if len(src_parts) == 1 else (find_node(data, src_parts[:-1]) or {}).get("children", {})
    target = src_parts[-1].lower()
    key = None
    for k in src_container.keys():
        if k.lower() == target or target in k.lower():
            key = k
            break
    if key is None:
        print(f"❌ Source not found: {src_parts[-1]}")
        sys.exit(1)
    moved = src_container.pop(key)
    dst_node = find_node(data, parse_path(dst_str), create=True)
    dst_node.setdefault("children", {})[key] = moved
    save_data(data)
    print(f"📦 Moved: {key} → {dst_str}")

def cmd_dump():
    print(json.dumps(load_data(), indent=2))

def cmd_email(subject, body, to_addrs):
    send_email(subject, body, to_addrs)

def cmd_email_todos(to_addrs):
    data = load_data()
    body = tree_to_text(data["nodes"])
    full = f"📋 Full Todo List\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{body}\n\n— Yukteshwar (Todo Agent)"
    send_email(f"📋 Full Todo List — {datetime.now().strftime('%Y-%m-%d')}", full, to_addrs)

def cmd_email_filtered(filter_type, to_addrs):
    data = load_data()
    items = filter_items(data, filter_type)
    labels = {
        "all": "All Items", "past-due": "⚠️ Past Due Items", "A1000": "A1000 Tagged Items",
        "MONDAY": "Monday Items", "TUESDAY": "Tuesday Items", "WEDNESDAY": "Wednesday Items",
        "THURSDAY": "Thursday Items", "FRIDAY": "Friday Items", "SATURDAY": "Saturday Items",
        "SUNDAY": "Sunday Items", "WEEKEND": "Weekend Items",
    }
    label = labels.get(filter_type.upper(), f"'{filter_type}' Items")
    send_email(f"📋 Todo: {label} — {datetime.now().strftime('%Y-%m-%d')}",
               format_filtered_items(items, label), to_addrs)

def cmd_config_show():
    cfg = load_config()
    print("📧 Email config:")
    for key in ["chuck_email", "gmail_address"]:
        print(f"  {key}: {cfg.get(key, '(not set)')}")

def cmd_config_set(key, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    print(f"✅ Set {key} = {value}")

def usage():
    print(__doc__)

# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        usage(); sys.exit(0)
    cmd = args[0]
    try:
        if cmd == "add":               cmd_add(args[1], args[2])
        elif cmd == "list":            cmd_list()
        elif cmd == "tree":            cmd_tree()
        elif cmd == "show":            cmd_show(args[1])
        elif cmd == "find":            cmd_find(args[1], args[2] if len(args) > 2 else "")
        elif cmd == "done":            cmd_done(args[1], int(args[2]))
        elif cmd == "undone":          cmd_done(args[1], int(args[2]), mark=False)
        elif cmd == "clear":           cmd_clear()
        elif cmd == "delete":          cmd_delete(args[1])
        elif cmd == "rename":          cmd_rename(args[1], args[2])
        elif cmd == "move":            cmd_move(args[1], args[2])
        elif cmd == "dump":            cmd_dump()
        elif cmd == "email":           cmd_email(args[1], args[2], args[3])
        elif cmd == "email-todos":     cmd_email_todos(args[1])
        elif cmd == "email-filtered":  cmd_email_filtered(args[1], args[2])
        elif cmd == "config-show":     cmd_config_show()
        elif cmd == "config-set":      cmd_config_set(args[1], args[2])
        else:
            print(f"Unknown command: {cmd}"); usage(); sys.exit(1)
    except IndexError as e:
        print(f"❌ Missing argument: {e}"); usage(); sys.exit(1)