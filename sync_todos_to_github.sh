#!/usr/bin/env bash
# ============================================================================
# sync_todos_to_github.sh
# Copies the three agent JSONs into the local todo-data repo clone and pushes
# to GitHub if anything changed. Run from cron on Pi2.
#
# Safe to run every N minutes: if nothing changed, it does nothing and exits.
# ============================================================================
set -uo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
REPO_DIR="$HOME/github/todo-data"
BRANCH="main"
LOG="$HOME/.openclaw/todo-sync.log"

# source file on disk  ->  filename inside the repo (keep the same names)
declare -A SOURCES=(
  ["$HOME/.openclaw/workspace/todos.json"]="todos.json"
  ["$HOME/.openclaw/workspace-realestate/properties.json"]="properties.json"
  ["$HOME/.openclaw/workspace-eternalquest/eternalquest-todos.json"]="eternalquest-todos.json"
)

# ── Helpers ─────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# ── Main ────────────────────────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
  log "ERROR: $REPO_DIR is not a git repo. Clone todo-data there first."
  exit 1
fi

copied=()
for src in "${!SOURCES[@]}"; do
  dest="${SOURCES[$src]}"
  if [ -f "$src" ]; then
    cp -f "$src" "$REPO_DIR/$dest"
    copied+=("$dest")
  else
    log "WARN: source missing, skipping: $src"
  fi
done

cd "$REPO_DIR" || { log "ERROR: cannot cd to $REPO_DIR"; exit 1; }

# Anything actually changed?
if [ -z "$(git status --porcelain)" ]; then
  # Nothing to do — stay quiet (don't spam the log every run)
  exit 0
fi

git add -A
git commit -m "todo sync $(date '+%Y-%m-%d %H:%M:%S') [${copied[*]}]" >> "$LOG" 2>&1

if git push origin "$BRANCH" >> "$LOG" 2>&1; then
  log "pushed: ${copied[*]}"
else
  # Push failed (network/auth). The commit is safe locally; next run retries.
  log "ERROR: push failed — commit is local, will retry next run"
  exit 1
fi