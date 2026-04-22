#!/usr/bin/env python3
"""
todo-cron.py — Scheduled email reminders for todo items

Called by cron, determines what to send based on current day/time.
This script is meant to be called once per minute by a single cron entry,
and it checks the current time to decide what to do.

Alternatively, use separate cron entries per schedule (recommended).

Usage:
  python3 todo-cron.py full-list          # Email full todo list
  python3 todo-cron.py daily-priority     # Past-due + A1000 tagged items
  python3 todo-cron.py day-tagged         # Items tagged with today's day name
  python3 todo-cron.py weekend-tagged     # Items tagged Saturday/Sunday/Weekend
"""

import sys
import os
import subprocess
from datetime import datetime, date
from pathlib import Path

# Path to todo.py (same directory as this script)
SCRIPT_DIR = Path(__file__).parent
TODO_PY = SCRIPT_DIR / "todo.py"

# Default recipient
DEFAULT_TO = "rchak1@aol.com"

def run_todo_cmd(cmd_args):
    """Run todo.py with given arguments."""
    full_cmd = [sys.executable, str(TODO_PY)] + cmd_args
    env = os.environ.copy()
    # Ensure we load bashrc env vars if running from cron
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        # Extract GMAIL_APP_PASSWORD from bashrc if not in env
        if "GMAIL_APP_PASSWORD" not in env:
            import re
            content = bashrc.read_text()
            match = re.search(r"export\s+GMAIL_APP_PASSWORD=['\"]?([^'\"#\n]+)['\"]?", content)
            if match:
                env["GMAIL_APP_PASSWORD"] = match.group(1).strip()
    result = subprocess.run(full_cmd, capture_output=True, text=True, env=env)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode

def cmd_full_list(to_addr=DEFAULT_TO):
    """Send the complete todo list via email."""
    print(f"📋 Sending full todo list to {to_addr}...")
    return run_todo_cmd(["email-todos", to_addr])

def cmd_daily_priority(to_addr=DEFAULT_TO):
    """Send past-due items + A1000 tagged items."""
    print(f"⚠️ Sending daily priority items to {to_addr}...")
    # We'll send both filters in one email by calling the script twice
    # or better: create a combined report
    import json
    
    # Load todo.py functions directly
    sys.path.insert(0, str(SCRIPT_DIR))
    import todo
    
    tree = todo.load_data()
    
    # Get past-due items
    past_due = todo.filter_items(tree, "past-due")
    # Get A1000 items (not done)
    a1000 = todo.filter_items(tree, "A1000")
    a1000 = [(p, i, item) for p, i, item in a1000 if not item.get("done")]
    
    # Deduplicate (item might be both past-due and A1000)
    seen = set()
    combined = []
    for p, i, item in past_due + a1000:
        key = (p, item["text"])
        if key not in seen:
            seen.add(key)
            combined.append((p, i, item))
    
    if not combined:
        print("No past-due or A1000 items found. Skipping email.")
        return 0
    
    body = todo.format_filtered_items(combined, "⚠️ Past Due + A1000 Priority")
    subject = f"📋 Todo Priority: Past Due + A1000 — {datetime.now().strftime('%Y-%m-%d')}"
    todo.send_email(subject, body, to_addr)
    return 0

def cmd_day_tagged(to_addr=DEFAULT_TO):
    """Send items tagged with today's day name (Monday, Tuesday, etc.)."""
    today = datetime.now().strftime("%A")  # "Monday", "Tuesday", etc.
    print(f"📅 Sending {today}-tagged items to {to_addr}...")
    return run_todo_cmd(["email-filtered", today, to_addr])

def cmd_weekend_tagged(to_addr=DEFAULT_TO):
    """Send items tagged Saturday, Sunday, or Weekend."""
    print(f"🌴 Sending weekend-tagged items to {to_addr}...")
    return run_todo_cmd(["email-filtered", "Weekend", to_addr])

# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    to_addr = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TO

    if cmd == "full-list":
        sys.exit(cmd_full_list(to_addr))
    elif cmd == "daily-priority":
        sys.exit(cmd_daily_priority(to_addr))
    elif cmd == "day-tagged":
        sys.exit(cmd_day_tagged(to_addr))
    elif cmd == "weekend-tagged":
        sys.exit(cmd_weekend_tagged(to_addr))
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)