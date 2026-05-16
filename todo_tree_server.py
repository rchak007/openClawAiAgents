#!/usr/bin/env python3
"""
TodoTree Dashboard — Read-only Notion-style tree view of todos.json
Deploy from: ~/github/openClawAiAgents/
Reads:      ~/.openclaw/workspace/todos.json
Tag config: ~/.openclaw/workspace/tag_config.json (auto-created on first run)
Access:     http://100.77.66.80:8081?key=YOUR_KEY

Write path stays Telegram bots. This is the calm read-only window.

Design philosophy:
  • Notion toggle tree as the centerpiece — click ▸ to expand/collapse folders
  • Streamlit-style sidebar with radio-button smart views
  • Pale tinted tag pills (not loud caps-on-color)
  • Indentation guide lines do the structural work
  • Tag config lives in a sibling JSON file — edit it, refresh, no restart
"""

import json
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse
import uvicorn

# ─── Config ───────────────────────────────────────────────────────────────────

TODO_FILE = os.environ.get(
    "TODO_FILE",
    os.path.expanduser("~/.openclaw/workspace/todos.json")
)
TAG_CONFIG_FILE = os.environ.get(
    "TAG_CONFIG_FILE",
    os.path.expanduser("~/.openclaw/workspace/tag_config.json")
)

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
        print(f"[Dashboard] Generated new secret key: {SECRET_KEY}")

# Default tag config — written on first run if file is missing.
# Edit the file directly to add/recolor tags; no restart needed (just refresh in browser).
# Available colors: red, teal, purple, blue, amber, green, pink, gray
DEFAULT_TAG_CONFIG = {
    "URGENT":   {"color": "red",    "aliases": ["ASAP", "CRITICAL", "urgent", "asap"]},
    "HABIT":    {"color": "teal",   "aliases": ["DAILY", "WEEKLY", "habit", "daily", "weekly"]},
    "GOAL":     {"color": "purple", "aliases": ["MILESTONE", "goal", "milestone"]},
    "Night":    {"color": "blue",   "aliases": ["night", "NIGHT", "evening", "EVENING"]},
    "Weekend":  {"color": "amber",  "aliases": ["weekend", "WEEKEND", "Sat", "Sun"]},
    "Morning":  {"color": "green",  "aliases": ["morning", "MORNING", "AM"]},
}

app = FastAPI(title="TodoTree Dashboard")

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

def load_tag_config() -> dict:
    if not os.path.exists(TAG_CONFIG_FILE):
        os.makedirs(os.path.dirname(TAG_CONFIG_FILE), exist_ok=True)
        with open(TAG_CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_TAG_CONFIG, f, indent=2)
        print(f"[Dashboard] Wrote default tag config to {TAG_CONFIG_FILE}")
        return DEFAULT_TAG_CONFIG
    try:
        with open(TAG_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Dashboard] Tag config load error: {e}; using defaults")
        return DEFAULT_TAG_CONFIG

