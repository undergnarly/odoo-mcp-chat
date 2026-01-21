# MCP Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve Odoo MCP Chat with error sanitization, smart field selection, caching, and performance logging based on analysis of best practices from odoo-mcp-improved and mcp-server-odoo repositories.

**Architecture:** Three new modules (error_sanitizer, field_selector, cache) + performance logging integration. Each module is independent and tested separately. No breaking changes to existing functionality.

**Tech Stack:** Python 3.11+, LangChain, Chainlit, loguru, TTL caching

---

## Phase 1: Error Sanitization

### Task 1.1: Create Error Sanitizer Module

**Files:**
- Create: `src/utils/error_sanitizer.py`
- Test: `tests/utils/test_error_sanitizer.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_error_sanitizer.py
import pytest
from src.utils.error_sanitizer import ErrorSanitizer


class TestErrorSanitizer:
    def test_removes_file_paths(self):
        raw = "Error at /home/user/project/src/module.py:123"
        result = ErrorSanitizer.sanitize(raw)
        assert "/home/user" not in result
        assert "module.py:123" not in result

    def test_removes_stack_trace(self):
        raw = """Traceback (most recent call last):
  File "/opt/odoo/server.py", line 456
    result = execute()
ValueError: Invalid field"""
        result = ErrorSanitizer.sanitize(raw)
        assert "Traceback" not in result
        assert "Invalid field" in result

    def test_preserves_field_name(self):
        raw = "Invalid field res.partner.supplier in leaf"
        result = ErrorSanitizer.sanitize(raw)
        assert "supplier" in result
        assert "res.partner" in result

    def test_preserves_model_name(self):
        raw = "Access denied to model sale.order"
        result = ErrorSanitizer.sanitize(raw)
        assert "sale.order" in result

    def test_maps_common_errors(self):
        raw = "xmlrpc.client.Fault: Access Denied"
        result = ErrorSanitizer.sanitize(raw)
        assert "Access" in result
        assert "xmlrpc" not in result
```

**Step 2: Run test to verify it fails**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_error_sanitizer.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.utils.error_sanitizer'"

**Step 3: Write minimal implementation**

```python
# src/utils/error_sanitizer.py
"""
Error sanitization for user-friendly error messages.
Inspired by mcp-server-odoo error handling patterns.
"""
import re
from typing import Optional


class ErrorSanitizer:
    """
    Sanitizes error messages by removing internal implementation details
    while preserving useful information for the user.
    """

    # Patterns to remove from error messages
    REMOVE_PATTERNS = [
        # File paths with line numbers
        r'/[\w/.-]+\.py:\d+',
        r'/[\w/.-]+\.py',
        # Home directory paths
        r'/home/[\w/.-]+',
        r'/opt/[\w/.-]+',
        r'/usr/[\w/.-]+',
        # Stack traces
        r'Traceback \(most recent call last\):.*?(?=\w+Error:|\w+Exception:|\Z)',
        r'File ".*?", line \d+.*?\n',
        # Python module internals
        r'xmlrpc\.client\.',
        r'odoo\.exceptions\.',
        r'psycopg2\.\w+\.',
    ]

    # Patterns to preserve (model names, field names)
    PRESERVE_PATTERNS = [
        r'\b[a-z]+\.[a-z_]+\b',  # Odoo model names like res.partner
    ]

    # Error message mappings for common errors
    ERROR_MAPPINGS = {
        "Access Denied": "Access denied. You don't have permission for this operation.",
        "ValidationError": "Validation failed. Please check your input.",
        "UserError": "Operation failed. Please check your input.",
        "MissingError": "Record not found. It may have been deleted.",
        "AccessError": "Access denied to this record or model.",
    }

    @classmethod
    def sanitize(cls, error_message: str) -> str:
        """
        Sanitize an error message for user display.

        Args:
            error_message: Raw error message (may contain paths, traces)

        Returns:
            Clean, user-friendly error message
        """
        if not error_message:
            return "An unknown error occurred."

        result = str(error_message)

        # Extract the main error type and message
        # Pattern: "SomeError: actual message"
        error_match = re.search(r'(\w+Error|\w+Exception):\s*(.+?)(?:\n|$)', result, re.DOTALL)
        if error_match:
            error_type = error_match.group(1)
            error_detail = error_match.group(2).strip()

            # Use mapped message if available
            for key, mapped_msg in cls.ERROR_MAPPINGS.items():
                if key in error_type or key in error_detail:
                    # Append specific detail if it contains useful info
                    if cls._contains_useful_info(error_detail):
                        return f"{mapped_msg} Details: {cls._clean_detail(error_detail)}"
                    return mapped_msg

            # Otherwise, clean and return the detail
            result = cls._clean_detail(error_detail)
        else:
            # No standard error format, just clean the whole message
            result = cls._clean_detail(result)

        return result if result else "An error occurred during the operation."

    @classmethod
    def _contains_useful_info(cls, text: str) -> bool:
        """Check if text contains useful info like model/field names."""
        # Check for Odoo model names
        if re.search(r'\b[a-z]+\.[a-z_]+\b', text):
            return True
        # Check for field names
        if re.search(r"field[s]?\s+['\"]?\w+['\"]?", text, re.IGNORECASE):
            return True
        return False

    @classmethod
    def _clean_detail(cls, text: str) -> str:
        """Remove technical details while preserving useful info."""
        result = text

        # Remove patterns
        for pattern in cls.REMOVE_PATTERNS:
            result = re.sub(pattern, '', result, flags=re.DOTALL | re.MULTILINE)

        # Clean up multiple whitespace/newlines
        result = re.sub(r'\s+', ' ', result).strip()

        # Remove leading/trailing quotes
        result = result.strip('"\'')

        return result
```

