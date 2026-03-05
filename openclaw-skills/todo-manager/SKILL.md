---
name: todo-manager
description: "Hierarchical personal todo list manager. Use this skill when the user wants to add tasks, list todos, mark items done, search by tag (like A1000, URGENT), find items by path, clear completed items, or manage the tree. Triggered by: add todo, add task, show my todos, list tasks, mark done, find A1000, search todos, what do I have in Finance, clear completed, add category, create new node."
metadata: {
  "openclaw": {
    "emoji": "📋",
    "requires": {
      "bins": ["python3"]
    }
  }
}
---

# Todo Manager Skill

## Overview
Personal hierarchical todo list stored in `~/.openclaw/workspace/todos.json`.

The tree is **fully fluid and unlimited depth**: the user can write any path on the fly and all missing nodes are created automatically. Never ask the user to pre-create a category, task, or subtask — just create it.

Path structure: **node1 > node2 > node3 > ... > item text**

The last segment of a path is always the item text. Everything before it is the tree path. Example:
- `Personal > Finance > Taxes > 2022 > A1000 file returns` → path is `Personal/Finance/Taxes/2022`, item is `A1000 file returns`
- `Work > ProjectAlpha > A1000 write spec` → path is `Work/ProjectAlpha`, item is `A1000 write spec`
- `Shopping > A1000 buy milk` → path is `Shopping`, item is `A1000 buy milk`

Items support embedded UPPERCASE tags (e.g. `A1000`, `URGENT`, `SP9`) for filtering.

## Data File
Always read/write: `~/.openclaw/workspace/todos.json`

The JSON structure mirrors the tree exactly. Each node is an object with two possible keys:
- `children`: nested nodes (dict of node_name → node_object)
- `items`: list of item objects (leaf content)

```json
{
  "nodes": {
    "Personal": {
      "children": {
        "Finance": {
          "children": {
            "Taxes": {
              "children": {
                "2022": {
                  "items": [
                    {"id": 1, "text": "A1000 file returns", "done": false, "created": "2026-03-03 14:30"}
                  ]
                }
              }
            }
          }
        }
      }
    }
  }
}
```

If the file doesn't exist, create it: `{"nodes": {}}`

## Item Schema
```json
{"id": 1, "text": "A1000 File 2022 tax returns", "done": false, "created": "2026-03-03 14:30"}
```
Tags are UPPERCASE words extracted from item text: regex `\b[A-Z][A-Z0-9]{1,9}\b`

## Operations

### ADD an item — FLUID PATH
The user can specify any path in any format:
- `Personal > Finance > Taxes > 2022 > A1000 file returns`
- `personal finance taxes 2022 — A1000 file returns`
- `add A1000 file returns to Personal Finance Taxes 2022`

Parse the path from the user's message. Infer where the path ends and item text begins.
**ALWAYS auto-create any missing nodes — never ask the user to create them first.**

Steps:
1. Parse the full path and item text from the user's message
2. Call: `python3 todo.py add "node1/node2/node3" "item text"`
3. Respond: `✅ Added to Personal › Finance › Taxes › 2022: "A1000 file returns"` + tags if any

### LIST all todos
Format as indented tree. Nodes that have both children and items show items first, then children.

```
📋 Todo Tree

📂 Personal
  📂 Finance
    📂 Taxes
      📂 2022
        ⬜ #1 A1000 file returns
        ✅ #2 A1000 file 2021
      📂 2023
        ⬜ #1 SP9 estimate Q3

📂 Work
  📂 ProjectAlpha
    ⬜ #1 URGENT write spec
```

Skip empty nodes (no items anywhere in subtree).

### SEARCH / FIND
User says things like:
- `find A1000` → search ALL nodes for items tagged A1000
- `find A1000 in Personal Finance` → narrow to that subtree
- `show Personal Finance Taxes` → show everything under that path
- `what's in Work ProjectAlpha` → show items there

Call: `python3 todo.py find "A1000" "Personal/Finance"` or `python3 todo.py show "Personal/Finance/Taxes"`

### MARK DONE
User says: `mark #3 in Personal Finance Taxes 2022 as done`
Call: `python3 todo.py done "Personal/Finance/Taxes/2022" 3`

### CLEAR completed
`python3 todo.py clear` — removes all done items everywhere.

### SHOW tree structure (no items)
`python3 todo.py tree` — shows just the node names, no items. Good for "what categories do I have?"

### DELETE a node
Always confirm before deleting — it removes all children and items inside.
`python3 todo.py delete "Personal/Finance/OldStuff"`

## Script Helper
```bash
python3 ~/.openclaw/workspace/skills/todo-manager/scripts/todo.py <command> [args...]
```
See `references/todo-script-api.md` for full command reference.

## Rules
- **Auto-create any missing nodes immediately — never ask the user to create them first**
- The tree is unlimited depth — Personal > Finance > Taxes > 2022 > Q1 > January is valid
- NEVER delete without explicit confirmation
- When showing paths, use › separator: `Personal › Finance › Taxes › 2022`
- IDs are sequential within each node's items list
- When user says "all A1000" with no path — search EVERYWHERE
- If path is ambiguous, use partial match (case-insensitive)

## Quick Examples
User: "add Personal > Finance > Taxes > 2022 > A1000 file returns"
→ `python3 todo.py add "Personal/Finance/Taxes/2022" "A1000 file returns"`

User: "add a new category Goals and add learn OpenClaw to it"
→ `python3 todo.py add "Goals" "learn OpenClaw"` ← Goals auto-created

User: "find all A1000 in Personal Finance"
→ `python3 todo.py find "A1000" "Personal/Finance"`

User: "show what's in Work"
→ `python3 todo.py show "Work"`

User: "mark #1 in Personal Finance Taxes 2022 as done"
→ `python3 todo.py done "Personal/Finance/Taxes/2022" 1`

User: "what categories do I have?"
→ `python3 todo.py tree`