def file_mtime(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")

def flatten(nodes: dict, path: list = None) -> list[dict]:
    """Flatten the tree into a list of items with breadcrumb paths."""
    if path is None: path = []
    out = []
    for name, node in (nodes or {}).items():
        cur = path + [name]
        for item in (node.get("items") or []):
            out.append({
                "id":      item.get("id"),
                "text":    item.get("text", ""),
                "done":    bool(item.get("done", False)),
                "created": item.get("created", ""),
                "path":    cur,
            })
        out.extend(flatten(node.get("children") or {}, cur))
    return out

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/data")
async def get_data(key: str = Depends(verify_key)):
    """Single endpoint: tree + flat items + tag config + meta."""
    data = load_todos()
    tags = load_tag_config()
    items = flatten(data.get("nodes") or {})
    return {
        "tree":       data.get("nodes", {}),
        "items":      items,
        "tag_config": tags,
        "meta": {
            "todo_mtime": file_mtime(TODO_FILE),
            "tag_mtime":  file_mtime(TAG_CONFIG_FILE),
            "total":      len(items),
            "open":       sum(1 for i in items if not i["done"]),
            "done":       sum(1 for i in items if i["done"]),
        }
    }

# ─── Frontend ─────────────────────────────────────────────────────────────────

FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TodoTree</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   Streamlit-clean chrome + Notion toggle tree
   Light theme (Notion-style), with dark mode support.
   ═══════════════════════════════════════════════════════════════════════════ */

:root {
  --bg-main: #FFFFFF;
  --bg-sidebar: #F0F2F6;
  --bg-secondary: #F0F2F6;
  --bg-hover: #F7F8FA;
  --text-main: #31333F;
  --text-secondary: #555867;
  --text-faded: #808495;
  --border: #E4E5EB;
  --border-light: #F0F0F2;
  --accent: #FF4B4B;
  --accent-soft: rgba(255, 75, 75, 0.10);
  --link: #0068C9;
  --radius: 6px;

  /* Pale Notion-style tag swatches */
  --tag-red-bg:    #FCE9E9; --tag-red-fg:    #B33A3A;
  --tag-teal-bg:   #E0F2EE; --tag-teal-fg:   #1D6B5F;
  --tag-purple-bg: #ECE5F7; --tag-purple-fg: #5E3FAB;
  --tag-blue-bg:   #E1ECFA; --tag-blue-fg:   #2B5FA0;
  --tag-amber-bg:  #FAEDD0; --tag-amber-fg:  #8B6A14;
  --tag-green-bg:  #DDF0E0; --tag-green-fg:  #1F7035;
  --tag-pink-bg:   #FAE3EC; --tag-pink-fg:   #A6336A;
  --tag-gray-bg:   #ECEDF0; --tag-gray-fg:   #555867;
  --tag-orange-bg: #FCE5D0; --tag-orange-fg: #A55A1D;
}

[data-theme="dark"] {
  --bg-main: #1A1A1A;
  --bg-sidebar: #232425;
  --bg-secondary: #2A2B2D;
  --bg-hover: #2D2E30;
  --text-main: #E8E8E8;
  --text-secondary: #B0B0B0;
  --text-faded: #888A90;
  --border: #3A3B3D;
  --border-light: #2D2E30;
  --accent: #FF6B6B;
  --accent-soft: rgba(255, 107, 107, 0.15);

  --tag-red-bg:    #4A1F1F; --tag-red-fg:    #F8A6A6;
  --tag-teal-bg:   #133634; --tag-teal-fg:   #7FD4C5;
  --tag-purple-bg: #2C1F4A; --tag-purple-fg: #C4ADF0;
  --tag-blue-bg:   #1A2F4A; --tag-blue-fg:   #9CBEEC;
  --tag-amber-bg:  #3A2F0F; --tag-amber-fg:  #F0CC72;
  --tag-green-bg:  #163320; --tag-green-fg:  #7DD495;
  --tag-pink-bg:   #3F1F2D; --tag-pink-fg:   #ECA0BE;
  --tag-gray-bg:   #2D2E30; --tag-gray-fg:   #B0B0B0;
  --tag-orange-bg: #3F2614; --tag-orange-fg: #F0B080;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body { height: 100%; }

body {
  font-family: 'Source Sans 3', -apple-system, sans-serif;
  background: var(--bg-main);
  color: var(--text-main);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

.app {
  display: grid;
  grid-template-columns: 244px 1fr;
  height: 100vh;
}

/* ── Sidebar ──────────────────────────────────────────────── */
.sidebar {
  background: var(--bg-sidebar);
  padding: 24px 16px 32px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
}
.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

.sidebar h1 {
  font-size: 20px; font-weight: 700;
  margin-bottom: 4px; letter-spacing: -0.3px;
  display: flex; align-items: center; gap: 8px;
}
.sidebar .tagline {
  font-size: 12px; color: var(--text-faded);
  margin-bottom: 22px;
}

.sidebar h2 {
  font-size: 13px; font-weight: 600;
  margin: 18px 0 10px;
  color: var(--text-main);
  display: flex; align-items: center; gap: 6px;
}

/* Radio buttons — Streamlit style */
.radio-group { display: flex; flex-direction: column; gap: 0; }
.radio-item {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 4px; cursor: pointer;
  font-size: 14px; color: var(--text-main);
  border-radius: 4px;
}
.radio-item:hover { background: var(--bg-hover); }
.radio-item input { display: none; }
.radio-dot {
  width: 16px; height: 16px;
  border: 1.5px solid #BABCC4;
  border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-main); transition: all 120ms;
}
[data-theme="dark"] .radio-dot { border-color: #5A5C60; background: var(--bg-sidebar); }
.radio-item.active .radio-dot { border-color: var(--accent); }
.radio-item.active .radio-dot::after {
  content: ''; width: 8px; height: 8px;
  background: var(--accent); border-radius: 50%;
}
.radio-item.active { font-weight: 600; }
.radio-item .count {
  margin-left: auto;
  font-size: 11.5px; color: var(--text-faded);
  font-weight: 400;
}
.radio-item.active .count { color: var(--accent); }

.sidebar-caption {
  font-size: 11px; color: var(--text-faded);
  margin-top: 22px; padding: 10px;
  background: var(--bg-main); border-radius: var(--radius);
  font-family: 'Courier New', monospace;
  word-break: break-all;
  line-height: 1.5;
  border: 1px solid var(--border-light);
}
[data-theme="dark"] .sidebar-caption { background: var(--bg-secondary); }

.theme-toggle {
  margin-top: 16px;
  width: 100%;
  padding: 8px;
  background: var(--bg-main);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  font: inherit; font-size: 13px;
  color: var(--text-secondary);
}
.theme-toggle:hover { background: var(--bg-hover); color: var(--text-main); }
[data-theme="dark"] .theme-toggle { background: var(--bg-secondary); }

/* ── Main ─────────────────────────────────────────────────── */
.main {
  padding: 36px 56px 60px;
  max-width: 1100px;
  overflow-y: auto;
  height: 100vh;
}
.main::-webkit-scrollbar { width: 8px; }
.main::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.page-head {
  display: flex; justify-content: space-between; align-items: flex-end;
  margin-bottom: 28px;
}
h1.page-title {
  font-size: 34px; font-weight: 700;
  letter-spacing: -1px; line-height: 1.1;
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 4px;
}
.page-desc {
  color: var(--text-secondary); font-size: 14.5px;
}
.refresh-btn {
  font-family: inherit; font-size: 13px; font-weight: 500;
  padding: 8px 14px;
  background: var(--bg-main);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer; color: var(--text-main);
  display: inline-flex; align-items: center; gap: 6px;
  transition: all 80ms;
}
.refresh-btn:hover { background: var(--bg-hover); border-color: #BABCC4; }
.refresh-btn.spin .ico { animation: spin 600ms linear; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

/* KPI metrics — Streamlit's st.metric */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-bottom: 32px;
}
.metric {
  padding: 6px 0;
}
.metric .label {
  font-size: 13.5px; color: var(--text-secondary);
  font-weight: 400; margin-bottom: 4px;
}
.metric .value {
  font-size: 34px; font-weight: 600;
  letter-spacing: -1.5px; color: var(--text-main);
  line-height: 1;
}
.metric.urgent .value { color: var(--accent); }
.metric.done .value { color: #2D8A56; }

/* Search row */
.search-row {
  display: flex; gap: 12px; align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.search-input {
  flex: 1; min-width: 260px; max-width: 520px;
  padding: 10px 14px;
  background: var(--bg-main);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font: inherit; font-size: 14px;
  color: var(--text-main);
  outline: none;
  transition: all 80ms;
}
.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.search-input::placeholder { color: var(--text-faded); }
.search-meta {
  font-size: 13px; color: var(--text-faded);
  white-space: nowrap;
}
.expand-controls {
  display: flex; gap: 4px; margin-left: auto;
}
.btn-text {
  background: none; border: none;
  font: inherit; font-size: 13px;
  color: var(--text-secondary); cursor: pointer;
  padding: 6px 10px; border-radius: var(--radius);
}
.btn-text:hover { background: var(--bg-secondary); color: var(--text-main); }

/* ── NOTION-STYLE TOGGLE TREE ─────────────────────────────── */
.tree-section-title {
  font-size: 16px; font-weight: 600;
  margin-bottom: 12px; letter-spacing: -0.2px;
  display: flex; align-items: baseline; gap: 10px;
}
.tree-section-title .count {
  font-size: 12.5px; font-weight: 400;
  color: var(--text-faded);
}

.tree { padding: 0; }

.tree-node-row {
  display: flex; align-items: center; gap: 4px;
  padding: 5px 8px 5px 4px;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  transition: background 80ms;
}
.tree-node-row:hover { background: var(--bg-hover); }
.tree-toggle {
  width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--text-faded);
  font-size: 9px;
  transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 3px;
}
.tree-toggle:hover { background: var(--border-light); color: var(--text-main); }
.tree-toggle.empty { visibility: hidden; }
.tree-node.open > .tree-node-row > .tree-toggle { transform: rotate(90deg); }
.tree-folder-icon {
  font-size: 14px; flex-shrink: 0;
  width: 18px; text-align: center;
  opacity: 0.85;
}
.tree-node-label {
  font-size: 14.5px; font-weight: 600;
  color: var(--text-main);
  flex: 1; letter-spacing: -0.1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tree-node-count {
  font-size: 11.5px; color: var(--text-faded);
  font-weight: 500;
  padding: 1px 8px;
  background: var(--bg-secondary);
  border-radius: 10px;
  min-width: 28px; text-align: center;
}

.tree-node-children {
  margin-left: 13px;
  padding-left: 14px;
  border-left: 1.5px solid var(--border);
  display: none;
}
.tree-node.open > .tree-node-children { display: block; }

/* Items — Notion-style rows */
.tree-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 5px 8px 5px 26px;
  border-radius: 4px;
  font-size: 14px;
  transition: background 80ms;
}
.tree-item:hover { background: var(--bg-hover); }
.tree-item-bullet {
  color: var(--text-faded);
  margin-top: 8px; line-height: 1;
  font-size: 6px;
  flex-shrink: 0;
}
.tree-item-id {
  font-family: 'Courier New', monospace;
  font-size: 11px; color: var(--text-faded);
  margin-top: 2px;
  min-width: 26px;
  flex-shrink: 0;
}
.tree-item-text {
  color: var(--text-main); line-height: 1.5;
  flex: 1;
  word-break: break-word;
}
.tree-item.done .tree-item-text {
  text-decoration: line-through;
  color: var(--text-faded);
}
.tree-item-tags {
  display: inline-flex; flex-wrap: wrap; gap: 4px;
  margin-left: 8px;
  vertical-align: middle;
}
.tag-pill {
  display: inline-block;
  font-size: 11px; font-weight: 500;
  padding: 1px 8px;
  border-radius: 3px;
  line-height: 1.5;
  white-space: nowrap;
}
.tag-pill.red    { background: var(--tag-red-bg);    color: var(--tag-red-fg); }
.tag-pill.teal   { background: var(--tag-teal-bg);   color: var(--tag-teal-fg); }
.tag-pill.purple { background: var(--tag-purple-bg); color: var(--tag-purple-fg); }
.tag-pill.blue   { background: var(--tag-blue-bg);   color: var(--tag-blue-fg); }
.tag-pill.amber  { background: var(--tag-amber-bg);  color: var(--tag-amber-fg); }
.tag-pill.green  { background: var(--tag-green-bg);  color: var(--tag-green-fg); }
.tag-pill.pink   { background: var(--tag-pink-bg);   color: var(--tag-pink-fg); }
.tag-pill.gray   { background: var(--tag-gray-bg);   color: var(--tag-gray-fg); }
.tag-pill.orange { background: var(--tag-orange-bg); color: var(--tag-orange-fg); }

.tree-item-date {
  font-family: 'Courier New', monospace;
  font-size: 11px; color: var(--text-faded);
  margin-top: 2px; margin-left: 6px;
  white-space: nowrap;
  opacity: 0; transition: opacity 80ms;
}
.tree-item:hover .tree-item-date { opacity: 1; }

/* Search dimming + highlight */
.tree-node.dim > .tree-node-row { opacity: 0.35; }
.tree-item.dim { opacity: 0.25; }
mark.hl {
  background: var(--accent-soft); color: var(--accent);
  padding: 0 2px; border-radius: 2px; font-weight: 600;
}

/* Empty / loading */
.loading, .empty-state {
  padding: 60px 20px;
  color: var(--text-faded);
  text-align: center;
}
.empty-state .ico { font-size: 40px; margin-bottom: 12px; opacity: 0.5; }
.empty-state h3 {
  font-size: 16px; font-weight: 600;
  color: var(--text-secondary); margin-bottom: 4px;
}

/* Responsive */
@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  .sidebar { padding: 16px; max-height: 50vh; overflow-y: auto; }
  .main { padding: 24px 20px 60px; height: auto; }
  .metrics-row { grid-template-columns: repeat(2, 1fr); }
  h1.page-title { font-size: 26px; }
}
</style>
</head>
<body>
<div id="app" class="app">
  <div class="loading">Loading...</div>
</div>

<script>
// ─── State ──────────────────────────────────────────────────────────────────
const API_KEY = new URLSearchParams(location.search).get('key') || '';
const STATE = {
  data: { tree: {}, items: [], tag_config: {}, meta: {} },
  view: 'overview',          // overview | urgent | habits | goals | week | done | folder:<name>
  search: '',
  openNodes: new Set(),      // path-keys of open folders
  loading: true,
  initialized: false,
  theme: (window.name === 'dark' || window.name === 'light')
           ? window.name
           : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
};
document.documentElement.setAttribute('data-theme', STATE.theme);

// ─── API ────────────────────────────────────────────────────────────────────
async function fetchData() {
  try {
    const res = await fetch('/api/data?key=' + encodeURIComponent(API_KEY));
    if (!res.ok) throw new Error('HTTP ' + res.status);
    STATE.data = await res.json();
    // First load: open top-level folders only
    if (!STATE.initialized) {
      Object.keys(STATE.data.tree || {}).forEach(name => STATE.openNodes.add(name));
      STATE.initialized = true;
    }
  } catch (e) {
    console.error('Fetch failed:', e);
    STATE.data = { tree: {}, items: [], tag_config: {}, meta: {}, error: e.message };
  }
  STATE.loading = false;
  render();
}

// ─── Helpers ────────────────────────────────────────────────────────────────
function esc(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }
function pathKey(p) { return p.join('\x00'); }

function buildTagIndex() {
  const idx = {};
  Object.entries(STATE.data.tag_config || {}).forEach(([canonical, info]) => {
    idx[canonical.toLowerCase()] = { canonical, color: info.color || 'orange' };
    (info.aliases || []).forEach(a => {
      idx[a.toLowerCase()] = { canonical, color: info.color || 'orange' };
    });
  });
  return idx;
}

function detectTags(text) {
  if (!text) return [];
  const idx = buildTagIndex();
  const found = new Set();
  const out = [];
  Object.keys(idx).forEach(key => {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('(?:^|[^A-Za-z0-9_])(' + escaped + ')(?=$|[^A-Za-z0-9_])', 'i');
    if (re.test(text)) {
      const info = idx[key];
      if (!found.has(info.canonical)) {
        found.add(info.canonical);
        out.push({ name: info.canonical, color: info.color });
      }
    }
  });
  // Fallback: ALL-CAPS / CAP+digit tokens not in config (e.g. A1000)
  const caps = text.match(/\b[A-Z][A-Z0-9]{1,9}\b/g) || [];
  caps.forEach(t => {
    if (!found.has(t)) {
      const lc = t.toLowerCase();
      if (idx[lc]) {
        const info = idx[lc];
        if (!found.has(info.canonical)) { found.add(info.canonical); out.push({ name: info.canonical, color: info.color }); }
      } else {
        found.add(t); out.push({ name: t, color: 'gray' });
      }
    }
  });
  return out;
}

function itemTagNames(item) { return detectTags(item.text).map(t => t.name); }

function parseCreated(s) {
  if (!s) return null;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}):(\d{2}))?/);
  if (!m) return null;
  return new Date(+m[1], +m[2]-1, +m[3], +(m[4]||0), +(m[5]||0));
}

