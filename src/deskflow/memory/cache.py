"""LRU cache for memory retrieval results."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class LRUCache:
    """Thread-safe LRU cache for memory retrieval results.

    L1 cache layer: stores query -> results mappings in memory
    for fast repeated lookups.
    """

    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(query: str, top_k: int, memory_type: str | None) -> str:
        """Create a cache key from query parameters."""
        raw = f"{query}|{top_k}|{memory_type or 'all'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(
        self, query: str, top_k: int = 5, memory_type: str | None = None
    ) -> Any | None:
        """Get a cached result.

        Returns:
            Cached value or None if not found.
        """
        key = self._make_key(query, top_k, memory_type)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(
        self,
        query: str,
        top_k: int,
        memory_type: str | None,
        value: Any,
    ) -> None:
        """Store a result in the cache."""
        key = self._make_key(query, top_k, memory_type)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._capacity:
                self._cache.popitem(last=False)

    def invalidate(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total * 100

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {
            "size": self.size,
            "capacity": self._capacity,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 1),
        }
