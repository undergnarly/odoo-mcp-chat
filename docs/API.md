# Odoo AI Agent - API Documentation

## REST API Endpoints

The Odoo AI Agent provides a REST API for programmatic access to all features.

### Base URL

```
http://localhost:8000
```

### Authentication

All endpoints (except `/health` and `/`) require API key authentication:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/query
```

## Endpoints

### Health Check

Check system status and connectivity.

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "odoo_connected": true,
  "llm_configured": true
}
```

### Query Endpoint

Process natural language queries against Odoo.

```http
POST /api/query
Content-Type: application/json
X-API-Key: your-api-key

{
  "message": "Show me all pending purchase orders",
  "context": {}
}
```

**Response:**

```json
{
  "success": true,
  "type": "query_result",
  "content": "Found 15 records",
  "data": {
    "model": "purchase.order",
    "count": 15,
    "results": [...]
  }
}
```

### Action Endpoint

Execute write operations and actions (requires confirmation).

```http
POST /api/action
Content-Type: application/json
X-API-Key: your-api-key

{
  "message": "Approve PO-1234",
  "confirm": false,
  "context": {}
}
```

**Response:**

```json
{
  "success": true,
  "type": "confirmation_required",
  "content": "⚠️ About to approve PO-1234. Proceed?",
  "requires_confirmation": true
}
```

### List Models

Get all available Odoo models.

```http
GET /models
X-API-Key: your-api-key
```

**Response:**

```json
{
  "success": true,
  "models": ["res.partner", "purchase.order", "sale.order", ...],
  "total": 125
}
```

### Get Model Details

Get field definitions for a specific model.

```http
GET /models/{model_name}
X-API-Key: your-api-key
```

**Response:**

```json
{
  "success": true,
  "model": "purchase.order",
  "info": {...},
  "fields": {
    "name": {...},
    "partner_id": {...},
    ...
  }
}
```

## Python Client Example

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "your-api-key"

headers = {"X-API-Key": API_KEY}

# Query example
response = requests.post(
    f"{API_URL}/api/query",
    headers=headers,
    json={"message": "Show me pending purchase orders"}
)
print(response.json())

# List models
response = requests.get(
    f"{API_URL}/models",
    headers=headers
)
print(response.json())
```

## JavaScript Client Example

```javascript
const API_URL = "http://localhost:8000";
const API_KEY = "your-api-key";

const headers = {
  "X-API-Key": API_KEY,
  "Content-Type": "application/json"
};

// Query example
fetch(`${API_URL}/api/query`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    message: "Show me pending purchase orders"
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad request
- `401` - Unauthorized (missing API key)
- `403` - Forbidden (invalid API key)
- `500` - Internal server error

## Rate Limiting

By default:
- 100 requests per minute
- 1000 requests per hour

Configure via environment variables:
```bash
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
```
