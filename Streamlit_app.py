"""
TodoTree — read-only Streamlit viewer (multi-agent).

Pulls JSON snapshots from a PRIVATE GitHub repo using a token stored in
Streamlit secrets, and renders them read-only. A selector switches between
the three agents; "Main" is the default.

  Reading at work  -> this app (public HTTPS / 443, gets through the firewall)
  Editing anywhere -> Telegram bots or the home web UI

SECURITY — READ THIS:
  Streamlit Community Cloud apps are PUBLIC BY DEFAULT. A private repo behind a
  public app means this data is readable by anyone with the URL. This board
  contains ticket numbers and employee identifiers, and the Real Estate data is
  SHARED WITH NISHA. You MUST enable Streamlit viewer authentication
  (App settings -> Sharing -> "Only specific people can view this app") and
  restrict it to the right Google account(s). Do not deploy publicly without it.

secrets.toml (Streamlit Cloud -> App settings -> Secrets):
  github_token  = "github_pat_xxx"      # fine-grained PAT, READ-ONLY, this repo only
  github_repo   = "rchak007/todo-data"
  github_branch = "main"
"""

import base64
import json
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(page_title="TodoTree", page_icon="🌳", layout="wide")

# ─── Config ─────────────────────────────────────────────────────────────────

GH_TOKEN = st.secrets.get("github_token", "")
GH_REPO = st.secrets.get("github_repo", "")
GH_BRANCH = st.secrets.get("github_branch", "main")

# label shown in selector -> filename in the repo
AGENTS = {
    "🗂️ Main": "todos.json",
    "🏠 Real Estate": "realestate.json",
    "🕉️ Self-Realization": "eternalquest.json",
}


@st.cache_data(ttl=60)
def fetch_json(repo_file: str):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{repo_file}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, params={"ref": GH_BRANCH}, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    data = json.loads(raw)
    if "nodes" not in data and "categories" in data:
        data = {"nodes": data["categories"]}
    return data


# ─── Tree rendering (todos.json / eternalquest shape) ────────────────────────

def count_items(node):
    total = done = 0
    for it in node.get("items", []):
        total += 1
        if it.get("done"):
            done += 1
    for child in (node.get("children") or {}).values():
        t, d = count_items(child)
        total += t
        done += d
    return total, done


def total_stats(nodes):
    total = done = folders = 0
    def walk(obj):
        nonlocal total, done, folders
        for node in obj.values():
            folders += 1
            for it in node.get("items", []):
                total += 1
                if it.get("done"):
                    done += 1
            if node.get("children"):
                walk(node["children"])
    walk(nodes)
    return total, done, total - done, folders


def render_node(name, node, depth=0):
    total, done = count_items(node)
    badge = f"  `{done}/{total}`" if total else ""
    with st.expander(f"📁 **{name}**{badge}", expanded=(depth == 0)):
        for it in node.get("items", []):
            check = "✅" if it.get("done") else "⬜"
            line = f"{check} `#{it.get('id','')}` {it.get('text','')}"
            st.markdown(f"~~{line}~~" if it.get("done") else line)
        for child_name in sorted(node.get("children", {}).keys()):
            render_node(child_name, node["children"][child_name], depth + 1)


def render_tree(data):
    nodes = data.get("nodes", {})
    total, done, pending, folders = total_stats(nodes)
    m1, m2, m3 = st.columns(3)
    m1.metric("Open", pending)
    m2.metric("Done", done)
    m3.metric("Folders", folders)
    st.divider()
    if not nodes:
        st.info("No items yet.")
        return
    for name in sorted(nodes.keys()):
        render_node(name, nodes[name])


# ─── Fallback rendering (unknown shape, e.g. properties.json) ────────────────

def render_generic(data):
    """For files that aren't the node/children/items tree — show readably."""
    st.info("This file isn't in the standard tree format — showing raw structure.")
    if isinstance(data, list):
        st.caption(f"{len(data)} records")
        for i, rec in enumerate(data):
            label = ""
            if isinstance(rec, dict):
                label = rec.get("name") or rec.get("address") or rec.get("title") or f"Record {i+1}"
            with st.expander(str(label) or f"Record {i+1}"):
                st.json(rec)
    elif isinstance(data, dict):
        for key, val in data.items():
            with st.expander(str(key)):
                st.json(val)
    else:
        st.json(data)


# ─── UI ─────────────────────────────────────────────────────────────────────

st.title("🌳 TodoTree")
st.caption("Read-only viewer · edits via Telegram or home UI")

if not GH_TOKEN or not GH_REPO:
    st.error("Missing secrets. Set `github_token` and `github_repo` in App settings → Secrets.")
    st.stop()

top = st.columns([3, 1])
with top[0]:
    choice = st.radio("Agent", list(AGENTS.keys()), horizontal=True, label_visibility="collapsed")
with top[1]:
    if st.button("↻ Refresh"):
        st.cache_data.clear()
        st.rerun()

repo_file = AGENTS[choice]

try:
    data = fetch_json(repo_file)
except requests.HTTPError as e:
    code = e.response.status_code
    if code == 404:
        st.warning(f"`{repo_file}` not found in the repo yet — that agent may not have synced.")
    else:
        st.error(f"GitHub fetch failed: {code}. Check the token/repo.")
    st.stop()
except Exception as e:
    st.error(f"Could not load `{repo_file}`: {e}")
    st.stop()

st.caption(f"Showing **{choice}** · loaded {datetime.now():%Y-%m-%d %H:%M:%S}")

# Render as a tree if it looks like one, otherwise fall back gracefully.
if isinstance(data, dict) and "nodes" in data:
    render_tree(data)
else:
    render_generic(data)