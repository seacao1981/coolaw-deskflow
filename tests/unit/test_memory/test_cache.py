"""Tests for LRU cache."""

from __future__ import annotations

from deskflow.memory.cache import LRUCache


class TestLRUCache:
    """Tests for LRU cache."""

    def test_put_and_get(self, lru_cache: LRUCache) -> None:
        lru_cache.put("hello", 5, None, ["result1", "result2"])
        result = lru_cache.get("hello", 5, None)
        assert result == ["result1", "result2"]

    def test_cache_miss(self, lru_cache: LRUCache) -> None:
        result = lru_cache.get("nonexistent", 5, None)
        assert result is None

    def test_capacity_eviction(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 5, None, "val_a")
        cache.put("b", 5, None, "val_b")
        cache.put("c", 5, None, "val_c")
        cache.put("d", 5, None, "val_d")  # Should evict "a"

        assert cache.get("a", 5, None) is None
        assert cache.get("b", 5, None) == "val_b"
        assert cache.get("d", 5, None) == "val_d"
        assert cache.size == 3

    def test_lru_ordering(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 5, None, "1")
        cache.put("b", 5, None, "2")
        cache.put("c", 5, None, "3")

        # Access "a" to make it most recently used
        cache.get("a", 5, None)

        # Insert new item - should evict "b" (least recently used)
        cache.put("d", 5, None, "4")
        assert cache.get("b", 5, None) is None
        assert cache.get("a", 5, None) == "1"

    def test_update_existing_key(self, lru_cache: LRUCache) -> None:
        lru_cache.put("query", 5, None, "old_value")
        lru_cache.put("query", 5, None, "new_value")
        assert lru_cache.get("query", 5, None) == "new_value"

    def test_invalidate(self, lru_cache: LRUCache) -> None:
        lru_cache.put("a", 5, None, "1")
        lru_cache.put("b", 5, None, "2")
        assert lru_cache.size == 2

        lru_cache.invalidate()
        assert lru_cache.size == 0
        assert lru_cache.get("a", 5, None) is None

    def test_hit_rate(self, lru_cache: LRUCache) -> None:
        lru_cache.put("a", 5, None, "val")

        lru_cache.get("a", 5, None)  # Hit
        lru_cache.get("b", 5, None)  # Miss

        assert lru_cache.hit_rate == 50.0

    def test_hit_rate_zero_when_empty(self) -> None:
        cache = LRUCache()
        assert cache.hit_rate == 0.0

    def test_stats(self, lru_cache: LRUCache) -> None:
        lru_cache.put("a", 5, None, "1")
        lru_cache.get("a", 5, None)
        lru_cache.get("miss", 5, None)

        stats = lru_cache.stats()
        assert stats["size"] == 1
        assert stats["capacity"] == 5
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_different_keys_for_different_params(self, lru_cache: LRUCache) -> None:
        lru_cache.put("query", 5, None, "result_5")
        lru_cache.put("query", 10, None, "result_10")
        lru_cache.put("query", 5, "episodic", "result_episodic")

        assert lru_cache.get("query", 5, None) == "result_5"
        assert lru_cache.get("query", 10, None) == "result_10"
        assert lru_cache.get("query", 5, "episodic") == "result_episodic"
