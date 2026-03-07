#!/usr/bin/env python3
"""
realestate.py — Property management helper for OpenClaw real estate agent

Commands:
  list                          — show full property tree
  deadlines [days=30]           — show upcoming deadlines sorted by date
  add "Property/Category" "text DEADLINE:YYYY-MM-DD"  — add item
  done "Property/Category" <id> — mark item done
  email "subject" "body" "to1,to2"  — send email
  remind [days=30]              — send deadline reminder email to all partners
  config-show                   — show email config
  config-set <key> <value>      — set config value
  init                          — initialize default property structure
  dump                          — print raw JSON
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
WORKSPACE = Path.home() / ".openclaw" / "workspace-realestate"
DATA      = WORKSPACE / "properties.json"
CONFIG    = WORKSPACE / "config.json"

# ── Default data ──────────────────────────────────────────────────
DEFAULT_DATA = {
  "nodes": {
    "Millpointe": {
      "items": [],
      "children": {
        "Rent": {
          "items": [
            {"id": 1, "text": "RENT Monthly rent collection DEADLINE:2026-03-03", "done": False, "created": "2026-03-06 00:00"},
            {"id": 2, "text": "RENT TAB deadline 3rd of month DEADLINE:2026-03-03", "done": False, "created": "2026-03-06 00:00"}
          ],
          "children": {}
        },
        "PropertyTax": {
          "items": [
            {"id": 1, "text": "TAX Property tax payment DEADLINE:2026-04-01", "done": False, "created": "2026-03-06 00:00"}
          ],
          "children": {}
        }
      }
    },
    "NPlainfield": {
      "items": [],
      "children": {
        "Rent": {
          "items": [
            {"id": 1, "text": "RENT Monthly rent collection DEADLINE:2026-03-03", "done": False, "created": "2026-03-06 00:00"},
            {"id": 2, "text": "RENT TAB deadline 3rd of month DEADLINE:2026-03-03", "done": False, "created": "2026-03-06 00:00"}
          ],
          "children": {}
        },
        "PropertyTax": {
          "items": [
            {"id": 1, "text": "TAX Property tax payment DEADLINE:2026-04-01", "done": False, "created": "2026-03-06 00:00"}
          ],
          "children": {}
        }
      }
    }
  }
}

DEFAULT_CONFIG = {
    "chuck_email": "",
    "nisha_email": "",
    "gmail_address": ""
}

PROPERTY_ADDRESSES = {
    "Millpointe": "392 College Drive",
    "NPlainfield": "401 Highway"
}

# ── Data helpers ──────────────────────────────────────────────────
def load() -> dict:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    d = json.loads(json.dumps(DEFAULT_DATA))
    _save(d)
    return d

def _save(d: dict):
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def load_config() -> dict:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    return DEFAULT_CONFIG.copy()

def save_config(c: dict):
    CONFIG.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

def parse_path(raw: str) -> list:
    if "/" in raw:
        return [p.strip() for p in raw.split("/") if p.strip()]
    if " > " in raw:
        return [p.strip() for p in raw.split(" > ") if p.strip()]
    return [raw.strip()]

def extract_deadline(text: str):
    m = re.search(r'DEADLINE:(\d{4}-\d{2}-\d{2})', text)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            return None
    return None

def extract_tags(text: str) -> list:
    return re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b', text)

def next_id(items: list) -> int:
    return max((i["id"] for i in items), default=0) + 1

def _fuzzy(d: dict, key: str):
    if key in d: return key
    key_l = key.lower()
    exact = [k for k in d if k.lower() == key_l]
    if exact: return exact[0]
    candidates = [k for k in d if key_l in k.lower()]
    return candidates[0] if candidates else None

def get_node(d: dict, parts: list, create=False):
    cur = d["nodes"]
    node = None
    for part in parts:
        match = _fuzzy(cur, part)
        if match:
            node = cur[match]
        elif create:
            cur[part] = {"items": [], "children": {}}
            node = cur[part]
            match = part
        else:
            return None
        cur = node.setdefault("children", {})
    return node

# ── Print helpers ─────────────────────────────────────────────────
INDENT = "  "

def deadline_flag(dl):
    if not dl: return ""
    today = date.today()
    days_left = (dl - today).days
    if days_left < 0:   return " 🔴 OVERDUE"
    if days_left <= 7:  return f" 🔴 due in {days_left}d"
    if days_left <= 30: return f" 🟡 due in {days_left}d"
    return f" ⚪ due {dl}"

def print_node(name: str, node: dict, depth=0):
    pad = INDENT * depth
    addr = PROPERTY_ADDRESSES.get(name, "")
    label = f"{name} ({addr})" if addr else name
    print(f"{pad}🏠 {label}" if depth == 0 else f"{pad}📁 {name}")
    for item in node.get("items", []):
        dl = extract_deadline(item["text"])
        tick = "✅" if item["done"] else "⬜"
        flag = deadline_flag(dl)
        print(f"{pad}{INDENT}{tick} #{item['id']} {item['text']}{flag}")
    for child_name, child in node.get("children", {}).items():
        print_node(child_name, child, depth + 1)

# ── Commands ──────────────────────────────────────────────────────

def cmd_list():
    d = load()
    print("🏠 Real Estate Properties\n")
    for name, node in d["nodes"].items():
        print_node(name, node)
        print()

def cmd_deadlines(days=30):
    d = load()
    today = date.today()
    cutoff = today + timedelta(days=int(days))
    results = []

    def scan(node, path):
        for item in node.get("items", []):
            if item["done"]: continue
            dl = extract_deadline(item["text"])
            if dl and dl <= cutoff:
                results.append((dl, path, item))
        for child_name, child in node.get("children", {}).items():
            scan(child, path + [child_name])

    for name, node in d["nodes"].items():
        scan(node, [name])

    results.sort(key=lambda x: x[0])

    if not results:
        print(f"✅ No deadlines in the next {days} days."); return

    print(f"📅 Upcoming deadlines (next {days} days):\n")
    for dl, path, item in results:
        flag = deadline_flag(dl)
        path_str = " › ".join(path)
        print(f"{flag.strip()}  {path_str}")
        print(f"    #{item['id']} {item['text']}\n")

def cmd_add(path_str: str, text: str):
    parts = parse_path(path_str)
    d = load()
    node = get_node(d, parts, create=True)
    items = node.setdefault("items", [])
    item = {"id": next_id(items), "text": text, "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    items.append(item)
    _save(d)
    dl = extract_deadline(text)
    flag = deadline_flag(dl) if dl else ""
    print(f"✅ Added to {' › '.join(parts)}:\n   #{item['id']} {text}{flag}")

def cmd_done(path_str: str, item_id: int):
    parts = parse_path(path_str)
    d = load()
    node = get_node(d, parts)
    if not node:
        print(f"❌ Path not found: {' › '.join(parts)}"); return
    for item in node.get("items", []):
        if item["id"] == item_id:
            item["done"] = True
            _save(d)
            print(f"✅ Done: {item['text']}"); return
    print(f"❌ Item #{item_id} not found")

def cmd_email(subject: str, body: str, to_addresses: str):
    cfg = load_config()
    gmail_addr = cfg.get("gmail_address") or os.environ.get("GMAIL_ADDRESS", "")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_addr:
        print("❌ gmail_address not configured. Run: python3 realestate.py config-set gmail_address you@gmail.com"); return
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD env var not set."); return

    recipients = [e.strip() for e in to_addresses.split(",") if e.strip()]
    msg = MIMEMultipart()
    msg["From"]    = gmail_addr
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_addr, app_password)
            server.sendmail(gmail_addr, recipients, msg.as_string())
        print(f"✅ Email sent to: {', '.join(recipients)}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def cmd_remind(days=30):
    cfg = load_config()
    chuck  = cfg.get("chuck_email", "")
    nisha  = cfg.get("nisha_email", "")

    if not chuck or not nisha:
        print("❌ Email addresses not configured. Run:\n  python3 realestate.py config-set chuck_email your@email.com\n  python3 realestate.py config-set nisha_email partner@email.com"); return

    d = load()
    today = date.today()
    cutoff = today + timedelta(days=int(days))

    # Build reminder content per property
    property_lines = {}
    def scan(node, path):
        prop = path[0]
        for item in node.get("items", []):
            if item["done"]: continue
            dl = extract_deadline(item["text"])
            if dl and dl <= cutoff:
                if prop not in property_lines:
                    property_lines[prop] = []
                clean = re.sub(r'DEADLINE:\d{4}-\d{2}-\d{2}', '', item["text"]).strip()
                property_lines[prop].append(f"  📅 {dl.strftime('%b %d')}: {clean}")
        for child_name, child in node.get("children", {}).items():
            scan(child, path + [child_name])

    for name, node in d["nodes"].items():
        scan(node, [name])

    if not property_lines:
        print(f"✅ No deadlines in next {days} days — no reminder sent."); return

    # Build email body
    body_lines = ["Hi Chuck & Nisha,\n", f"Upcoming property deadlines (next {days} days):\n"]
    for prop, lines in property_lines.items():
        addr = PROPERTY_ADDRESSES.get(prop, "")
        body_lines.append(f"🏠 {prop} — {addr}")
        body_lines.extend(lines)
        body_lines.append("")
    body_lines.append("— Real Estate Assistant")
    body = "\n".join(body_lines)

    subject = f"[Real Estate] Upcoming Deadlines — {today.strftime('%b %d, %Y')}"

    print("📧 Preview:\n")
    print(f"To: {chuck}, {nisha}")
    print(f"Subject: {subject}")
    print(f"\n{body}\n")

    confirm = input("Send this email? [y/N] ").strip().lower()
    if confirm == "y":
        cmd_email(subject, body, f"{chuck},{nisha}")
    else:
        print("Cancelled.")

def cmd_config_show():
    cfg = load_config()
    print("📧 Email config:\n")
    for k, v in cfg.items():
        val = v if v else "(not set)"
        print(f"  {k}: {val}")

def cmd_config_set(key: str, value: str):
    cfg = load_config()
    if key not in DEFAULT_CONFIG:
        print(f"❌ Unknown key: {key}. Valid keys: {', '.join(DEFAULT_CONFIG.keys())}"); return
    cfg[key] = value
    save_config(cfg)
    print(f"✅ Set {key} = {value}")

def cmd_init():
    d = json.loads(json.dumps(DEFAULT_DATA))
    _save(d)
    print("✅ Initialized default property structure.")
    cmd_list()

def cmd_dump():
    print(json.dumps(load(), indent=2, ensure_ascii=False))

# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    cmd = args[0]
    try:
        if cmd == "list":           cmd_list()
        elif cmd == "deadlines":    cmd_deadlines(args[1] if len(args) > 1 else 30)
        elif cmd == "add":          cmd_add(args[1], args[2])
        elif cmd == "done":         cmd_done(args[1], int(args[2]))
        elif cmd == "email":        cmd_email(args[1], args[2], args[3])
        elif cmd == "remind":       cmd_remind(args[1] if len(args) > 1 else 30)
        elif cmd == "config-show":  cmd_config_show()
        elif cmd == "config-set":   cmd_config_set(args[1], args[2])
        elif cmd == "init":         cmd_init()
        elif cmd == "dump":         cmd_dump()
        else:
            print(f"Unknown command: {cmd}"); sys.exit(1)
    except IndexError as e:
        print(f"❌ Missing argument: {e}"); print(__doc__); sys.exit(1)