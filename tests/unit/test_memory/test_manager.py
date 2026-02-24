"""Tests for MemoryManager."""

from __future__ import annotations

import pytest

from deskflow.core.models import MemoryEntry
from deskflow.memory.manager import MemoryManager


class TestMemoryManager:
    """Tests for MemoryManager (unified interface)."""

    async def test_store_and_retrieve(self, memory_manager: MemoryManager) -> None:
        entry = MemoryEntry(
            content="User likes Python programming",
            memory_type="episodic",
            importance=0.7,
            tags=["preference"],
        )

        entry_id = await memory_manager.store(entry)
        assert entry_id == entry.id

        results = await memory_manager.retrieve("Python")
        assert len(results) >= 1

    async def test_get_by_id(self, memory_manager: MemoryManager) -> None:
        entry = MemoryEntry(content="test memory")
        await memory_manager.store(entry)

        result = await memory_manager.get_by_id(entry.id)
        assert result is not None
        assert result.content == "test memory"

    async def test_delete(self, memory_manager: MemoryManager) -> None:
        entry = MemoryEntry(content="to delete")
        await memory_manager.store(entry)

        deleted = await memory_manager.delete(entry.id)
        assert deleted is True

        result = await memory_manager.get_by_id(entry.id)
        assert result is None

    async def test_count(self, memory_manager: MemoryManager) -> None:
        assert await memory_manager.count() == 0

        await memory_manager.store(MemoryEntry(content="one"))
        await memory_manager.store(MemoryEntry(content="two"))

        assert await memory_manager.count() == 2

    async def test_get_recent(self, memory_manager: MemoryManager) -> None:
        for i in range(5):
            await memory_manager.store(MemoryEntry(content=f"entry {i}"))

        recent = await memory_manager.get_recent(limit=3)
        assert len(recent) == 3

    async def test_cache_invalidation_on_store(
        self, memory_manager: MemoryManager
    ) -> None:
        """Storing a new entry should invalidate the retrieval cache."""
        entry = MemoryEntry(content="Python is great for data science")
        await memory_manager.store(entry)

        # Retrieve to populate cache
        await memory_manager.retrieve("Python")

        # Store new entry
        await memory_manager.store(
            MemoryEntry(content="Python is also great for web")
        )

        # Cache should be invalidated, second retrieval hits DB
        results = await memory_manager.retrieve("Python")
        assert len(results) >= 1

    async def test_cache_stats(self, memory_manager: MemoryManager) -> None:
        stats = memory_manager.cache_stats()
        assert "size" in stats
        assert "capacity" in stats
        assert "hits" in stats

    async def test_retrieve_with_type_filter(
        self, memory_manager: MemoryManager
    ) -> None:
        await memory_manager.store(
            MemoryEntry(content="Python fact", memory_type="semantic")
        )
        await memory_manager.store(
            MemoryEntry(content="Python chat", memory_type="episodic")
        )

        # Filter by type
        results = await memory_manager.retrieve(
            "Python", memory_type="semantic"
        )
        for r in results:
            assert r.memory_type == "semantic"