function highlight(text) {
  if (!STATE.search) return esc(text);
  const escaped = esc(text);
  const q = STATE.search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(new RegExp('(' + q + ')', 'gi'), '<mark class="hl">$1</mark>');
}

// Strip text of tag tokens so they don't appear twice (once in text, once as pill)
function stripTagsFromText(text) {
  if (!text) return '';
  const idx = buildTagIndex();
  let out = text;
  Object.keys(idx).forEach(key => {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    out = out.replace(new RegExp('(^|[^A-Za-z0-9_])(' + escaped + ')(?=$|[^A-Za-z0-9_])', 'gi'), '$1');
  });
  // Strip leftover all-caps tokens too
  out = out.replace(/\b[A-Z][A-Z0-9]{1,9}\b/g, '');
  return out.replace(/\s{2,}/g, ' ').trim();
}

// ─── View filter logic ──────────────────────────────────────────────────────
function itemMatchesView(item) {
  if (STATE.view === 'overview') return !item.done;
  if (STATE.view === 'urgent')   return !item.done && itemTagNames(item).includes('URGENT');
  if (STATE.view === 'habits')   return !item.done && itemTagNames(item).includes('HABIT');
  if (STATE.view === 'goals')    return !item.done && itemTagNames(item).includes('GOAL');
  if (STATE.view === 'week') {
    if (item.done) return false;
    const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 7);
    const d = parseCreated(item.created);
    return d && d >= cutoff;
  }
  if (STATE.view === 'done') return item.done;
  if (STATE.view.startsWith('folder:')) {
    const target = STATE.view.slice(7);
    return item.path[0] === target;
  }
  return true;
}

