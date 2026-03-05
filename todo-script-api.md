# Todo Script API Reference

Paths use `/` separator or ` > `. Partial, case-insensitive node names work.

## Commands

| Command | Args | Example |
|---------|------|---------|
| `add` | "path" "text" | `todo.py add "Personal/Finance/Taxes/2022" "A1000 file returns"` |
| `list` | — | `todo.py list` |
| `tree` | — | `todo.py tree` (node names only, no items) |
| `show` | "path" | `todo.py show "Personal/Finance"` |
| `find` | "TAG" ["path"] | `todo.py find "A1000" "Personal/Finance"` |
| `done` | "path" id | `todo.py done "Personal/Finance/Taxes/2022" 1` |
| `undone` | "path" id | `todo.py undone "Personal/Finance/Taxes/2022" 1` |
| `clear` | — | `todo.py clear` |
| `delete` | "path" | `todo.py delete "Personal/Finance/OldStuff"` |
| `rename` | "path" "new name" | `todo.py rename "Personal/Finace" "Finance"` |
| `move` | "src" "dst" | `todo.py move "Personal/Temp" "Archive"` |
| `dump` | — | `todo.py dump` |

## Notes
- **All paths are auto-created on `add`** — no need to pre-create nodes
- Paths accept `/` or ` > ` as separator
- Node names match partially and case-insensitively: "personal" matches "Personal"
- Tags auto-extracted from item text (UPPERCASE words like A1000, URGENT, SP9)
- `find` with empty tag `""` shows all items at that path scope
- Tree depth is unlimited — any nesting level works
