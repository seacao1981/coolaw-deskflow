"""Memory lifecycle management - TTL and LRU policies.

Provides:
- TTL (Time-To-Live) expiration policy
- LRU (Least Recently Used) eviction policy
- Scheduled cleanup tasks
- Memory capacity management
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.memory.manager import MemoryManager

logger = get_logger(__name__)


@dataclass
class LifecycleConfig:
    """Configuration for memory lifecycle management."""

    # TTL settings (in hours)
    episodic_ttl: float = 168.0  # 7 days
    semantic_ttl: float = 720.0  # 30 days
    procedural_ttl: float = float("inf")  # Never expire

    # LRU settings
    max_memories: int = 10000  # Maximum number of memories
    lru_min_delete: int = 100  # Minimum memories to delete when over limit
    lru_delete_ratio: float = 0.1  # Delete 10% when over limit

    # Cleanup schedule
    cleanup_interval_hours: float = 1.0  # Run cleanup every hour

    # Importance threshold (memories below this may be deleted sooner)
    low_importance_threshold: float = 0.2
    low_importance_ttl_multiplier: float = 0.5  # Delete low importance memories faster


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    ttl_deleted: int = 0
    lru_deleted: int = 0
    total_deleted: int = 0
    ttl_by_type: dict[str, int] = field(default_factory=dict)
    lru_deleted_ids: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ttl_deleted": self.ttl_deleted,
            "lru_deleted": self.lru_deleted,
            "total_deleted": self.total_deleted,
            "ttl_by_type": self.ttl_by_type,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class MemoryLifecycleManager:
    """Manages memory lifecycle with TTL and LRU policies.

    Features:
    - Automatic TTL-based expiration
    - LRU-based eviction when over capacity
    - Scheduled cleanup tasks
    - Importance-aware deletion
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        config: LifecycleConfig | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._config = config or LifecycleConfig()
        self._cleanup_task: asyncio.Task | None = None
        self._running = False
        self._last_cleanup: datetime | None = None
        self._cleanup_history: list[CleanupResult] = []
        self._max_history = 100  # Keep last 100 cleanup results

    async def start(self) -> None:
        """Start the lifecycle manager (begins scheduled cleanup)."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("memory_lifecycle_manager_started")

    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        logger.info("memory_lifecycle_manager_stopped")

    async def cleanup_expired(self) -> CleanupResult:
        """Manually trigger cleanup of expired memories.

        Returns:
            CleanupResult with details of deleted memories.
        """
        import time

        start_time = time.time()

        result = CleanupResult()

        try:
            # Get all memories and check TTL
            ttl_deleted_by_type: dict[str, int] = {}
            ttl_deleted = 0

            # Check each memory type
            for memory_type in ["episodic", "semantic", "procedural"]:
                deleted = await self._delete_expired_by_type(memory_type)
                ttl_deleted += deleted
                ttl_deleted_by_type[memory_type] = deleted

            result.ttl_deleted = ttl_deleted
            result.ttl_by_type = ttl_deleted_by_type

            # LRU eviction if over limit
            lru_deleted, lru_ids = await self._evict_lru()
            result.lru_deleted = lru_deleted
            result.lru_deleted_ids = lru_ids[:50]  # Keep first 50 for logging

            result.total_deleted = ttl_deleted + lru_deleted
            result.duration_ms = (time.time() - start_time) * 1000

            self._last_cleanup = datetime.now()
            self._cleanup_history.append(result)

            # Trim history
            if len(self._cleanup_history) > self._max_history:
                self._cleanup_history = self._cleanup_history[-self._max_history :]

            logger.info(
                "memory_cleanup_completed",
                ttl_deleted=ttl_deleted,
                lru_deleted=lru_deleted,
                duration_ms=result.duration_ms,
            )

        except Exception as e:
            logger.error("memory_cleanup_failed", error=str(e))
            raise

        return result

    async def _delete_expired_by_type(self, memory_type: str) -> int:
        """Delete expired memories of a specific type.

        Args:
            memory_type: Type of memories to check (episodic, semantic, procedural)

        Returns:
            Number of deleted memories.
        """
        # Get TTL for this type
        ttl_hours = self._get_ttl_for_type(memory_type)

        if ttl_hours == float("inf"):
            # Never expire
            return 0

        cutoff = datetime.now() - timedelta(hours=ttl_hours)
        cutoff_timestamp = cutoff.timestamp()

        # Apply low importance multiplier
        low_importance_cutoff = datetime.now() - timedelta(
            hours=ttl_hours * self._config.low_importance_ttl_multiplier
        )

        # Get memories to delete
        deleted = 0
        batch_size = 100
        offset = 0

        while True:
            # Get old memories
            old_memories = await self._get_old_memories(
                memory_type=memory_type,
                cutoff=cutoff_timestamp,
                limit=batch_size,
                offset=offset,
            )

            if not old_memories:
                break

            for memory in old_memories:
                # Check if memory is expired
                created_at = datetime.fromtimestamp(memory.created_at)

                # Apply low importance faster expiration
                if memory.importance < self._config.low_importance_threshold:
                    effective_cutoff = low_importance_cutoff.timestamp()
                else:
                    effective_cutoff = cutoff_timestamp

                if created_at < datetime.fromtimestamp(effective_cutoff):
                    # Delete expired memory
                    await self._memory_manager.delete(memory.id)
                    deleted += 1

            offset += batch_size

        return deleted

    async def _evict_lru(self) -> tuple[int, list[str]]:
        """Evict least recently used memories if over capacity.

        Returns:
            Tuple of (number deleted, list of deleted IDs)
        """
        # Check current count
        count = await self._memory_manager.count()

        if count <= self._config.max_memories:
            return 0, []

        # Calculate how many to delete
        over_limit = count - self._config.max_memories
        to_delete = max(over_limit, int(count * self._config.lru_delete_ratio))
        to_delete = max(to_delete, self._config.lru_min_delete)

        deleted_ids: list[str] = []

        # Get least recently used memories
        lru_memories = await self._get_lru_memories(limit=to_delete)

        for memory in lru_memories:
            await self._memory_manager.delete(memory.id)
            deleted_ids.append(memory.id)

        logger.info(
            "lru_eviction_completed",
            evicted=len(deleted_ids),
            remaining=await self._memory_manager.count(),
        )

        return len(deleted_ids), deleted_ids

    async def _get_ttl_for_type(self, memory_type: str) -> float:
        """Get TTL hours for a memory type."""
        type_ttl_map = {
            "episodic": self._config.episodic_ttl,
            "semantic": self._config.semantic_ttl,
            "procedural": self._config.procedural_ttl,
        }
        return type_ttl_map.get(memory_type, self._config.episodic_ttl)

    async def _get_old_memories(
        self,
        memory_type: str,
        cutoff: float,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        """Get memories older than cutoff timestamp.

        Args:
            memory_type: Type of memories
            cutoff: Timestamp cutoff
            limit: Maximum to return
            offset: Offset for pagination

        Returns:
            List of memory entries.
        """
        # Access storage directly through manager
        storage = self._memory_manager._storage  # noqa: SLF001

        query = """
            SELECT id, content, memory_type, importance, embedding, tags,
                   source_conversation_id, created_at, last_accessed,
                   access_count, metadata
            FROM memories
            WHERE memory_type = ? AND created_at < ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
        """

        async with storage._db.execute(
            query,
            (memory_type, cutoff, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()

        from deskflow.core.models import MemoryEntry

        return [
            MemoryEntry(
                id=row[0],
                content=row[1],
                memory_type=row[2],
                importance=row[3],
                embedding=json.loads(row[4]) if row[4] else None,
                tags=json.loads(row[5]) if row[5] else [],
                source_conversation_id=row[6],
                created_at=row[7],
                last_accessed=row[8],
                access_count=row[9],
                metadata=json.loads(row[10]) if row[10] else {},
            )
            for row in rows
        ]

    async def _get_lru_memories(self, limit: int) -> list[Any]:
        """Get least recently used memories.

        Args:
            limit: Maximum to return

        Returns:
            List of memory entries, ordered by least recently accessed.
        """
        storage = self._memory_manager._storage  # noqa: SLF001

        # Order by access_count ASC and last_accessed ASC
        query = """
            SELECT id, content, memory_type, importance, embedding, tags,
                   source_conversation_id, created_at, last_accessed,
                   access_count, metadata
            FROM memories
            ORDER BY access_count ASC, last_accessed ASC
            LIMIT ?
        """

        async with storage._db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()

        from deskflow.core.models import MemoryEntry

        return [
            MemoryEntry(
                id=row[0],
                content=row[1],
                memory_type=row[2],
                importance=row[3],
                embedding=json.loads(row[4]) if row[4] else None,
                tags=json.loads(row[5]) if row[5] else [],
                source_conversation_id=row[6],
                created_at=row[7],
                last_accessed=row[8],
                access_count=row[9],
                metadata=json.loads(row[10]) if row[10] else {},
            )
            for row in rows
        ]

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                await asyncio.sleep(self._config.cleanup_interval_hours * 3600)

                if self._running:  # Check again after sleep
                    await self.cleanup_expired()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))
                # Wait before retrying
                await asyncio.sleep(60)

    def get_stats(self) -> dict[str, Any]:
        """Get lifecycle manager statistics."""
        return {
            "running": self._running,
            "last_cleanup": self._last_cleanup.isoformat() if self._last_cleanup else None,
            "cleanup_history_count": len(self._cleanup_history),
            "config": {
                "max_memories": self._config.max_memories,
                "episodic_ttl_hours": self._config.episodic_ttl,
                "semantic_ttl_hours": self._config.semantic_ttl,
                "cleanup_interval_hours": self._config.cleanup_interval_hours,
            },
        }


# Import json at module level for the functions that need it
import json


def get_lifecycle_manager(
    memory_manager: Any,
    config: LifecycleConfig | None = None,
) -> MemoryLifecycleManager:
    """Get or create memory lifecycle manager.

    Args:
        memory_manager: The MemoryManager instance to manage.
        config: Optional lifecycle configuration.

    Returns:
        MemoryLifecycleManager instance.
    """
    return MemoryLifecycleManager(memory_manager, config)


async def create_and_start_lifecycle(
    memory_manager: Any,
    config: LifecycleConfig | None = None,
) -> MemoryLifecycleManager:
    """Create and start a lifecycle manager.

    Args:
        memory_manager: The MemoryManager instance to manage.
        config: Optional lifecycle configuration.

    Returns:
        Started MemoryLifecycleManager instance.
    """
    manager = MemoryLifecycleManager(memory_manager, config)
    await manager.start()
    return manager
