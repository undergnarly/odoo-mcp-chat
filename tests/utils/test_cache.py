import pytest
import time
import threading
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

    def test_invalidate_pattern(self):
        """Test pattern-based invalidation."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("user:1:profile", {"name": "Alice"})
        cache.set("user:1:settings", {"theme": "dark"})
        cache.set("user:2:profile", {"name": "Bob"})
        cache.set("product:1", {"name": "Widget"})

        # Invalidate all user:1: keys
        count = cache.invalidate_pattern("user:1:")
        assert count == 2
        assert cache.get("user:1:profile") is None
        assert cache.get("user:1:settings") is None
        assert cache.get("user:2:profile") == {"name": "Bob"}
        assert cache.get("product:1") == {"name": "Widget"}

    def test_invalidate_pattern_no_matches(self):
        """Test pattern invalidation with no matches."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        count = cache.invalidate_pattern("nonexistent:")
        assert count == 0
        assert cache.get("key1") == "value1"

    def test_stats(self):
        """Test cache statistics."""
        cache = TTLCache(ttl_seconds=60, max_size=10)

        # Initial stats
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0
        assert stats["size"] == 0
        assert stats["max_size"] == 10

        # Add some data
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Hit
        cache.get("key1")
        # Miss
        cache.get("missing")

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 2

    def test_update_existing_key(self):
        """Test updating an existing key."""
        cache = TTLCache(ttl_seconds=60, max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Update existing key - should not evict anything
        cache.set("key1", "updated_value1")

        assert cache.get("key1") == "updated_value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

        # Verify that updating a key doesn't increase cache size
        stats = cache.stats()
        assert stats["size"] == 3

    def test_lru_ordering(self):
        """Test LRU eviction order."""
        cache = TTLCache(ttl_seconds=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access 'a' to make it most recently used
        cache.get("a")

        # Add 'd' - should evict 'b' (oldest)
        cache.set("d", 4)

        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_thread_safety_basic(self):
        """Test basic thread safety."""
        cache = TTLCache(ttl_seconds=60)
        results = []
        errors = []

        def worker(thread_id):
            try:
                for i in range(100):
                    key = f"key_{i % 10}"
                    cache.set(key, f"value_{thread_id}_{i}")
                    value = cache.get(key)
                    if value is not None:
                        results.append(value)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0
        # Should have results
        assert len(results) > 0

    def test_invalidate_nonexistent_key(self):
        """Test invalidating a key that doesn't exist."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")

        # Should not raise error
        cache.invalidate("nonexistent")
        assert cache.get("key1") == "value1"

    def test_different_value_types(self):
        """Test caching different value types."""
        cache = TTLCache(ttl_seconds=60)

        cache.set("string", "text")
        cache.set("int", 42)
        cache.set("float", 3.14)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})
        cache.set("none", None)

        assert cache.get("string") == "text"
        assert cache.get("int") == 42
        assert cache.get("float") == 3.14
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}
        assert cache.get("none") is None

    def test_stats_after_clear(self):
        """Test statistics after clearing cache."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("missing")  # Miss

        cache.clear()

        stats = cache.stats()
        # Stats should persist after clear
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        # But size should be 0
        assert stats["size"] == 0

    def test_expired_entries_removed_on_access(self):
        """Test that expired entries are removed when accessed."""
        cache = TTLCache(ttl_seconds=1)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Wait for expiration
        time.sleep(1.1)

        # Accessing expired key should remove it
        assert cache.get("key1") is None

        # Should be counted as miss
        stats = cache.stats()
        assert stats["misses"] == 1
        assert stats["size"] == 1  # key2 still in cache but expired

    def test_max_size_with_unlimited(self):
        """Test cache with no max size limit."""
        cache = TTLCache(ttl_seconds=60, max_size=None)

        # Add many items
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        # All should be accessible
        assert cache.get("key_0") == "value_0"
        assert cache.get("key_99") == "value_99"

        stats = cache.stats()
        assert stats["size"] == 100
        assert stats["max_size"] is None

    def test_default_parameters(self):
        """Test cache with default parameters."""
        cache = TTLCache()

        # Default TTL is 300 seconds
        assert cache.ttl_seconds == 300
        assert cache.max_size is None

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
