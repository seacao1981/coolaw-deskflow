"""Tests for MemoryStorage (SQLite backend)."""

from __future__ import annotations

from pathlib import Path

import pytest

from deskflow.core.models import MemoryEntry
from deskflow.errors import MemoryStorageError
from deskflow.memory.storage import MemoryStorage


class TestMemoryStorage:
    """Tests for MemoryStorage."""

    async def test_initialize(self, temp_db_path: Path) -> None:
        storage = MemoryStorage(temp_db_path)
        await storage.initialize()
        assert temp_db_path.exists()
        await storage.close()

    async def test_store_and_get(self, memory_storage: MemoryStorage) -> None:
        entry = MemoryEntry(
            content="Python is great",
            memory_type="semantic",
            importance=0.8,
            tags=["python", "opinion"],
        )

        entry_id = await memory_storage.store_memory(entry)
        assert entry_id == entry.id

        retrieved = await memory_storage.get_by_id(entry.id)
        assert retrieved is not None
        assert retrieved.content == "Python is great"
        assert retrieved.memory_type == "semantic"
        assert retrieved.importance == 0.8
        assert "python" in retrieved.tags

    async def test_get_nonexistent(self, memory_storage: MemoryStorage) -> None:
        result = await memory_storage.get_by_id("nonexistent-id")
        assert result is None

    async def test_delete(self, memory_storage: MemoryStorage) -> None:
        entry = MemoryEntry(content="to be deleted")
        await memory_storage.store_memory(entry)

        deleted = await memory_storage.delete_memory(entry.id)
        assert deleted is True

        result = await memory_storage.get_by_id(entry.id)
        assert result is None

    async def test_delete_nonexistent(self, memory_storage: MemoryStorage) -> None:
        deleted = await memory_storage.delete_memory("fake-id")
        assert deleted is False

    async def test_count(self, memory_storage: MemoryStorage) -> None:
        assert await memory_storage.count() == 0

        await memory_storage.store_memory(MemoryEntry(content="entry 1"))
        await memory_storage.store_memory(MemoryEntry(content="entry 2"))
        await memory_storage.store_memory(MemoryEntry(content="entry 3"))

        assert await memory_storage.count() == 3

    async def test_search_fts(self, memory_storage: MemoryStorage) -> None:
        await memory_storage.store_memory(
            MemoryEntry(content="Python is a programming language")
        )
        await memory_storage.store_memory(
            MemoryEntry(content="JavaScript runs in browsers")
        )
        await memory_storage.store_memory(
            MemoryEntry(content="Python has great libraries")
        )

        results = await memory_storage.search_fts("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    async def test_search_like_fallback(self, memory_storage: MemoryStorage) -> None:
        await memory_storage.store_memory(
            MemoryEntry(content="The user prefers dark mode")
        )

        results = await memory_storage.search_like("dark mode")
        assert len(results) >= 1
        assert "dark mode" in results[0].content

    async def test_get_recent(self, memory_storage: MemoryStorage) -> None:
        for i in range(5):
            await memory_storage.store_memory(
                MemoryEntry(content=f"Memory entry {i}")
            )

        recent = await memory_storage.get_recent(limit=3)
        assert len(recent) == 3

    async def test_store_with_embedding(self, memory_storage: MemoryStorage) -> None:
        entry = MemoryEntry(
            content="test",
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        await memory_storage.store_memory(entry)

        retrieved = await memory_storage.get_by_id(entry.id)
        assert retrieved is not None
        assert retrieved.embedding is not None
        assert len(retrieved.embedding) == 4
        assert abs(retrieved.embedding[0] - 0.1) < 0.001

    async def test_not_initialized_raises(self) -> None:
        storage = MemoryStorage("/tmp/not_initialized.db")
        with pytest.raises(MemoryStorageError, match="not initialized"):
            storage._ensure_connected()

    async def test_store_with_metadata(self, memory_storage: MemoryStorage) -> None:
        entry = MemoryEntry(
            content="test",
            metadata={"source": "chat", "round": 3},
        )
        await memory_storage.store_memory(entry)

        retrieved = await memory_storage.get_by_id(entry.id)
        assert retrieved is not None
        assert retrieved.metadata["source"] == "chat"
        assert retrieved.metadata["round"] == 3
