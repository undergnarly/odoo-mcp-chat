# AI Agent API Design

## Overview

External API for AI agents to interact with Odoo via natural language. Same core logic as chat UI, but returns JSON and executes write operations without confirmation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Chainlit App (:8080)                     │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │   Chat UI (/)   │  │  Admin (/admin) │  │ API (/api)  │  │
│  │   human-friendly│  │   audit logs    │  │ machine API │  │
│  └────────┬────────┘  └─────────────────┘  └──────┬──────┘  │
│           │                                       │         │
│           └──────────────┬────────────────────────┘         │
│                          ▼                                  │
│              ┌─────────────────────┐                        │
│              │     OdooAgent       │                        │
│              │  (shared core)      │                        │
│              │                     │                        │
│              │  require_confirmation│                       │
│              │  - True for chat    │                        │
│              │  - False for API    │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## API Format

### Endpoint

```
POST /api/v1/chat
Headers:
  X-API-Key: <api_key>
  Content-Type: application/json
```

### Request

```json
{
  "message": "Show me the last 5 purchase orders",
  "history": [
    {"role": "user", "content": "What models are available?"},
    {"role": "assistant", "content": "Available models: purchase.order, res.partner..."}
  ]
}
```

- `message` (required) - current request
- `history` (optional) - previous messages for context

### Response

```json
{
  "success": true,
  "type": "query",
  "intent": "QUERY",
  "model": "purchase.order",
  "data": {
    "records": [...],
    "total": 5,
    "fields": ["id", "name", "state", "amount_total"]
  },
  "message": "Found 5 purchase orders"
}
```

**Response types:**
- `query` - query results with `data.records`
- `create` - created record with `data.record_id`
- `update` - updated record with `data.record_id`
- `delete` - deleted record with `data.record_id`
- `action` - action result
- `chat` - text response in `message`
- `error` - error with `error.code` and `error.message`

### Error Response

```json
{
  "success": false,
  "type": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field 'partner_id' is required"
  }
}
```

## OdooAgent Changes

### New parameter `require_confirmation`

```python
class OdooAgent:
    def __init__(self, odoo_client, discovery_service, require_confirmation=True):
        self.require_confirmation = require_confirmation
```

### Modified _handle_create/update/delete

```python
async def _handle_create(self, model, parameters, original_message):
    # ... validation ...

    if self.require_confirmation:
        # Chat mode - return confirmation request
        return {
            "type": "confirmation_required",
            "action": "create",
            "model": model,
            "values": values,
        }
    else:
        # API mode - execute immediately
        result = self.odoo.execute_method(model, "create", [values])
        audit_log_json(action="create", model=model, ...)
        return {
            "type": "create",
            "success": True,
            "data": {"record_id": result},
        }
```

## File Structure

### New files

```
src/
├── api/
│   ├── __init__.py      # FastAPI router
│   ├── chat.py          # POST /api/v1/chat endpoint
│   ├── models.py        # Pydantic schemas
│   └── auth.py          # API key middleware
```

### Modified files

1. `src/agent/langchain_agent.py` - add `require_confirmation` parameter
2. `src/ui/chainlit_app.py` - mount `/api` router
3. `.env.example` - add `AGENT_API_KEY`

## Authentication

- API Key in `X-API-Key` header
- Key stored in `.env` as `AGENT_API_KEY`
- Middleware validates before processing

## Session/History

- Hybrid approach: stateless by default
- Client can pass `history` array for context
- No server-side session storage required

## Differences: Chat vs API

| Feature | Chat UI | API |
|---------|---------|-----|
| Confirmation for writes | Yes | No |
| Response format | Markdown | JSON |
| Authentication | Chainlit login | API Key |
| Session | Server-managed | Client-managed history |
| Target user | Human | AI Agent |
