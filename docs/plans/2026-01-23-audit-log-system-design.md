# Audit Log System Design

## Overview

Separate admin page to view all database changes made by the AI agent, with focus on create/update/delete operations.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Chainlit App (:8080)                 │
│  ┌─────────────────┐     ┌────────────────────────────┐ │
│  │   Chat UI       │     │   FastAPI Mount (/admin)   │ │
│  │   /             │     │   /admin/audit             │ │
│  └─────────────────┘     │   /admin/... (future)      │ │
│                          └────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ logs/audit.jsonl │
                    └─────────────────┘
```

**Key decisions:**
- FastAPI mounted in Chainlit app at `/admin/*`
- Single port (8080), unified entry point
- JSONL file for storage (rotation by size)
- UI inherits Chainlit styles (dark theme, fonts, colors)

## Data Format (JSONL)

```json
{
  "id": "uuid-v4",
  "timestamp": "2026-01-23T14:30:00.123Z",
  "action": "update",
  "model": "purchase.order",
  "record_id": 42,
  "record_name": "PO00042",
  "user": "admin",
  "session_id": "abc123",
  "thread_id": "def456",
  "changes": {
    "state": {"old": "draft", "new": "sent"},
    "date_order": {"old": "2026-01-20", "new": "2026-01-23"}
  },
  "values": null
}
```

**Fields by operation type:**
- **create**: `values` contains created data, `changes` = null
- **update**: `changes` contains old/new for each field, `values` = null
- **delete**: `values` contains data before deletion, `changes` = null

**For update**: before `write()` call `read()` to get old values.

## UI Page `/admin/audit`

**Header:**
- Title "Audit Log"
- Filters: action (create/update/delete), model (dropdown), date (from-to)
- Refresh button

**Table:**
| Time | Action | Model | Record | User | Changes |
|------|--------|-------|--------|------|---------|
| 14:30 | 🟢 create | purchase.order | PO00042 | admin | {partner_id: 5, ...} |
| 14:25 | 🟡 update | purchase.order | PO00041 | admin | state: draft → sent |
| 14:20 | 🔴 delete | res.partner | #123 | admin | {name: "Test"} |

**Styling (Chainlit-like):**
- Dark background `#1e1e1e`, text `#e0e0e0`
- Accent colors: green create, yellow update, red delete
- Font: Inter or system-ui
- Pagination: 50 records per page

**Record details:**
- Click row to expand full JSON with changes/values
- Copy session_id to search in chat

## Code Changes

### Files to modify:
1. `src/utils/logging.py` — new function `audit_log_json()` for JSONL format
2. `src/extensions/write_tools.py` — before `write()` read old values, call new audit
3. `src/agent/langchain_agent.py` — if operations go through agent, also log

### Files to create:
1. `src/admin/__init__.py` — FastAPI router
2. `src/admin/audit.py` — endpoints: `GET /admin/audit` (HTML), `GET /admin/api/audit` (JSON)
3. `src/admin/templates/audit.html` — Jinja2 template
4. `src/ui/chainlit_app.py` — mount FastAPI router

### Workflow:
```
1. audit_log_json() → writes to logs/audit.jsonl
2. write_tools.py → read() old values → write() → audit_log_json()
3. FastAPI router → reads JSONL → returns HTML/JSON
4. Mount in Chainlit app
```

## Features NOT included (by design)

- No "undo/revert" functionality — use agent or Odoo directly for rollbacks
- No real-time updates — manual refresh only
- No authentication for admin pages (relies on Chainlit auth)
