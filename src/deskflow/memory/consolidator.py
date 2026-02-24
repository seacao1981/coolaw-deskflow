"""Memory consolidator for daily review and long-term memory optimization.

Runs periodically to:
1. Extract insights from recent memories
2. Compress and merge related memories
3. Update HNSW index with new embeddings
4. Generate daily summary reports

Enhancements in v2.0:
- Batch processing for large memory sets
- Topic clustering before compression
- Incremental consolidation
- Quality scoring for compressed memories
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.models import MemoryEntry
    from deskflow.llm.client import LLMClient
    from deskflow.memory.storage import MemoryStorage
    from deskflow.memory.hnsw_index import HNSWIndex

logger = get_logger(__name__)


class MemoryConsolidator:
    """Daily memory consolidation processor.

    Mimics human sleep consolidation - reviews daily experiences,
    extracts key insights, and compresses into long-term memory.

    Enhancements:
    - Topic clustering before compression
    - Batch processing for efficiency
    - Quality scoring for compressed memories
    - Incremental consolidation support
    """

    def __init__(
        self,
        storage: MemoryStorage,
        hnsw_index: HNSWIndex | None = None,
        llm_client: LLMClient | None = None,
        batch_size: int = 50,
        max_consolidate_per_run: int = 200,
    ) -> None:
        self._storage = storage
        self._hnsw = hnsw_index
        self._llm = llm_client
        self._last_consolidation: datetime | None = None
        self._batch_size = batch_size
        self._max_consolidate_per_run = max_consolidate_per_run
        self._consolidation_stats = {
            "total_runs": 0,
            "total_insights": 0,
            "total_compressed": 0,
        }

    async def consolidate_daily(
        self,
        hours_back: int = 24,
        compress_threshold: int = 10,
        enable_clustering: bool = True,
    ) -> ConsolidationResult:
        """Run daily memory consolidation.

        Args:
            hours_back: How many hours of memories to review
            compress_threshold: Min memories to trigger compression
            enable_clustering: Whether to cluster memories before compression

        Returns:
            Consolidation results with insights and compressed memories
        """
        cutoff = datetime.now() - timedelta(hours=hours_back)

        # Get recent memories
        recent = await self._storage.get_recent(limit=self._max_consolidate_per_run, since=cutoff)

        if not recent:
            logger.info("no_memories_to_consolidate", hours_back=hours_back)
            return ConsolidationResult(
                insights=[],
                compressed_memories=[],
                updated_index=False,
            )

        logger.info("starting_consolidation", memories=len(recent), hours=hours_back)

        # Extract insights using LLM (batch processing)
        insights = await self._extract_insights_batched(recent)

        # Cluster and compress related memories
        compressed = []
        if enable_clustering and len(recent) >= compress_threshold:
            compressed = await self._cluster_and_compress(recent, compress_threshold)
        else:
            compressed = await self._compress_memories(recent, compress_threshold)

        # Update HNSW index
        index_updated = await self._update_index(recent)

        self._last_consolidation = datetime.now()
        self._consolidation_stats["total_runs"] += 1
        self._consolidation_stats["total_insights"] += len(insights)
        self._consolidation_stats["total_compressed"] += len(compressed)

        logger.info(
            "consolidation_complete",
            insights=len(insights),
            compressed=len(compressed),
            index_updated=index_updated,
        )

        return ConsolidationResult(
            insights=insights,
            compressed_memories=compressed,
            updated_index=index_updated,
        )

    async def _extract_insights_batched(
        self,
        memories: list[MemoryEntry],
        batch_size: int = 20,
    ) -> list[Insight]:
        """Extract insights from memories in batches.

        Args:
            memories: Memories to analyze
            batch_size: Number of memories per batch

        Returns:
            List of extracted insights
        """
        if not self._llm or not memories:
            return []

        all_insights = []

        # Process in batches
        for i in range(0, len(memories), batch_size):
            batch = memories[i:i + batch_size]

            # Prepare memory content for analysis
            content = "\n".join(
                f"- [{m.memory_type}] {m.content[:200]}" for m in batch
            )

            prompt = f"""Review these conversation memories and extract key insights:

{content}

For each insight, provide:
1. A brief title (2-5 words)
2. The insight content (1-2 sentences)
3. Category: fact, preference, skill, or pattern