**Step 4: Run test to verify it passes**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_error_sanitizer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /home/muvs/work/odoo
git add src/utils/error_sanitizer.py tests/utils/test_error_sanitizer.py
git commit -m "feat: add error sanitizer for user-friendly error messages"
```

---

### Task 1.2: Integrate Error Sanitizer into Agent

**Files:**
- Modify: `src/agent/langchain_agent.py:499-504, 410-416`
- Test: Manual testing via chat

**Step 1: Import sanitizer in langchain_agent.py**

Add import at top of file:
```python
from src.utils.error_sanitizer import ErrorSanitizer
```

**Step 2: Update _handle_query error handling**

Replace lines 499-504:
```python
except Exception as e:
    logger.error(f"Error in query: {e}")
    sanitized_error = ErrorSanitizer.sanitize(str(e))
    return {
        "type": "error",
        "content": f"Error querying {model}: {sanitized_error}",
    }
```

**Step 3: Update process_message error handling**

Replace lines 410-416:
```python
except Exception as e:
    logger.error(f"Error processing message: {e}")
    sanitized_error = ErrorSanitizer.sanitize(str(e))
    return {
        "type": "error",
        "content": f"Sorry, I encountered an error: {sanitized_error}",
    }
```

**Step 4: Test manually**

Start chat and trigger an error (e.g., query invalid model)

**Step 5: Commit**

```bash
cd /home/muvs/work/odoo
git add src/agent/langchain_agent.py
git commit -m "feat: integrate error sanitizer into agent responses"
```

---

## Phase 2: Smart Field Selection

### Task 2.1: Create Field Selector Module

**Files:**
- Create: `src/utils/field_selector.py`
- Test: `tests/utils/test_field_selector.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_field_selector.py
import pytest
from src.utils.field_selector import SmartFieldSelector


class TestSmartFieldSelector:
    def test_essential_fields_always_included(self):
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "display_name": {"type": "char"},
            "random_field": {"type": "char"},
        }
        result = SmartFieldSelector.select(fields_info, limit=3)
        assert "id" in result
        assert "name" in result

    def test_limits_fields(self):
        fields_info = {f"field_{i}": {"type": "char"} for i in range(50)}
        fields_info["id"] = {"type": "integer"}
        fields_info["name"] = {"type": "char"}

        result = SmartFieldSelector.select(fields_info, limit=10)
        assert len(result) <= 10

    def test_excludes_binary_fields(self):
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "image": {"type": "binary"},
            "attachment": {"type": "binary"},
        }
        result = SmartFieldSelector.select(fields_info)
        assert "image" not in result
        assert "attachment" not in result

    def test_prioritizes_business_fields(self):
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "state": {"type": "selection"},
            "email": {"type": "char"},
            "random_xyz": {"type": "char"},
        }
        result = SmartFieldSelector.select(fields_info, limit=4)
        assert "state" in result
        assert "email" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_field_selector.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/field_selector.py
"""
Smart field selection for Odoo queries.
Inspired by mcp-server-odoo field importance scoring.
"""
from typing import Dict, List, Optional, Set


