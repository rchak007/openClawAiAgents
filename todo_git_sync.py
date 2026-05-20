#!/usr/bin/env python3
"""
todo_git_sync.py — Watch multiple agent JSON files and push changes to the
private data repo, each under its own filename.

Covers all three OpenClaw agents:
    main         -> ~/.openclaw/workspace/todos.json                       -> todos.json
    realestate   -> ~/.openclaw/workspace-realestate/properties.json       -> realestate.json
    eternalquest -> ~/.openclaw/workspace-eternalquest/eternalquest-todos.json -> eternalquest.json

Why a watcher (not a save_todos() hook):
  Each JSON is written by TWO independent processes — the web/server side AND
  the OpenClaw Telegram agent. Watching the files on disk catches BOTH writers,
  regardless of which process made the change.

  NOTE: realestate is SHARED WITH NISHA. Pushing it mirrors her data to GitHub
  and Streamlit too — make sure viewer auth includes the right people.

Behaviour:
  - Polls each source file's content hash every POLL_SECONDS.
  - On a real content change, debounces DEBOUNCE_SECONDS, copies into the repo
    under its mapped name, then makes ONE commit for whatever changed and pushes.
  - Push runs here, never in any web request path.

Runs as a systemd --user service.
"""

import hashlib
import os
import shutil
import subprocess
import time
from datetime import datetime

# ─── Sources: (source file on disk) -> (filename inside the repo) ────────────
# Override the source paths via env if your layout differs.

HOME = os.path.expanduser("~")

SOURCES = [
    {
        "label": "main",
        "src": os.environ.get(
            "TODO_FILE",
            f"{HOME}/.openclaw/workspace/todos.json",
        ),
        "repo_name": "todos.json",
    },
    {
        "label": "realestate",
        "src": os.environ.get(
            "REALESTATE_FILE",
            f"{HOME}/.openclaw/workspace-realestate/properties.json",
        ),
        "repo_name": "realestate.json",
    },
    {
        "label": "eternalquest",
        "src": os.environ.get(
            "ETERNALQUEST_FILE",
            f"{HOME}/.openclaw/workspace-eternalquest/eternalquest-todos.json",
        ),
        "repo_name": "eternalquest.json",
    },
]

REPO_DIR = os.environ.get("TODO_DATA_REPO", f"{HOME}/github/todo-data")
GIT_BRANCH = os.environ.get("TODO_DATA_BRANCH", "main")

POLL_SECONDS = float(os.environ.get("TODO_SYNC_POLL", "5"))
DEBOUNCE_SECONDS = float(os.environ.get("TODO_SYNC_DEBOUNCE", "8"))


def log(msg: str):
    print(f"[todo-sync {datetime.now():%H:%M:%S}] {msg}", flush=True)


def file_hash(path: str) -> str:
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", REPO_DIR, *args],
        capture_output=True, text=True, check=check,
    )


def sync_to_repo():
    """Copy every present source into the repo, commit any changes, push once."""
    os.makedirs(REPO_DIR, exist_ok=True)
    copied_labels = []

    for s in SOURCES:
        if not os.path.exists(s["src"]):
            continue  # agent not present / file not created yet — skip silently
        dest = os.path.join(REPO_DIR, s["repo_name"])
        shutil.copy2(s["src"], dest)
        copied_labels.append(s["label"])

    # Anything actually changed in the repo?
    status = git("status", "--porcelain")
    if not status.stdout.strip():
        return False

    git("add", "-A")
    changed = ", ".join(copied_labels) or "data"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    git("commit", "-m", f"update [{changed}] {stamp}")

    pushed = git("push", "origin", GIT_BRANCH, check=False)
    if pushed.returncode != 0:
        log(f"push failed (will retry on next change): {pushed.stderr.strip()}")
        return False

    log(f"pushed: {status.stdout.strip().splitlines()[0]}")
    return True


def main():
    log(f"repo {REPO_DIR} ({GIT_BRANCH})")
    for s in SOURCES:
        present = "ok" if os.path.exists(s["src"]) else "MISSING"
        log(f"  watch {s['label']:12s} -> {s['repo_name']:20s} [{present}] {s['src']}")

    # Track each source's hash independently.
    hashes = {s["label"]: file_hash(s["src"]) for s in SOURCES}

    # Startup: bring the repo current.
    try:
        sync_to_repo()
    except Exception as e:
        log(f"startup sync error: {e}")

    pending_since = None

    while True:
        time.sleep(POLL_SECONDS)
        try:
            changed = False
            for s in SOURCES:
                cur = file_hash(s["src"])
                if cur != hashes[s["label"]]:
                    hashes[s["label"]] = cur
                    changed = True

            if changed:
                # (Re)start the debounce window — collapses a burst into one commit.
                pending_since = time.monotonic()
                continue

            if pending_since is not None:
                if time.monotonic() - pending_since >= DEBOUNCE_SECONDS:
                    pending_since = None
                    sync_to_repo()

        except Exception as e:
            log(f"loop error: {e}")


if __name__ == "__main__":
    main()