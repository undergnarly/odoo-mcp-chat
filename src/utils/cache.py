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