function itemMatchesSearch(item) {
  if (!STATE.search) return true;
  const q = STATE.search.toLowerCase();
  return item.text.toLowerCase().includes(q) || item.path.some(p => p.toLowerCase().includes(q));
}

// ─── Stats ──────────────────────────────────────────────────────────────────
function computeStats() {
  const items = STATE.data.items || [];
  const open = items.filter(i => !i.done);
  const urgent = open.filter(i => itemTagNames(i).includes('URGENT')).length;
  const habits = open.filter(i => itemTagNames(i).includes('HABIT')).length;
  const goals  = open.filter(i => itemTagNames(i).includes('GOAL')).length;
  const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 7);
  const week = open.filter(i => { const d = parseCreated(i.created); return d && d >= cutoff; }).length;
  return { urgent, habits, goals, week };
}

function topFolderCounts() {
  const tree = STATE.data.tree || {};
  return Object.keys(tree).sort((a,b) => a.localeCompare(b)).map(name => ({
    name,
    n: (STATE.data.items || []).filter(i => i.path[0] === name && !i.done).length
  }));
}

// ─── Tree filtering for view + search ───────────────────────────────────────
/*
  For each node, recursively decide:
    - showItems: items in this node that pass view+search filter
    - showChildren: subtree nodes that have any visible content
    - hasMatch: any item or descendant matches *search* specifically (drives auto-expand & dim)
    - hasVisible: anything is shown at all (drives whether to render the node)
*/
function buildVisibility(tree) {
  const result = {};
  function walk(nodes, path) {
    Object.entries(nodes || {}).forEach(([name, node]) => {
      const cur = path.concat([name]);
      const key = pathKey(cur);
      const items = (node.items || []).filter(it => {
        const itemObj = { ...it, path: cur };
        return itemMatchesView(itemObj) && itemMatchesSearch(itemObj);
      });
      walk(node.children || {}, cur);
      const childKeys = Object.keys(node.children || {}).map(n => pathKey(cur.concat([n])));
      const childVisible = childKeys.some(k => result[k] && result[k].hasVisible);
      const childHasMatch = childKeys.some(k => result[k] && result[k].hasMatch);
      const nameMatchesSearch = STATE.search
        ? name.toLowerCase().includes(STATE.search.toLowerCase())
        : false;
      const hasMatch = nameMatchesSearch || items.length > 0 || childHasMatch;
      const hasVisible = items.length > 0 || childVisible || (STATE.search ? hasMatch : true);
      result[key] = { items, hasMatch, hasVisible, nameMatchesSearch };
    });
  }
  walk(tree, []);
  return result;
}

