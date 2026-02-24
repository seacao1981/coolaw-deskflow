"""Memory manager - unified entry point for memory operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from deskflow.core.recent_entities import RecentEntitiesCache
from deskflow.memory.consolidator import MemoryConsolidator, ConsolidationResult
from deskflow.memory.hnsw_index import HNSWIndex
from deskflow.memory.lifecycle import LifecycleConfig, MemoryLifecycleManager
from deskflow.memory.retriever import MemoryRetriever
from deskflow.memory.storage import MemoryStorage
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.models import MemoryEntry, Message
    from deskflow.llm.client import LLMClient

logger = get_logger(__name__)


class MemoryManager:
    """Unified memory manager that coordinates storage and retrieval.

    Implements MemoryProtocol for injection into Agent.
    Features:
    - LRU cache for fast lookups (<10ms)
    - FTS5 full-text search
    - HNSW semantic vector search
    - Daily consolidation with LLM insights
    - Recent entities cache for short-term context
    """

    def __init__(
        self,
        db_path: str | Path,
        cache_capacity: int = 1000,
        hnsw_dim: int = 384,
        hnsw_max_elements: int = 100000,
        enable_consolidation: bool = True,
        enable_lifecycle: bool = True,
        lifecycle_config: LifecycleConfig | None = None,
        recent_entities_max: int = 20,
        recent_entities_ttl: float = 300.0,  # 5 minutes
    ) -> None:
        self._storage = MemoryStorage(db_path)
        self._hnsw = HNSWIndex(
            dim=hnsw_dim,
            max_elements=hnsw_max_elements,
            index_dir=Path(db_path).parent / "hnsw",
        )
        self._retriever = MemoryRetriever(
            storage=self._storage,
            cache_capacity=cache_capacity,
            hnsw_index=self._hnsw,
        )
        self._consolidator: MemoryConsolidator | None = None
        if enable_consolidation:
            self._consolidator = MemoryConsolidator(
                storage=self._storage,
                hnsw_index=self._hnsw,
            )
        self._lifecycle: MemoryLifecycleManager | None = None
        if enable_lifecycle:
            self._lifecycle = MemoryLifecycleManager(
                memory_manager=self,
                config=lifecycle_config,
            )

        # Recent entities cache for short-term context
        self._recent_entities = RecentEntitiesCache(
            max_entities=recent_entities_max,
            ttl_seconds=recent_entities_ttl,
        )

        self._initialized = False
        self._llm_client: LLMClient | None = None

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Set LLM client for consolidation insights."""
        self._llm_client = llm_client
        if self._consolidator:
            self._consolidator._llm = llm_client

    async def initialize(self) -> None:
        """Initialize storage (create tables etc.)."""
        await self._storage.initialize()

        # Rebuild HNSW index from database on startup
        # This ensures memories in DB are available in the vector index
        await self.rebuild_hnsw_index()

        # Start lifecycle manager if enabled
        if self._lifecycle:
            await self._lifecycle.start()

        self._initialized = True
        logger.info("memory_manager_initialized")

    async def close(self) -> None:
        """Close storage connection and save HNSW index."""
        # Stop lifecycle manager
        if self._lifecycle:
            try:
                await self._lifecycle.stop()
            except Exception as e:
                logger.warning("lifecycle_stop_failed", error=str(e))

        # Save HNSW index before closing
        try:
            self._hnsw.save_index()
            logger.info("hnsw_index_saved_on_close")
        except Exception as e:
            logger.warning("hnsw_save_on_close_failed", error=str(e))

        await self._storage.close()
        self._initialized = False

    # ========== Recent Entities Methods ==========

    def add_recent_entity(
        self,
        entity_type: str,
        name: str,
        action: str,
        location: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Add a recently manipulated entity to short-term cache.

        Args:
            entity_type: Type (file, folder, process, etc.)
            name: Name or identifier
            action: Action performed (create, delete, modify, etc.)
            location: Optional location path
            metadata: Optional additional metadata
        """
        self._recent_entities.add(entity_type, name, action, location, metadata)
        logger.debug(
            "recent_entity_added",
            entity_type=entity_type,
            name=name,
            action=action,
        )

    def get_recent_entities(
        self,
        limit: int = 5,
        max_age_seconds: float | None = None,
        entity_type: str | None = None,
    ) -> list:
        """Get recent entities.

        Args:
            limit: Maximum number to return
            max_age_seconds: Only return entities newer than this
            entity_type: Filter by type

        Returns:
            List of RecentEntity objects
        """
        return self._recent_entities.get_recent(limit, max_age_seconds, entity_type)

    def get_last_entity(
        self,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        """Get the most recent entity.

        Args:
            entity_type: Filter by type
            action: Filter by action

        Returns:
            The most recent entity or None
        """
        return self._recent_entities.get_last(entity_type, action)

    def get_recent_entities_context(self, limit: int = 3) -> str:
        """Get a prompt-ready context string of recent entities.

        Args:
            limit: Maximum number of entities to include

        Returns:
            Context string for prompts
        """
        return self._recent_entities.to_prompts()

    def clear_recent_entities(self) -> None:
        """Clear all recent entities."""
        self._recent_entities.clear()

    # ========== Conversation History Methods ==========

    async def save_conversation(
        self,
        conversation_id: str,
        messages: list[Message],
        title: str | None = None,
    ) -> None:
        """Save a conversation to persistent storage.

        Args:
            conversation_id: The conversation ID
            messages: List of messages
            title: Optional conversation title
        """
        await self._storage.save_conversation(conversation_id, messages, title)

    async def load_conversation(self, conversation_id: str) -> list[Message] | None:
        """Load a conversation from persistent storage.

        Args:
            conversation_id: The conversation ID

        Returns:
            List of messages or None if not found
        """
        return await self._storage.load_conversation(conversation_id)

    async def get_conversation_ids(self, limit: int = 50) -> list[str]:
        """Get list of recent conversation IDs."""
        return await self._storage.get_conversation_ids(limit)

    # ========== Memory Storage Methods ==========

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry.

        Generates embedding and adds to HNSW index automatically.

        Returns:
            The memory ID.
        """
        # Generate embedding if not already present
        if entry.embedding is None:
            try:
                embeddings = self._hnsw.embed([entry.content])
                if len(embeddings) > 0:
                    entry.embedding = embeddings[0].tolist()
            except Exception as e:
                logger.warning("embedding_generation_failed", error=str(e))

        # Store in database
        result = await self._storage.store_memory(entry)

        # Add to HNSW index
        try:
            self._hnsw.add_items([entry.content], [result])
        except Exception as e:
            logger.warning("hnsw_add_failed", error=str(e))

        # Invalidate cache since data changed
        self._retriever.invalidate_cache()
        return result

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_type: str | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories.

        Args:
            query: Search query.
            top_k: Maximum results.
            memory_type: Optional type filter.

        Returns:
            List of relevant memory entries.
        """
        return await self._retriever.retrieve(query, top_k, memory_type)

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Get a specific memory by ID."""
        return await self._storage.get_by_id(memory_id)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory. Returns True if deleted."""
        result = await self._storage.delete_memory(memory_id)
        if result:
            self._retriever.invalidate_cache()
        return result

    async def count(self) -> int:
        """Return total stored memory count."""
        return await self._storage.count()

    async def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Get the most recent memories."""
        return await self._storage.get_recent(limit)

    async def rebuild_hnsw_index(self, batch_size: int = 100) -> int:
        """Rebuild HNSW index from existing database memories.

        This is useful when restarting the service - memories in the database
        that are not in the HNSW index will be added.

        Args:
            batch_size: Number of memories to process in each batch

        Returns:
            Number of memories added to the index
        """
        # Get all memories without embedding
        all_memories = await self._storage.get_recent(limit=10000)

        added = 0
        texts_to_add = []
        ids_to_add = []

        for memory in all_memories:
            # Generate embedding if missing
            if memory.embedding is None:
                try:
                    embeddings = self._hnsw.embed([memory.content])
                    if len(embeddings) > 0:
                        memory.embedding = embeddings[0].tolist()
                        # Update in database
                        await self._storage._db.execute(
                            "UPDATE memories SET embedding = ? WHERE id = ?",
                            (json.dumps(memory.embedding), memory.id),
                        )
                except Exception as e:
                    logger.warning("embedding_generation_failed", error=str(e))
                    continue

            texts_to_add.append(memory.content)
            ids_to_add.append(memory.id)
            added += 1

        # Batch add to HNSW index
        if texts_to_add:
            try:
                self._hnsw.add_items(texts_to_add, ids_to_add)
            except Exception as e:
                logger.warning("hnsw_batch_add_failed", error=str(e))

        await self._storage._db.commit()
        logger.info("hnsw_index_rebuilt", memories_added=added)
        return added

    def cache_stats(self) -> dict[str, object]:
        """Return retrieval cache statistics."""
        return self._retriever.cache_stats()

    async def consolidate_daily(self, hours_back: int = 24) -> ConsolidationResult:
        """Run daily memory consolidation.

        Args:
            hours_back: How many hours of memories to review

        Returns:
            Consolidation results
        """
        if not self._consolidator:
            return ConsolidationResult(insights=[], compressed_memories=[], updated_index=False)

        return await self._consolidator.consolidate_daily(hours_back=hours_back)

    async def cleanup_memories(self) -> dict:
        """Manually trigger memory cleanup (TTL + LRU).

        Returns:
            Cleanup result dictionary.
        """
        if not self._lifecycle:
            return {"error": "Lifecycle management not enabled"}

        result = await self._lifecycle.cleanup_expired()
        return result.to_dict()

    def get_stats(self) -> dict:
        """Get memory manager statistics."""
        stats = {
            "cache": self._retriever.cache_stats(),
            "hnsw": self._hnsw.get_stats() if self._hnsw else {},
            "recent_entities": {
                "count": len(self._recent_entities.get_recent(limit=100)),
            },
        }
        if self._consolidator:
            stats["consolidation"] = self._consolidator.get_stats()
        if self._lifecycle:
            stats["lifecycle"] = self._lifecycle.get_stats()
        return stats
