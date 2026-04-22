#!/bin/bash
# setup-todo-email.sh — Set up email and cron for todo agent
#
# Run this on the Pi after deploying the updated todo-manager skill:
#   bash ~/github/openClawAiAgents/setup-todo-email.sh

set -e

SKILL_DIR="$HOME/.openclaw/workspace/skills/todo-manager/scripts"
TODO_PY="$SKILL_DIR/todo.py"
CRON_PY="$SKILL_DIR/todo-cron.py"
TO_EMAIL="rchak1@aol.com"

echo "═══════════════════════════════════════════════"
echo "  Todo Agent — Email & Cron Setup"
echo "═══════════════════════════════════════════════"
echo ""

# ── Step 1: Check GMAIL_APP_PASSWORD ──────────────────────────────
echo "1️⃣  Checking GMAIL_APP_PASSWORD..."
if [ -z "$GMAIL_APP_PASSWORD" ]; then
    echo "   ❌ GMAIL_APP_PASSWORD not set!"
    echo "   It should already be in ~/.bashrc from the realestate setup."
    echo "   Run: source ~/.bashrc"
    echo "   Then re-run this script."
    exit 1
fi
echo "   ✅ GMAIL_APP_PASSWORD is set"
echo ""

# ── Step 2: Set email config ─────────────────────────────────────
echo "2️⃣  Setting email config..."
python3 "$TODO_PY" config-set chuck_email "$TO_EMAIL"
python3 "$TODO_PY" config-set gmail_address "selfrealizationpy@gmail.com"
echo ""
python3 "$TODO_PY" config-show
echo ""

# ── Step 3: Test email ────────────────────────────────────────────
echo "3️⃣  Send test email? (y/n)"
read -r REPLY
if [ "$REPLY" = "y" ]; then
    python3 "$TODO_PY" email "Todo Agent Test ✅" "This is a test email from your Yukteshwar todo agent. If you're reading this, email is working!" "$TO_EMAIL"
    echo ""
fi

# ── Step 4: Install cron jobs ─────────────────────────────────────
echo "4️⃣  Installing cron jobs..."

# Build cron entries
# Note: cron doesn't load .bashrc, so we source env vars inline
CRON_PREFIX="GMAIL_APP_PASSWORD='$GMAIL_APP_PASSWORD' PYTHONPATH='$SKILL_DIR'"

# Remove any existing todo-cron entries
crontab -l 2>/dev/null | grep -v "todo-cron.py" > /tmp/cron_clean 2>/dev/null || true

# Add new entries
cat >> /tmp/cron_clean << CRON

# ── Todo Agent Scheduled Emails ──────────────────────────────────
# Monday 9:00 AM — Full todo list
0 9 * * 1 $CRON_PREFIX python3 $CRON_PY full-list $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Daily 9:15 AM — Past-due + A1000 priority items
15 9 * * * $CRON_PREFIX python3 $CRON_PY daily-priority $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Monday 9:30 AM — Monday tagged items
30 9 * * 1 $CRON_PREFIX python3 $CRON_PY day-tagged $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Tuesday 9:30 AM — Tuesday tagged items
30 9 * * 2 $CRON_PREFIX python3 $CRON_PY day-tagged $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Friday 9:30 AM — Friday tagged items
30 9 * * 5 $CRON_PREFIX python3 $CRON_PY day-tagged $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Saturday 9:30 AM — Weekend tagged items (Sat/Sun/Weekend)
30 9 * * 6 $CRON_PREFIX python3 $CRON_PY weekend-tagged $TO_EMAIL >> /tmp/todo-cron.log 2>&1

# Sunday 9:30 AM — Weekend tagged items (Sat/Sun/Weekend)
30 9 * * 0 $CRON_PREFIX python3 $CRON_PY weekend-tagged $TO_EMAIL >> /tmp/todo-cron.log 2>&1
CRON

crontab /tmp/cron_clean
rm /tmp/cron_clean

echo "   ✅ Cron jobs installed!"
echo ""
echo "   Verify with: crontab -l"
echo ""

# ── Summary ───────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════════"
echo ""
echo "  📧 Sending from: selfrealizationpy@gmail.com"
echo "  📬 Sending to:   $TO_EMAIL"
echo ""
echo "  ⏰ Schedule:"
echo "  ┌─────────────┬────────┬──────────────────────────────┐"
echo "  │ Day         │ Time   │ What                         │"
echo "  ├─────────────┼────────┼──────────────────────────────┤"
echo "  │ Monday      │ 9:00   │ Full todo list               │"
echo "  │ Every day   │ 9:15   │ Past-due + A1000 items       │"
echo "  │ Monday      │ 9:30   │ Monday-tagged items          │"
echo "  │ Tuesday     │ 9:30   │ Tuesday-tagged items         │"
echo "  │ Friday      │ 9:30   │ Friday-tagged items          │"
echo "  │ Saturday    │ 9:30   │ Weekend-tagged items         │"
echo "  │ Sunday      │ 9:30   │ Weekend-tagged items         │"
echo "  └─────────────┴────────┴──────────────────────────────┘"
echo ""
echo "  📋 Via Telegram, just say:"
echo "     'email my full todo list'"
echo "     'email me all A1000 items'"
echo "     'email past due items'"
echo ""
echo "  🔍 Logs: tail -f /tmp/todo-cron.log"
echo ""