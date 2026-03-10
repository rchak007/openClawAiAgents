---
name: eternalquest
description: "Personal goals, habits, and growth tracker for EternalQuest_bot. Use this skill when the user wants to add goals, list quests, mark milestones done, search by tag (like HABIT, GOAL, URGENT), find items by path, clear completed items, or manage the personal growth tree. Triggered by: add goal, add habit, show my quests, list goals, mark done, find HABIT, search goals, what's in Health, clear completed, add category."
metadata: {
  "openclaw": {
    "emoji": "🌟",
    "requires": {
      "bins": ["python3"]
    }
  }
}
---

# EternalQuest Skill

## Overview
Personal goals, habits, and growth tracker stored in `~/.openclaw/workspace/eternalquest-todos.json`.

**Separate data file from the main todo bot and realestate bot.**

The tree is **fully fluid and unlimited depth**: any path is valid, all missing nodes are auto-created. Never ask the user to pre-create a category.

Path structure: **node1 > node2 > node3 > ... > item text**

The last segment is always the item text. Everything before it is the tree path. Examples:
- `Health > Fitness > Running > HABIT run 5k weekly` → path `Health/Fitness/Running`, item `HABIT run 5k weekly`
- `Learning > Books > GOAL finish Autobiography of a Yogi` → path `Learning/Books`, item `GOAL finish Autobiography of a Yogi`
- `Spiritual > Meditation > HABIT meditate 30min daily` → path `Spiritual/Meditation`, item `HABIT meditate 30min daily`

Items support embedded UPPERCASE tags (e.g. `HABIT`, `GOAL`, `URGENT`, `WEEKLY`) for filtering.

## Data File
Always read/write: `~/.openclaw/workspace/eternalquest-todos.json`

Same JSON structure as the main todo skill:
```json
{
  "nodes": {
    "Health": {
      "children": {
        "Fitness": {
          "items": [
            {"id": 1, "text": "HABIT run 5k weekly", "done": false, "created": "2026-03-10 09:00"}
          ]
        }
      }
    }
  }
}
```

If the file doesn't exist, create it: `{"nodes": {}}`

## Item Schema
```json
{"id": 1, "text": "HABIT run 5k weekly", "done": false, "created": "2026-03-10 09:00"}
```
Tags are UPPERCASE words extracted from item text: regex `\b[A-Z][A-Z0-9]{1,9}\b`

## Script
```bash
python3 ~/.openclaw/workspace/skills/eternalquest/scripts/todo.py <command> [args...]
```

## Operations

### ADD an item — FLUID PATH
```
python3 todo.py add "Health/Fitness/Running" "HABIT run 5k weekly"
```
Respond: `✅ Added to Health › Fitness › Running: "HABIT run 5k weekly"` + tags if any

### LIST all goals
```
python3 todo.py list
```
Format as indented tree. Never show Archive nodes unless explicitly asked.

```
🌟 EternalQuest Tree

📂 Health
  📂 Fitness
    📂 Running
      ⬜ #1 HABIT run 5k weekly
      ✅ #2 HABIT stretch daily

📂 Learning
  📂 Books
    ⬜ #1 GOAL finish Autobiography of a Yogi
```

### SEARCH / FIND
```
python3 todo.py find "HABIT"
python3 todo.py find "HABIT" "Health/Fitness"
python3 todo.py show "Health/Fitness"
```

### MARK DONE
```
python3 todo.py done "Health/Fitness/Running" 1
```

### CLEAR completed
```
python3 todo.py clear
```

### SHOW tree structure (no items)
```
python3 todo.py tree
```

### DELETE a node
Always confirm before deleting.
```
python3 todo.py delete "Health/Fitness/OldStuff"
```

## Rules
- **Auto-create any missing nodes — never ask the user to create them first**
- Unlimited depth tree
- NEVER delete without explicit confirmation
- NEVER show Archive nodes unless explicitly asked
- When showing paths, use › separator: `Health › Fitness › Running`
- IDs are sequential within each node's items list
- When user says "all HABIT" with no path — search EVERYWHERE

## Quick Examples
User: "add Health > Fitness > HABIT run 5k weekly"
→ `python3 todo.py add "Health/Fitness" "HABIT run 5k weekly"`

User: "add a new category Spiritual and add HABIT meditate 30min to it"
→ `python3 todo.py add "Spiritual" "HABIT meditate 30min"`

User: "find all HABITs"
→ `python3 todo.py find "HABIT"`

User: "show what's in Learning"
→ `python3 todo.py show "Learning"`

User: "mark #1 in Health Fitness Running as done"
→ `python3 todo.py done "Health/Fitness/Running" 1`

User: "what categories do I have?"
→ `python3 todo.py tree`