// ─── Render: tag pill ───────────────────────────────────────────────────────
function renderTags(item) {
  const tags = detectTags(item.text);
  if (!tags.length) return '';
  return '<span class="tree-item-tags">' +
    tags.map(t => `<span class="tag-pill ${esc(t.color)}">${esc(t.name)}</span>`).join('') +
    '</span>';
}

// ─── Render: a single item ──────────────────────────────────────────────────
function renderItem(item, path, dim) {
  const fullItem = { ...item, path };
  const cleaned = stripTagsFromText(item.text);
  return `<div class="tree-item ${item.done?'done':''} ${dim?'dim':''}">
    <span class="tree-item-bullet">●</span>
    <span class="tree-item-id">#${esc(item.id)}</span>
    <span class="tree-item-text">${highlight(cleaned || item.text)}${renderTags(item)}</span>
    <span class="tree-item-date">${esc(item.created || '')}</span>
  </div>`;
}

// ─── Render: a folder node ──────────────────────────────────────────────────
function renderNode(name, node, parentPath, visibility) {
  const path = parentPath.concat([name]);
  const key = pathKey(path);
  const vis = visibility[key];
  if (!vis || !vis.hasVisible) return '';

  // Decide if open: search auto-expands matches; otherwise user state
  let isOpen;
  if (STATE.search) {
    isOpen = vis.hasMatch;
  } else {
    isOpen = STATE.openNodes.has(key);
  }

  // Dim if searching and this branch has no match
  const dim = STATE.search && !vis.hasMatch;

  const hasContent = vis.items.length > 0 || Object.keys(node.children || {}).length > 0;
  const totalCount = countAllOpen(node);

  const childrenHtml = Object.entries(node.children || {})
    .sort(([a],[b]) => a.localeCompare(b))
    .map(([n, c]) => renderNode(n, c, path, visibility))
    .join('');

  const itemsHtml = vis.items
    .sort((a,b) => (a.done?1:0) - (b.done?1:0) || (b.id||0) - (a.id||0))
    .map(it => renderItem(it, path, dim))
    .join('');

  const onclickAttr = hasContent ? `onclick="event.stopPropagation();toggleNode('${esc(key).replace(/'/g,"\\'")}')"` : '';

  return `<div class="tree-node ${isOpen?'open':''} ${dim?'dim':''}" data-key="${esc(key)}">
    <div class="tree-node-row" ${onclickAttr}>
      <span class="tree-toggle ${hasContent?'':'empty'}">▸</span>
      <span class="tree-folder-icon">📁</span>
      <span class="tree-node-label">${highlight(name)}</span>
      ${totalCount > 0 ? `<span class="tree-node-count">${totalCount}</span>` : ''}
    </div>
    <div class="tree-node-children">
      ${itemsHtml}
      ${childrenHtml}
    </div>
  </div>`;
}