Format as JSON array:
[
  {{"title": "...", "content": "...", "category": "fact"}},
  ...
]

Return at most 5 key insights."""

            try:
                response = await self._llm.chat(prompt, max_tokens=500)
                insights_json = response.content.strip()

                # Parse JSON
                insights_data = json.loads(insights_json)
                batch_insights = [
                    Insight(
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        category=item.get("category", "general"),
                        confidence=item.get("confidence", 0.8),
                    )
                    for item in insights_data[:5]
                ]

                # Save insights as meta-memories
                for insight in batch_insights:
                    await self._storage.store_memory(
                        MemoryEntry(
                            content=f"Insight: {insight.title} - {insight.content}",
                            memory_type="insight",
                            importance=0.8,
                            metadata={"category": insight.category},
                        )
                    )

                all_insights.extend(batch_insights)

            except Exception as e:
                logger.warning("insight_extraction_failed", error=str(e))

        return all_insights

    async def _cluster_and_compress(
        self,
        memories: list[MemoryEntry],
        threshold: int,
    ) -> list[MemoryEntry]:
        """Cluster memories by topic and compress each cluster.

        Args:
            memories: Memories to potentially compress
            threshold: Minimum cluster size to trigger compression

        Returns:
            List of newly created compressed memories
        """
        if not self._hnsw or len(memories) < threshold:
            return await self._compress_memories(memories, threshold)

        # Use HNSW to find similar memories and cluster them
        clusters: dict[str, list[MemoryEntry]] = {}

        for memory in memories:
            # Find similar memories
            similar = self._hnsw.search(memory.content, top_k=5)

            if similar:
                # Use most similar ID as cluster key
                cluster_key = similar[0][0]
                if cluster_key not in clusters:
                    clusters[cluster_key] = []
                clusters[cluster_key].append(memory)

        # Compress each cluster
        compressed = []
        for cluster_key, cluster_memories in clusters.items():
            if len(cluster_memories) >= threshold // 2:  # Lower threshold for clusters
                result = await self._compress_cluster(cluster_memories)
                if result:
                    compressed.append(result)

        return compressed

    async def _compress_cluster(
        self,
        cluster: list[MemoryEntry],
    ) -> MemoryEntry | None:
        """Compress a cluster of memories into a summary.

        Args:
            cluster: Cluster of related memories

        Returns:
            Compressed memory entry or None
        """
        if not self._llm or not cluster:
            return None

        content = "\n".join(m.content[:150] for m in cluster[-10:])
        memory_types = set(m.memory_type for m in cluster)

        prompt = f"""Summarize these related memories (types: {', '.join(memory_types)}) into 1-2 concise sentences:

{content}

Create a summary that captures the key information without redundancy."""

        try:
            response = await self._llm.chat(prompt, max_tokens=200)
            summary = response.content.strip()

            # Calculate quality score
            quality_score = self._calculate_compression_quality(cluster, summary)

            # Create compressed memory
            compressed_memory = MemoryEntry(
                content=summary,
                memory_type="compressed",
                importance=0.6,
                metadata={
                    "source_count": len(cluster),
                    "quality_score": quality_score,
                    "source_ids": [m.id for m in cluster],
                },
            )
            await self._storage.store_memory(compressed_memory)

            logger.info(
                "cluster_compressed",
                original=len(cluster),
                quality=quality_score,
            )
            return compressed_memory

        except Exception as e:
            logger.warning("cluster_compression_failed", error=str(e))
            return None

    def _calculate_compression_quality(
        self,
        originals: list[MemoryEntry],
        summary: str,
    ) -> float:
        """Calculate quality score for compressed memory.

        Args:
            originals: Original memories
            summary: Compressed summary

        Returns:
            Quality score (0-1)
        """
        if not originals or not summary:
            return 0.0

        # Factors:
        # 1. Compression ratio (shorter is better, but not too short)
        original_length = sum(len(m.content) for m in originals)
        summary_length = len(summary)
        ratio = summary_length / max(original_length, 1)

        # Ideal ratio: 0.1-0.3 (10-30% of original)
        if 0.1 <= ratio <= 0.3:
            ratio_score = 1.0
        elif ratio < 0.1:
            ratio_score = ratio / 0.1 * 0.5  # Too short
        else:
            ratio_score = max(0, 1.0 - (ratio - 0.3))  # Too long

        # 2. Coverage (summary should mention key terms from originals)
        original_terms = set()
        for m in originals:
            original_terms.update(m.content.lower().split()[:10])

        summary_terms = set(summary.lower().split())
        coverage = len(original_terms & summary_terms) / max(len(original_terms), 1)

        # Combined score
        quality = 0.5 * ratio_score + 0.5 * min(coverage, 1.0)
        return round(quality, 2)

    async def _compress_memories(
        self,
        memories: list[MemoryEntry],
        threshold: int,
    ) -> list[MemoryEntry]:
        """Compress related memories into summary memories.

        Groups similar memories and creates consolidated summaries.

        Args:
            memories: Memories to potentially compress
            threshold: Minimum similar memories to trigger compression

        Returns:
            List of newly created compressed memories
        """
        if len(memories) < threshold:
            return []

        # Group by type and content similarity
        groups: dict[str, list[MemoryEntry]] = {}
        for memory in memories:
            key = memory.memory_type
            if key not in groups:
                groups[key] = []
            groups[key].append(memory)

        compressed = []

        for memory_type, type_memories in groups.items():
            if len(type_memories) < threshold:
                continue

            # Create summary using LLM
            if self._llm:
                content = "\n".join(m.content[:150] for m in type_memories[-10:])

                prompt = f"""Summarize these related {memory_type} memories into 1-2 concise sentences:

