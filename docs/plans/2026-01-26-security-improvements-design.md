# Security Improvements Design

**Date:** 2026-01-26
**Status:** Approved

## Overview

Comprehensive security improvements for the Odoo AI Agent admin panel:
1. Admin role authentication for `/admin/*` routes
2. Secret encryption in SQLite database
3. Full API key management system with audit logging

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Security Layer                               │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │  Admin Auth      │  │  Secret Vault    │  │  API Key Mgr  │ │
│  │  Middleware      │  │  (Fernet)        │  │               │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
│           │                     │                     │         │
│           ▼                     ▼                     ▼         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    SQLite Database                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │  settings   │  │  api_keys   │  │  api_key_usage  │   │  │
│  │  │  (encrypted)│  │  (hashed)   │  │  (audit log)    │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Admin Authentication Middleware

**Mechanism:**
- Get `session_id` from Chainlit cookie
- Look up user in database by session
- Check user role is `admin`

**User roles:**
- `user` — default, chat access only
- `admin` — full admin panel access
- `readonly` — view-only access

**Database change:**
```sql
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
```

**Role assignment:**
- First registered user automatically gets `admin` role
- Admins can assign roles via `/admin/users` page

### 2. Secret Vault (Encryption)

**Library:** `cryptography.fernet` (symmetric encryption)

**Master key management:**
1. Check `ENCRYPTION_KEY` environment variable
2. Check `data/encryption.key` file
3. Generate new key and save to file

**Module:** `src/security/vault.py`
```python
class SecretVault:
    def encrypt(self, value: str) -> str
    def decrypt(self, encrypted: str) -> str

def get_or_create_master_key() -> bytes
```

**Encrypted fields:**
| Key | Encrypted |
|-----|-----------|
| `ODOO_PASSWORD` | Yes |
| `OPENAI_API_KEY` | Yes |
| `AGENT_API_KEY` | Yes |
| `ODOO_URL` | No |
| `LOG_LEVEL` | No |

**Database schema update:**
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    encrypted_value TEXT,
    is_secret BOOLEAN DEFAULT FALSE
);
```

### 3. API Key Management

**Table `api_keys`:**
```sql
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,
    created_by TEXT,
    permissions TEXT DEFAULT 'full'
);
```

**Table `api_key_usage`:**
```sql
CREATE TABLE api_key_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_status INTEGER
);
```

**Key format:** `sk_live_` + 32 random characters
- Example: `sk_live_<32_random_alphanumeric_characters>`
- `sk_live_` for production, `sk_test_` for test keys

**API endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/api/keys` | List keys (without key values) |
| POST | `/admin/api/keys` | Create new key |
| DELETE | `/admin/api/keys/{id}` | Revoke key |
| GET | `/admin/api/keys/{id}/usage` | Usage history |

**Important:** Full key is shown only once at creation — only hash is stored.

## File Structure

**New files:**
```
src/
├── security/
│   ├── __init__.py
│   ├── vault.py
│   ├── auth.py
│   └── api_keys.py
├── admin/
│   ├── users.py
│   ├── api_keys.py
│   └── templates/
│       ├── users.html
│       └── api_keys.html
```

**Modified files:**
- `src/ui/data_layer.py` — add `role` column, migration
- `src/settings_manager/settings_db.py` — integrate with SecretVault
- `src/admin/__init__.py` — add new routers, middleware
- `src/api/auth.py` — use APIKeyManager instead of env

## UI Pages

1. **`/admin/users`** — user table with role management
2. **`/admin/api-keys`** — create/revoke keys, usage statistics
3. **`/admin/settings`** — add "Encryption Status" section

**Admin navigation:**
```
┌─────────────────────────────────────┐
│  Settings | Users | API Keys | Logs │
└─────────────────────────────────────┘
```

## Implementation Order

| # | Task | Depends on |
|---|------|------------|
| 1 | Create `src/security/vault.py` | — |
| 2 | Create `src/security/auth.py` | — |
| 3 | Create `src/security/api_keys.py` | 1 |
| 4 | DB migration: add `role` to users, `api_keys`, `api_key_usage` tables | — |
| 5 | Update `settings_db.py` — integrate with vault | 1 |
| 6 | Add middleware to `admin/__init__.py` | 2 |
| 7 | Create `/admin/users` page | 2, 4 |
| 8 | Create `/admin/api-keys` page | 3, 4 |
| 9 | Update `src/api/auth.py` — use APIKeyManager | 3 |
| 10 | Migrate existing secrets to encrypted format | 1, 5 |

**Parallel execution:** 1+2+4, then 3+5+6, then 7+8+9, finally 10