// Count open items in this node + descendants (for the folder badge)
function countAllOpen(node) {
  let n = (node.items || []).filter(i => !i.done).length;
  Object.values(node.children || {}).forEach(c => { n += countAllOpen(c); });
  return n;
}

// ─── Render: page ──────────────────────────────────────────────────────────
function viewTitle() {
  if (STATE.view === 'overview') return { ico: '📋', title: 'Overview',   desc: "A bird's-eye view of every open todo across your workspace." };
  if (STATE.view === 'urgent')   return { ico: '🔥', title: 'Urgent',     desc: 'Items tagged URGENT, ASAP, or CRITICAL.' };
  if (STATE.view === 'habits')   return { ico: '🔁', title: 'Habits',     desc: 'Recurring practices and routines.' };
  if (STATE.view === 'goals')    return { ico: '🎯', title: 'Goals',      desc: 'Milestones and longer-term targets.' };
  if (STATE.view === 'week')     return { ico: '📅', title: 'This Week',  desc: 'Everything added in the last 7 days.' };
  if (STATE.view === 'done')     return { ico: '✅', title: 'Completed',  desc: 'Items marked done.' };
  if (STATE.view.startsWith('folder:')) {
    return { ico: '📁', title: STATE.view.slice(7), desc: 'Items in this folder and its subfolders.' };
  }
  return { ico: '·', title: '·', desc: '' };
}

