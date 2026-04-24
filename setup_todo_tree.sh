#!/bin/bash
# ─── Todo Tree Setup ─────────────────────────────────────────────────────────
# Run from: ~/github/openClawAiAgents/
#   bash setup_todo_tree.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

REPO_DIR="$HOME/github/openClawAiAgents"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  🌳 TodoTree — Setup"
echo "  ───────────────────────────"
echo ""

# Verify we're in or can find the repo
if [ ! -f "$REPO_DIR/todo_tree_server.py" ]; then
    echo "  ✗ todo_tree_server.py not found in $REPO_DIR"
    echo "    Make sure you've pushed & pulled the files first."
    exit 1
fi

# 1. Install dependencies
echo "  [1/4] Installing dependencies..."
python3 -m pip install fastapi uvicorn --break-system-packages -q 2>/dev/null || \
python3 -m pip install fastapi uvicorn -q

# 2. Install systemd service
echo "  [2/4] Installing systemd service..."
mkdir -p ~/.config/systemd/user
cp "$REPO_DIR/todo-tree.service" ~/.config/systemd/user/todo-tree.service
systemctl --user daemon-reload

# 3. Start the service
echo "  [3/4] Starting service..."
systemctl --user enable todo-tree
systemctl --user restart todo-tree

# 4. Show access info
echo "  [4/4] Verifying..."
sleep 2

if systemctl --user is-active --quiet todo-tree; then
    KEY_FILE="$HOME/.openclaw/.todo-tree-secret"
    if [ -f "$KEY_FILE" ]; then
        KEY=$(cat "$KEY_FILE")
    else
        # Wait for the server to generate the key
        sleep 2
        KEY=$(cat "$KEY_FILE" 2>/dev/null || echo "CHECK_LOGS")
    fi

    echo ""
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║  ✅  TodoTree is running!                    ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo ""
    echo "  🔗 URL: http://100.77.66.80:8081?key=${KEY}"
    echo ""
    echo "  🔑 Key stored in: ${KEY_FILE}"
    echo ""
    echo "  📋 Commands:"
    echo "     Status:   systemctl --user status todo-tree"
    echo "     Logs:     journalctl --user -u todo-tree -f"
    echo "     Restart:  systemctl --user restart todo-tree"
    echo "     Stop:     systemctl --user stop todo-tree"
    echo ""
    echo "  💡 After git pull, just run:"
    echo "     systemctl --user restart todo-tree"
    echo ""
else
    echo ""
    echo "  ✗ Service failed to start. Check logs:"
    echo "    journalctl --user -u todo-tree --no-pager -n 20"
    echo ""
fi