{content}

Create a summary that captures the key information without redundancy."""

                try:
                    response = await self._llm.chat(prompt, max_tokens=200)
                    summary = response.content.strip()

                    # Create compressed memory
                    compressed_memory = MemoryEntry(
                        content=summary,
                        memory_type=f"compressed_{memory_type}",
                        importance=0.6,
                        metadata={
                            "source_count": len(type_memories),
                            "source_ids": [m.id for m in type_memories],
                        },
                    )
                    await self._storage.store_memory(compressed_memory)
                    compressed.append(compressed_memory)

                    logger.info(
                        "memories_compressed",
                        type=memory_type,
                        original=len(type_memories),
                        summary=summary[:50],
                    )

                except Exception as e:
                    logger.warning("memory_compression_failed", error=str(e))

        return compressed

    async def _update_index(self, memories: list[MemoryEntry]) -> bool:
        """Update HNSW index with new memory embeddings.

        Args:
            memories: Memories to add to index

        Returns:
            True if index was updated
        """
        if not self._hnsw or not memories:
            return False

        try:
            # Generate embeddings for new memories
            texts = [m.content for m in memories]
            ids = [m.id for m in memories]
            metadata = [
                {"content": m.content, "tags": m.tags, "memory_type": m.memory_type}
                for m in memories
            ]

            self._hnsw.add_items(texts, ids, metadata)
            self._hnsw.save_index()

            logger.info("hnsw_index_updated", count=len(memories))
            return True

        except Exception as e:
            logger.warning("hnsw_update_failed", error=str(e))
            return False

    def get_stats(self) -> dict:
        """Get consolidation statistics."""
        return {
            "last_consolidation": (
                self._last_consolidation.isoformat() if self._last_consolidation else None
            ),
            "total_runs": self._consolidation_stats.get("total_runs", 0),
            "total_insights": self._consolidation_stats.get("total_insights", 0),
            "total_compressed": self._consolidation_stats.get("total_compressed", 0),
        }


class Insight:
    """Extracted insight from memory analysis."""

    def __init__(
        self,
        title: str,
        content: str,
        category: str = "general",
        confidence: float = 0.8,
    ) -> None:
        self.title = title
        self.content = content
        self.category = category
        self.confidence = confidence

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
        }


class ConsolidationResult:
    """Result of daily memory consolidation."""

    def __init__(
        self,
        insights: list[Insight],
        compressed_memories: list[MemoryEntry],
        updated_index: bool,
    ) -> None:
        self.insights = insights
        self.compressed_memories = compressed_memories
        self.updated_index = updated_index

    @property
    def insight_count(self) -> int:
        return len(self.insights)

    @property
    def compressed_count(self) -> int:
        return len(self.compressed_memories)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "insights": [i.to_dict() for i in self.insights],
            "compressed_count": self.compressed_count,
            "updated_index": self.updated_index,
        }