class SmartFieldSelector:
    """
    Selects the most relevant fields from Odoo model metadata
    based on importance scoring algorithm.
    """

    # Essential fields (always included)
    ESSENTIAL_FIELDS = {"id", "name", "display_name", "active"}

    # Field types to exclude (too large for responses)
    EXCLUDED_TYPES = {"binary", "html"}

    # Business-important field patterns
    BUSINESS_PATTERNS = {
        "state": 300,
        "status": 280,
        "email": 250,
        "phone": 240,
        "mobile": 230,
        "date": 220,
        "amount": 200,
        "total": 190,
        "price": 180,
        "quantity": 170,
        "qty": 160,
        "partner": 150,
        "company": 140,
        "user": 130,
        "create_date": 120,
        "write_date": 110,
    }

    # Field type scores
    TYPE_SCORES = {
        "char": 100,
        "text": 80,
        "integer": 90,
        "float": 85,
        "monetary": 95,
        "date": 90,
        "datetime": 85,
        "boolean": 70,
        "selection": 100,
        "many2one": 80,
        "many2many": 50,
        "one2many": 40,
    }

    @classmethod
    def select(
        cls,
        fields_info: Dict[str, Dict],
        limit: int = 15,
        exclude_fields: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Select the most important fields based on scoring.

        Args:
            fields_info: Dict of field_name -> field_metadata from fields_get()
            limit: Maximum number of fields to return
            exclude_fields: Optional set of field names to exclude

        Returns:
            List of field names ordered by importance
        """
        exclude_fields = exclude_fields or set()
        scored_fields = []

        for field_name, field_meta in fields_info.items():
            # Skip excluded fields
            if field_name in exclude_fields:
                continue

            # Skip excluded types
            field_type = field_meta.get("type", "")
            if field_type in cls.EXCLUDED_TYPES:
                continue

            # Skip computed fields without store
            if field_meta.get("store") is False:
                continue

            # Calculate score
            score = cls._calculate_score(field_name, field_meta)
            scored_fields.append((field_name, score))

        # Sort by score descending
        scored_fields.sort(key=lambda x: x[1], reverse=True)

        # Always include essential fields first
        result = []
        for f in cls.ESSENTIAL_FIELDS:
            if f in fields_info and f not in exclude_fields:
                result.append(f)

        # Add top scored fields up to limit
        for field_name, score in scored_fields:
            if field_name not in result:
                result.append(field_name)
                if len(result) >= limit:
                    break

        return result

    @classmethod
    def _calculate_score(cls, field_name: str, field_meta: Dict) -> int:
        """Calculate importance score for a field."""
        score = 0

        # Essential field bonus
        if field_name in cls.ESSENTIAL_FIELDS:
            score += 1000

        # Required field bonus
        if field_meta.get("required"):
            score += 500

        # Type score
        field_type = field_meta.get("type", "")
        score += cls.TYPE_SCORES.get(field_type, 50)

        # Business pattern bonus
        field_lower = field_name.lower()
        for pattern, pattern_score in cls.BUSINESS_PATTERNS.items():
            if pattern in field_lower:
                score += pattern_score
                break

        # Stored field bonus
        if field_meta.get("store", True):
            score += 50

        # Searchable bonus
        if field_meta.get("searchable", False):
            score += 30

        return score
```

**Step 4: Run test to verify it passes**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_field_selector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /home/muvs/work/odoo
git add src/utils/field_selector.py tests/utils/test_field_selector.py
git commit -m "feat: add smart field selector for optimized queries"
```

---

### Task 2.2: Integrate Field Selector into Discovery Service

**Files:**
- Modify: `src/extensions/discovery.py`
- Test: Manual testing

**Step 1: Import field selector**

Add import at top of discovery.py:
```python
from src.utils.field_selector import SmartFieldSelector
```

**Step 2: Update get_safe_fields method**

Modify the `get_safe_fields` method to use SmartFieldSelector when full fields_get is available. Keep existing fallback logic for predefined safe fields.

**Step 3: Test manually**

Query a model and verify response size is reduced

**Step 4: Commit**

```bash
cd /home/muvs/work/odoo
git add src/extensions/discovery.py
git commit -m "feat: integrate smart field selector into discovery"
```

---

## Phase 3: Caching for Model Fields

### Task 3.1: Create Cache Module

**Files:**
- Create: `src/utils/cache.py`
- Test: `tests/utils/test_cache.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_cache.py
import pytest
import time
from src.utils.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_ttl_expiration(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_max_size_eviction(self):
        cache = TTLCache(ttl_seconds=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict 'a'
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_invalidate(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
```

**Step 2: Run test to verify it fails**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_cache.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/cache.py
"""
TTL-based cache with LRU eviction.
Inspired by mcp-server-odoo caching patterns.
"""
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional


class TTLCache:
    """
    Thread-safe TTL cache with optional size-based LRU eviction.
    """

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_size: Optional[int] = None,
    ):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time-to-live for entries in seconds
            max_size: Maximum number of entries (None for unlimited)
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            value, timestamp = self._cache[key]

            # Check TTL
            if time.time() - timestamp > self.ttl_seconds:
                del self._cache[key]
                self.misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Evict if at max size
            if self.max_size and len(self._cache) >= self.max_size:
                if key not in self._cache:
                    # Remove oldest item
                    self._cache.popitem(last=False)

            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all keys matching a pattern (simple prefix match).

        Args:
            pattern: Key prefix to match

        Returns:
            Number of keys removed
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "size": len(self._cache),
                "max_size": self.max_size,
            }
```

**Step 4: Run test to verify it passes**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/utils/test_cache.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /home/muvs/work/odoo
git add src/utils/cache.py tests/utils/test_cache.py
git commit -m "feat: add TTL cache with LRU eviction"
```

---

### Task 3.2: Integrate Cache into Discovery Service

**Files:**
- Modify: `src/extensions/discovery.py`

**Step 1: Import cache**

Add import:
```python
from src.utils.cache import TTLCache
```

**Step 2: Add cache instances to OdooModelDiscovery**

Add cache instances in __init__:
```python
self._fields_cache = TTLCache(ttl_seconds=3600, max_size=100)  # 1 hour TTL
self._models_cache = TTLCache(ttl_seconds=3600, max_size=1)
```

**Step 3: Wrap get_model_fields with cache**

Before calling Odoo, check cache first.

**Step 4: Test manually**

Make repeated queries and verify cache hits in logs

**Step 5: Commit**

```bash
cd /home/muvs/work/odoo
git add src/extensions/discovery.py
git commit -m "feat: add caching to model discovery"
```

---

## Phase 4: Performance Logging

### Task 4.1: Add Performance Timing to Logging

**Files:**
- Modify: `src/utils/logging.py`
- Test: Manual testing

**Step 1: Add timing context manager**

Add to logging.py:
```python
import time
from contextlib import contextmanager

@contextmanager
def log_timing(operation: str, **extra):
    """Context manager for timing operations."""
    start = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start) * 1000
        level = "WARNING" if duration_ms > 1000 else "DEBUG"
        log_data = {"operation": operation, "duration_ms": round(duration_ms, 2), **extra}
        if level == "WARNING":
            logger.warning(f"Slow operation: {operation} took {duration_ms:.0f}ms")
        else:
            logger.debug(f"Operation {operation} completed in {duration_ms:.0f}ms")
```

**Step 2: Commit**

```bash
cd /home/muvs/work/odoo
git add src/utils/logging.py
git commit -m "feat: add performance timing to logging"
```

---

### Task 4.2: Add Timing to Critical Operations

**Files:**
- Modify: `src/agent/langchain_agent.py`
- Modify: `src/extensions/discovery.py`

**Step 1: Import log_timing**

**Step 2: Wrap Odoo calls with timing**

Example:
```python
with log_timing("odoo_search_read", model=model):
    results = self.odoo.search_read(...)
```

**Step 3: Commit**

```bash
cd /home/muvs/work/odoo
git add src/agent/langchain_agent.py src/extensions/discovery.py
git commit -m "feat: add performance timing to Odoo operations"
```

---

## Phase 5: Final Integration & Testing

### Task 5.1: Run All Tests

**Step 1: Run full test suite**

Run: `cd /home/muvs/work/odoo && python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Fix any failures**

### Task 5.2: Manual Integration Test

**Step 1: Start the server**

```bash
cd /home/muvs/work/odoo
source venv/bin/activate
chainlit run src/ui/chainlit_app.py --host 0.0.0.0 --port 8080
```

**Step 2: Test scenarios**

1. Query with invalid field -> verify sanitized error
2. Query suppliers -> verify smart field selection
3. Repeat query -> verify cache hit in logs
4. Check logs for timing information

### Task 5.3: Push to Repository

**Step 1: Verify no sensitive data**

```bash
git status
git diff --staged
```

**Step 2: Push**

```bash
git push -u origin main
```

---

## Summary of Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/utils/error_sanitizer.py` | NEW | User-friendly error messages |
| `src/utils/field_selector.py` | NEW | Smart field selection |
| `src/utils/cache.py` | NEW | TTL cache with LRU |
| `src/utils/logging.py` | MODIFY | Add timing context manager |
| `src/agent/langchain_agent.py` | MODIFY | Integrate error sanitizer, timing |
| `src/extensions/discovery.py` | MODIFY | Integrate field selector, cache |
| `tests/utils/test_error_sanitizer.py` | NEW | Tests |
| `tests/utils/test_field_selector.py` | NEW | Tests |
| `tests/utils/test_cache.py` | NEW | Tests |

---

## Rollback Plan

Each task creates a separate commit. If issues arise:

```bash
# View commits
git log --oneline -10

# Revert specific commit
git revert <commit-hash>

# Or reset to specific point
git reset --hard <commit-hash>
```