function render() {
  if (STATE.loading && !STATE.data.items?.length) {
    document.getElementById('app').innerHTML = `
      <aside class="sidebar"><h1>🌳 TodoTree</h1><div class="tagline">Read-only dashboard</div></aside>
      <main class="main"><div class="loading">Loading…</div></main>`;
    return;
  }

  const t = viewTitle();
  const m = STATE.data.meta || {};
  const s = computeStats();
  const folders = topFolderCounts();

  // Build a filtered tree view for current state
  const visibility = buildVisibility(STATE.data.tree || {});
  const treeHtml = Object.entries(STATE.data.tree || {})
    .sort(([a],[b]) => a.localeCompare(b))
    .map(([n, c]) => renderNode(n, c, [], visibility))
    .join('');

  // Count matches for search
  const matchCount = STATE.search
    ? (STATE.data.items || []).filter(itemMatchesSearch).length
    : 0;

  const navItems = [
    { id: 'overview', name: 'Overview',   count: m.open ?? 0 },
    { id: 'urgent',   name: 'Urgent',     count: s.urgent },
    { id: 'habits',   name: 'Habits',     count: s.habits },
    { id: 'goals',    name: 'Goals',      count: s.goals },
    { id: 'week',     name: 'This Week',  count: s.week },
    { id: 'done',     name: 'Completed',  count: m.done ?? 0 },
  ];

  document.getElementById('app').innerHTML = `
    <aside class="sidebar">
      <h1>🌳 TodoTree</h1>
      <div class="tagline">Read-only dashboard</div>

      <h2>📂 Smart views</h2>
      <div class="radio-group">
        ${navItems.map(it => `
          <div class="radio-item ${STATE.view===it.id?'active':''}" onclick="setView('${it.id}')">
            <span class="radio-dot"></span>
            <span>${it.name}</span>
            <span class="count">${it.count}</span>
          </div>
        `).join('')}
      </div>

      <h2>📁 Folders</h2>
      <div class="radio-group">
        ${folders.map(f => `
          <div class="radio-item ${STATE.view==='folder:'+f.name?'active':''}" onclick="setView('folder:${esc(f.name).replace(/'/g,"\\'")}')">
            <span class="radio-dot"></span>
            <span>${esc(f.name)}</span>
            <span class="count">${f.n}</span>
          </div>
        `).join('')}
      </div>

      <div class="sidebar-caption">
        ${esc(m.todo_mtime || '—')}<br>
        ${(m.open ?? 0)} open · ${(m.done ?? 0)} done
      </div>

      <button class="theme-toggle" onclick="toggleTheme()">
        ${STATE.theme === 'light' ? '🌙 Dark mode' : '☀️ Light mode'}
      </button>
    </aside>

    <main class="main">
      <div class="page-head">
        <div>
          <h1 class="page-title"><span>${t.ico}</span> ${esc(t.title)}</h1>
          <div class="page-desc">${esc(t.desc)}</div>
        </div>
        <button id="btn-refresh" class="refresh-btn" onclick="refresh()">
          <span class="ico">↻</span> Refresh
        </button>
      </div>

      <div class="metrics-row">
        <div class="metric"><div class="label">Open</div><div class="value">${m.open ?? 0}</div></div>
        <div class="metric urgent"><div class="label">Urgent</div><div class="value">${s.urgent}</div></div>
        <div class="metric"><div class="label">Habits</div><div class="value">${s.habits}</div></div>
        <div class="metric done"><div class="label">Done</div><div class="value">${m.done ?? 0}</div></div>
      </div>

      <div class="search-row">
        <input id="search-input" class="search-input" placeholder="🔍 Search items and folder names..." value="${esc(STATE.search)}" oninput="setSearch(this.value)">
        ${STATE.search ? `<span class="search-meta">${matchCount} match${matchCount===1?'':'es'}</span>` : ''}
        <div class="expand-controls">
          <button class="btn-text" onclick="expandAll()">Expand all</button>
          <button class="btn-text" onclick="collapseAll()">Collapse all</button>
        </div>
      </div>

      <div class="tree">
        ${treeHtml || `<div class="empty-state">
          <div class="ico">🌱</div>
          <h3>Nothing to show</h3>
          <p>Try a different view or clear the search.</p>
        </div>`}
      </div>
    </main>
  `;

  // Restore search focus
  if (STATE.search) {
    const inp = document.getElementById('search-input');
    if (inp) {
      inp.focus();
      inp.setSelectionRange(inp.value.length, inp.value.length);
    }
  }
}

