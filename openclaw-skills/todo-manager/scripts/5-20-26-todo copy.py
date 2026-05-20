#!/usr/bin/env python3
"""
todo.py — Personal todo tree manager for OpenClaw agent

Commands:
  list                          — show full todo tree
  tree                          — show node names only (no items)
  show "path"                   — show items under a path
  find "TAG" ["path"]           — find items by tag, optionally scoped
  add "path" "text"             — add item (auto-creates nodes)
  done "path" id                — mark item done
  undone "path" id              — mark item not done
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
from datetime import datetime, date, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Paths ─────────────────────────────────────────────────────────
WORKSPACE = Path.home() / ".openclaw" / "workspace"
DATA      = WORKSPACE / "todos.json"
CONFIG    = WORKSPACE / "config.json"

# ── Data helpers ──────────────────────────────────────────────────
def load_data():
    if DATA.exists():
        return json.loads(DATA.read_text())
    return {"name": "root", "children": [], "items": []}

def save_data(tree):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(tree, indent=2))

def load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {}

def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))

# ── Path resolution ───────────────────────────────────────────────
def parse_path(path_str):
    path_str = path_str.replace(" > ", "/")
    return [p.strip() for p in path_str.split("/") if p.strip()]

def find_node(tree, parts, create=False):
    node = tree
    for part in parts:
        found = None
        for child in node.get("children", []):
            if child["name"].lower() == part.lower():
                found = child
                break
        if not found:
            for child in node.get("children", []):
                if part.lower() in child["name"].lower():
                    found = child
                    break
        if not found:
            if create:
                new_node = {"name": part, "children": [], "items": []}
                node.setdefault("children", []).append(new_node)
                found = new_node
            else:
                return None
        node = found
    return node

# ── Tag extraction ────────────────────────────────────────────────
def extract_tags(text):
    return re.findall(r'\b[A-Z][A-Z0-9]{1,}(?:\b|$)', text)

# ── Display helpers ───────────────────────────────────────────────
def fmt_item(item, idx):
    check = "✅" if item.get("done") else "⬜"
    tags = item.get("tags", [])
    tag_str = f" [{', '.join(tags)}]" if tags else ""
    deadline = item.get("deadline", "")
    dl_str = f" 📅 {deadline}" if deadline else ""
    return f"  {check} #{idx} {item['text']}{tag_str}{dl_str}"

def print_tree(node, indent=0, items=True):
    prefix = "  " * indent
    if node["name"] != "root":
        print(f"{prefix}📂 {node['name']}")
    if items:
        for i, item in enumerate(node.get("items", []), 1):
            print(f"{prefix}{fmt_item(item, i)}")
    for child in node.get("children", []):
        print_tree(child, indent + 1, items)

def tree_to_text(node, indent=0, items=True):
    """Return the tree as a string (for email body)."""
    lines = []
    prefix = "  " * indent
    if node["name"] != "root":
        lines.append(f"{prefix}📂 {node['name']}")
    if items:
        for i, item in enumerate(node.get("items", []), 1):
            lines.append(f"{prefix}{fmt_item(item, i)}")
    for child in node.get("children", []):
        lines.append(tree_to_text(child, indent + 1, items))
    return "\n".join(lines)

# ── Collect all items recursively ─────────────────────────────────
def collect_items(node, path=""):
    """Yield (full_path, item_index, item) for every item in the tree."""
    current_path = f"{path}/{node['name']}" if node["name"] != "root" else ""
    for i, item in enumerate(node.get("items", []), 1):
        yield (current_path.lstrip("/"), i, item)
    for child in node.get("children", []):
        yield from collect_items(child, current_path)

# ── Email ─────────────────────────────────────────────────────────
def send_email(subject, body, to_addrs):
    """Send email via Gmail SMTP using App Password."""
    cfg = load_config()
    gmail_address = cfg.get("gmail_address", os.environ.get("GMAIL_ADDRESS", "selfrealizationpy@gmail.com"))
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not app_password:
        print("❌ GMAIL_APP_PASSWORD not set. Run: export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        sys.exit(1)

    # Remove spaces from app password (Google format: "xxxx xxxx xxxx xxxx")
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
def filter_items(tree, filter_type):
    """
    Filter items from the tree based on filter_type.
    Returns list of (path, idx, item) tuples.

    filter_type can be:
      - "all"       — everything
      - "past-due"  — items with deadline before today
      - "A1000"     — items tagged A1000
      - "Monday", "Tuesday", ... "Sunday" — items tagged with that day
      - "Weekend"   — items tagged Saturday, Sunday, or Weekend
      - any tag     — items matching that tag
    """
    today = date.today()
    results = []

    for path, idx, item in collect_items(tree):
        tags = [t.upper() for t in item.get("tags", [])]
        text_upper = item.get("text", "").upper()

        if filter_type == "all":
            results.append((path, idx, item))

        elif filter_type == "past-due":
            deadline_str = item.get("deadline", "")
            if deadline_str:
                try:
                    dl = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                    if dl < today:
                        results.append((path, idx, item))
                except ValueError:
                    pass

        elif filter_type.upper() == "WEEKEND":
            weekend_tags = {"SATURDAY", "SUNDAY", "WEEKEND"}
            if weekend_tags.intersection(set(tags)) or any(wt in text_upper for wt in weekend_tags):
                results.append((path, idx, item))

        else:
            # Match tag or text content
            search = filter_type.upper()
            if search in tags or search in text_upper:
                results.append((path, idx, item))

    return results

def format_filtered_items(items, filter_label):
    """Format filtered items into a nice email body."""
    if not items:
        return f"No items matching '{filter_label}' found.\n"

    lines = [f"📋 Todo Items — {filter_label}", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    # Group by path
    by_path = {}
    for path, idx, item in items:
        by_path.setdefault(path or "Root", []).append((idx, item))

    for path, path_items in sorted(by_path.items()):
        lines.append(f"📂 {path.replace('/', ' › ')}")
        for idx, item in path_items:
            check = "✅" if item.get("done") else "⬜"
            tags = item.get("tags", [])
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            deadline = item.get("deadline", "")
            dl_str = f" 📅 {deadline}" if deadline else ""
            overdue = ""
            if deadline and not item.get("done"):
                try:
                    dl = datetime.strptime(deadline, "%Y-%m-%d").date()
                    if dl < date.today():
                        overdue = " 🔴 OVERDUE"
                except ValueError:
                    pass
            lines.append(f"  {check} #{idx} {item['text']}{tag_str}{dl_str}{overdue}")
        lines.append("")

    lines.append("— Yukteshwar (Todo Agent)")
    return "\n".join(lines)

# ── Commands ──────────────────────────────────────────────────────
def cmd_add(path_str, text):
    tree = load_data()
    parts = parse_path(path_str)
    node = find_node(tree, parts, create=True)
    tags = extract_tags(text)
    # Extract deadline from text: DEADLINE:YYYY-MM-DD
    deadline = ""
    dl_match = re.search(r'DEADLINE:(\d{4}-\d{2}-\d{2})', text)
    if dl_match:
        deadline = dl_match.group(1)
        text = text.replace(dl_match.group(0), "").strip()
    item = {"text": text, "done": False, "tags": tags}
    if deadline:
        item["deadline"] = deadline
    node.setdefault("items", []).append(item)
    save_data(tree)
    path_display = " › ".join(parts)
    print(f"✅ Added to {path_display}: \"{text}\"")
    if tags:
        print(f"   Tags: {', '.join(tags)}")
    if deadline:
        print(f"   Deadline: {deadline}")

def cmd_list():
    tree = load_data()
    print("📋 Todo Tree\n")
    print_tree(tree)

def cmd_tree():
    tree = load_data()
    print("🌳 Tree Structure\n")
    print_tree(tree, items=False)

def cmd_show(path_str):
    tree = load_data()
    parts = parse_path(path_str)
    node = find_node(tree, parts)
    if not node:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    print_tree(node)

def cmd_find(tag, path_str=""):
    tree = load_data()
    root = tree
    if path_str:
        parts = parse_path(path_str)
        root = find_node(tree, parts)
        if not root:
            print(f"❌ Path not found: {path_str}")
            sys.exit(1)

    results = []
    def search(node, trail=""):
        current = f"{trail}/{node['name']}" if node['name'] != 'root' else trail
        for i, item in enumerate(node.get("items", []), 1):
            if tag.upper() in [t.upper() for t in item.get("tags", [])] or tag.upper() in item.get("text", "").upper():
                results.append((current.lstrip("/"), i, item))
        for child in node.get("children", []):
            search(child, current)

    search(root)
    if not results:
        print(f"🔍 No items matching '{tag}'")
        return
    print(f"🔍 Found {len(results)} item(s) matching '{tag}':\n")
    for path, idx, item in results:
        print(f"  📂 {path.replace('/', ' › ')}")
        print(f"  {fmt_item(item, idx)}\n")

def cmd_done(path_str, item_id, mark=True):
    tree = load_data()
    parts = parse_path(path_str)
    node = find_node(tree, parts)
    if not node:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    items = node.get("items", [])
    if item_id < 1 or item_id > len(items):
        print(f"❌ Item #{item_id} not found")
        sys.exit(1)
    items[item_id - 1]["done"] = mark
    save_data(tree)
    status = "done" if mark else "not done"
    print(f"✅ Marked #{item_id} as {status}: \"{items[item_id-1]['text']}\"")

def cmd_clear():
    tree = load_data()
    count = 0
    def clear_done(node):
        nonlocal count
        before = len(node.get("items", []))
        node["items"] = [i for i in node.get("items", []) if not i.get("done")]
        count += before - len(node["items"])
        for child in node.get("children", []):
            clear_done(child)
    clear_done(tree)
    save_data(tree)
    print(f"🧹 Cleared {count} completed item(s)")

def cmd_delete(path_str):
    tree = load_data()
    parts = parse_path(path_str)
    if len(parts) < 1:
        print("❌ Cannot delete root")
        sys.exit(1)
    parent = find_node(tree, parts[:-1]) if len(parts) > 1 else tree
    if not parent:
        print(f"❌ Parent path not found")
        sys.exit(1)
    target_name = parts[-1].lower()
    children = parent.get("children", [])
    found = None
    for i, child in enumerate(children):
        if child["name"].lower() == target_name or target_name in child["name"].lower():
            found = i
            break
    if found is None:
        print(f"❌ Node not found: {parts[-1]}")
        sys.exit(1)
    removed = children.pop(found)
    save_data(tree)
    print(f"🗑️ Deleted: {removed['name']}")

def cmd_rename(path_str, new_name):
    tree = load_data()
    parts = parse_path(path_str)
    node = find_node(tree, parts)
    if not node:
        print(f"❌ Path not found: {path_str}")
        sys.exit(1)
    old = node["name"]
    node["name"] = new_name
    save_data(tree)
    print(f"✏️ Renamed: {old} → {new_name}")

def cmd_move(src_str, dst_str):
    tree = load_data()
    src_parts = parse_path(src_str)
    if len(src_parts) < 1:
        print("❌ Cannot move root")
        sys.exit(1)
    src_parent = find_node(tree, src_parts[:-1]) if len(src_parts) > 1 else tree
    if not src_parent:
        print(f"❌ Source parent not found")
        sys.exit(1)
    target_name = src_parts[-1].lower()
    children = src_parent.get("children", [])
    found = None
    for i, child in enumerate(children):
        if child["name"].lower() == target_name or target_name in child["name"].lower():
            found = i
            break
    if found is None:
        print(f"❌ Source not found: {src_parts[-1]}")
        sys.exit(1)
    node = children.pop(found)
    dst_parts = parse_path(dst_str)
    dst_node = find_node(tree, dst_parts, create=True)
    dst_node.setdefault("children", []).append(node)
    save_data(tree)
    print(f"📦 Moved: {node['name']} → {dst_str}")

def cmd_dump():
    tree = load_data()
    print(json.dumps(tree, indent=2))

def cmd_email(subject, body, to_addrs):
    send_email(subject, body, to_addrs)

def cmd_email_todos(to_addrs):
    """Email the full todo tree."""
    tree = load_data()
    body = tree_to_text(tree)
    full_body = f"📋 Full Todo List\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{body}\n\n— Yukteshwar (Todo Agent)"
    subject = f"📋 Full Todo List — {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, full_body, to_addrs)

def cmd_email_filtered(filter_type, to_addrs):
    """Email filtered items."""
    tree = load_data()
    items = filter_items(tree, filter_type)

    # Build a nice subject based on filter
    filter_labels = {
        "all": "All Items",
        "past-due": "⚠️ Past Due Items",
        "A1000": "A1000 Tagged Items",
        "MONDAY": "Monday Items",
        "TUESDAY": "Tuesday Items",
        "WEDNESDAY": "Wednesday Items",
        "THURSDAY": "Thursday Items",
        "FRIDAY": "Friday Items",
        "SATURDAY": "Saturday Items",
        "SUNDAY": "Sunday Items",
        "WEEKEND": "Weekend Items",
    }
    label = filter_labels.get(filter_type.upper(), f"'{filter_type}' Items")
    subject = f"📋 Todo: {label} — {datetime.now().strftime('%Y-%m-%d')}"
    body = format_filtered_items(items, label)
    send_email(subject, body, to_addrs)

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
        usage()
        sys.exit(0)

    cmd = args[0]
    try:
        if cmd == "add":            cmd_add(args[1], args[2])
        elif cmd == "list":         cmd_list()
        elif cmd == "tree":         cmd_tree()
        elif cmd == "show":         cmd_show(args[1])
        elif cmd == "find":         cmd_find(args[1], args[2] if len(args) > 2 else "")
        elif cmd == "done":         cmd_done(args[1], int(args[2]))
        elif cmd == "undone":       cmd_done(args[1], int(args[2]), mark=False)
        elif cmd == "clear":        cmd_clear()
        elif cmd == "delete":       cmd_delete(args[1])
        elif cmd == "rename":       cmd_rename(args[1], args[2])
        elif cmd == "move":         cmd_move(args[1], args[2])
        elif cmd == "dump":         cmd_dump()
        elif cmd == "email":        cmd_email(args[1], args[2], args[3])
        elif cmd == "email-todos":  cmd_email_todos(args[1])
        elif cmd == "email-filtered": cmd_email_filtered(args[1], args[2])
        elif cmd == "config-show":  cmd_config_show()
        elif cmd == "config-set":   cmd_config_set(args[1], args[2])
        else:
            print(f"Unknown command: {cmd}"); usage(); sys.exit(1)
    except IndexError as e:
        print(f"❌ Missing argument: {e}"); usage(); sys.exit(1)