// ─── Actions ────────────────────────────────────────────────────────────────
function setView(v) {
  STATE.view = v;
  // Re-open top-level when switching to a folder view, since user just picked it
  if (v.startsWith('folder:')) {
    STATE.openNodes.add(v.slice(7));
  }
  render();
}
function setSearch(v) {
  STATE.search = v;
  render();
}
function toggleNode(key) {
  if (STATE.openNodes.has(key)) STATE.openNodes.delete(key);
  else STATE.openNodes.add(key);
  render();
}
function expandAll() {
  STATE.search = '';
  // Recursively open every node
  function walk(nodes, path) {
    Object.entries(nodes || {}).forEach(([name, node]) => {
      const cur = path.concat([name]);
      STATE.openNodes.add(pathKey(cur));
      walk(node.children || {}, cur);
    });
  }
  walk(STATE.data.tree || {}, []);
  render();
}
function collapseAll() {
  STATE.search = '';
  STATE.openNodes.clear();
  render();
}
async function refresh() {
  const btn = document.getElementById('btn-refresh');
  if (btn) btn.classList.add('spin');
  STATE.loading = true;
  await fetchData();
  setTimeout(() => { if (btn) btn.classList.remove('spin'); }, 600);
}
function toggleTheme() {
  STATE.theme = STATE.theme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', STATE.theme);
  window.name = STATE.theme;
  render();
}

// Expose for inline handlers
window.setView = setView;
window.setSearch = setSearch;
window.toggleNode = toggleNode;
window.expandAll = expandAll;
window.collapseAll = collapseAll;
window.refresh = refresh;
window.toggleTheme = toggleTheme;

// Boot
fetchData();
</script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TodoTree</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Source Sans 3', -apple-system, sans-serif;
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #FFFFFF; color: #31333F;
}
@media (prefers-color-scheme: dark) {
  body { background: #1A1A1A; color: #E8E8E8; }
  .card { background: #232425; border-color: #3A3B3D; }
  input { background: #2A2B2D; border-color: #3A3B3D; color: #E8E8E8; }
  input:focus { border-color: #FF6B6B; }
  button { background: #FF6B6B; }
  .sub { color: #888A90; }
}
.card {
  background: #fff; border: 1px solid #E4E5EB; border-radius: 10px;
  padding: 40px; width: 360px; text-align: center;
}
.icon { font-size: 40px; margin-bottom: 14px; }
h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 6px; }
.sub { color: #808495; font-size: 14px; margin-bottom: 24px; }
input {
  width: 100%; padding: 11px 14px; border: 1px solid #E4E5EB;
  border-radius: 6px; font-family: inherit; font-size: 14px;
  outline: none; margin-bottom: 12px; transition: all 100ms ease;
  text-align: center; letter-spacing: 2px;
}
input:focus { border-color: #FF4B4B; box-shadow: 0 0 0 3px rgba(255,75,75,0.10); }
button {
  width: 100%; padding: 11px; background: #FF4B4B; border: none;
  border-radius: 6px; color: white; font-family: inherit;
  font-size: 14px; font-weight: 600; cursor: pointer; transition: all 100ms ease;
}
button:hover { background: #E03B3B; }
</style></head><body>
<div class="card">
  <div class="icon">🌳</div>
  <h1>TodoTree</h1>
  <p class="sub">Enter your access key</p>
  <input id="k" type="password" placeholder="••••••••" autofocus onkeydown="if(event.key==='Enter')go()">
  <button onclick="go()">Unlock</button>
</div>
<script>function go(){const k=document.getElementById('k').value;if(k)location.href='/?key='+encodeURIComponent(k);}</script>
</body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index(key: str = Query(default="")):
    if not key or key != SECRET_KEY:
        return HTMLResponse(content=LOGIN_HTML)
    return HTMLResponse(content=FRONTEND_HTML)

if __name__ == "__main__":
    port = int(os.environ.get("TODO_PORT", "8081"))
    print(f"\n  🌳 TodoTree Dashboard (read-only · Notion tree)")
    print(f"  ───────────────────────────")
    print(f"  Todos:      {TODO_FILE}")
    print(f"  Tag config: {TAG_CONFIG_FILE}")
    print(f"  Port:       {port}")
    print(f"  URL:        http://100.77.66.80:{port}?key={SECRET_KEY}")
    print(f"  ───────────────────────────\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")