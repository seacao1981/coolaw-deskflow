"""Memory retriever with multi-path recall and caching.

Retrieval paths:
- L1: LRU in-memory cache (< 1ms)
- L2: FTS5 full-text search (< 50ms)
- L3: HNSW semantic similarity search (< 200ms)

Results are merged, ranked, and deduplicated.

Enhancements in v2.0:
- Query rewriting for better recall
- Diversity re-ranking
- Multi-stage retrieval
- SearchResult with detailed metadata
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deskflow.errors import MemoryRetrievalError
from deskflow.memory.cache import LRUCache
from deskflow.memory.hnsw_index import HNSWIndex
from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.models import MemoryEntry
    from deskflow.memory.storage import MemoryStorage

logger = get_logger(__name__)

# Time decay factor: memories lose relevance over time
TIME_DECAY_HALF_LIFE_DAYS = 30.0
SECONDS_PER_DAY = 86400.0


@dataclass
class SearchResult:
    """Search result with detailed metadata."""

    memory: MemoryEntry
    relevance_score: float
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    time_score: float = 0.0
    access_score: float = 0.0
    diversity_bonus: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory.id,
            "content": self.memory.content[:200],
            "relevance_score": self.relevance_score,
            "keyword_score": self.keyword_score,
            "semantic_score": self.semantic_score,
            "time_score": self.time_score,
            "access_score": self.access_score,
            "diversity_bonus": self.diversity_bonus,
        }


class MemoryRetriever:
    """Multi-path memory retriever with caching and ranking.

    Combines FTS5 keyword search, HNSW semantic search, importance scoring and
    time decay to produce the most relevant results.

    Enhancements:
    - Query rewriting for better recall
    - Diversity re-ranking for varied results
    - Multi-stage retrieval pipeline
    - Detailed search result metadata
    """

    def __init__(
        self,
        storage: MemoryStorage,
        cache_capacity: int = 1000,
        hnsw_index: HNSWIndex | None = None,
        enable_query_rewrite: bool = True,
        enable_diversity_rerank: bool = True,
    ) -> None:
        self._storage = storage
        self._cache = LRUCache(capacity=cache_capacity)
        self._hnsw = hnsw_index
        self._enable_query_rewrite = enable_query_rewrite
        self._enable_diversity_rerank = enable_diversity_rerank
        self._search_stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "avg_latency_ms": 0.0,
        }

    def rewrite_query(self, query: str) -> list[str]:
        """Rewrite query for better recall.

        Generates multiple query variations:
        - Original query
        - Expanded query (add related terms)
        - Simplified query (remove stop words)

        Args:
            query: Original query

        Returns:
            List of query variations
        """
        variations = [query]

        # Simplified query (remove common stop words)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being"}
        words = query.split()
        simplified = " ".join(w for w in words if w.lower() not in stop_words)
        if simplified and simplified != query:
            variations.append(simplified)

        # For Chinese queries, extract key phrases
        if any('\u4e00' <= c <= '\u9fff' for c in query):
            # Extract 2-4 character phrases
            if len(query) >= 4:
                variations.append(query[:4])
            if len(query) >= 6:
                variations.append(query[2:6])

        return variations

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_type: str | None = None,
        use_diversity: bool = True,
        return_details: bool = False,
    ) -> list[MemoryEntry] | list[SearchResult]:
        """Retrieve relevant memories using multi-path search.

        Args:
            query: Search query.
            top_k: Maximum results to return.
            memory_type: Optional filter by memory type.
            use_diversity: Whether to apply diversity re-ranking.
            return_details: Whether to return detailed search results.

        Returns:
            List of relevant memories or detailed search results.
        """
        start = time.time()
        self._search_stats["total_searches"] += 1

        # Check cache with original query
        cached = self._cache.get(query, top_k, memory_type)
        if cached is not None:
            duration_ms = (time.time() - start) * 1000
            self._search_stats["cache_hits"] += 1
            self._update_avg_latency(duration_ms)
            logger.debug(
                "memory_cache_hit",
                query=query[:50],
                results=len(cached),
                duration_ms=round(duration_ms, 2),
            )
            return cached  # type: ignore[no-any-return]

        try:
            # Multi-stage retrieval
            all_results = await self._multi_stage_retrieve(query, top_k, memory_type)

            # Filter by type if specified
            if memory_type:
                all_results = [
                    m for m in all_results if m.memory.memory_type == memory_type
                ]

            # Apply diversity re-ranking
            if use_diversity and self._enable_diversity_rerank:
                ranked = self._diversity_rerank(all_results, top_k)
            else:
                ranked = self._rank_results(all_results, query)[:top_k]

            # Extract MemoryEntry objects
            final_memories = [r.memory for r in ranked]

            # Store in cache
            self._cache.put(query, top_k, memory_type, final_memories)

            duration_ms = (time.time() - start) * 1000
            self._update_avg_latency(duration_ms)
            logger.info(
                "memory_retrieved",
                query=query[:50],
                candidates=len(all_results),
                results=len(final_memories),
                duration_ms=round(duration_ms, 2),
            )

            if return_details:
                return ranked
            return final_memories

        except Exception as e:
            raise MemoryRetrievalError(str(e)) from e

    async def _multi_stage_retrieve(
        self,
        query: str,
        top_k: int,
        memory_type: str | None,
    ) -> list[SearchResult]:
        """Multi-stage retrieval pipeline.

        Stage 1: FTS5 full-text search
        Stage 2: HNSW semantic search
        Stage 3: Merge and score
        """
        # Stage 1: FTS5 full-text search
        fts_results = await self._storage.search_fts(query, limit=top_k * 3)

        fts_search_results = []
        for entry in fts_results:
            result = SearchResult(
                memory=entry,
                relevance_score=0.0,
                keyword_score=0.7,  # Initial keyword score
            )
            fts_search_results.append(result)

        # Stage 2: HNSW semantic search
        semantic_results = []
        if self._hnsw:
            hnsw_results = self._hnsw.search(query, top_k=top_k * 2)
            for item_id, similarity in hnsw_results:
                semantic_results.append((item_id, similarity))

        # Stage 3: Merge results
        all_results = await self._merge_results_v2(fts_search_results, semantic_results, query)

        return all_results

    async def _merge_results_v2(
        self,
        fts_results: list[SearchResult],
        semantic_results: list[tuple[str, float]],
        query: str,
    ) -> list[SearchResult]:
        """Merge FTS and semantic search results with detailed scoring.

        Args:
            fts_results: FTS search results
            semantic_results: HNSW semantic search results
            query: Original query

        Returns:
            Merged and scored search results
        """
        # Create ID to FTS result mapping
        fts_by_id = {r.memory.id: r for r in fts_results}
        semantic_id_set = set(id for id, _ in semantic_results)

        merged = []

        # Process FTS results with semantic bonus
        for result in fts_results:
            if result.memory.id in semantic_id_set:
                # Boost for semantic match
                result.semantic_score = 0.3
                result.diversity_bonus = 0.1
            result.relevance_score = self._calculate_relevance(result)
            merged.append(result)

        # Add semantic-only results
        for item_id, similarity in semantic_results:
            if item_id not in fts_by_id:
                # Fetch from storage
                try:
                    entry = await self._storage.get_by_id(item_id)
                    if entry:
                        result = SearchResult(
                            memory=entry,
                            relevance_score=0.0,
                            semantic_score=similarity * 0.5,
                            keyword_score=0.0,
                        )
                        result.relevance_score = self._calculate_relevance(result)
                        merged.append(result)
                except Exception:
                    pass

        return merged

    def _calculate_relevance(self, result: SearchResult) -> float:
        """Calculate overall relevance score.

        Combines:
        - Keyword score (FTS match)
        - Semantic score (vector similarity)
        - Time score (recency)
        - Access score (frequency)
        """
        memory = result.memory
        now = time.time()

        # Time decay score
        age_days = (now - memory.created_at) / SECONDS_PER_DAY
        result.time_score = 0.5 ** (age_days / TIME_DECAY_HALF_LIFE_DAYS)

        # Access frequency score
        result.access_score = min(math.log1p(memory.access_count) / 5.0, 1.0)

        # Weighted combination
        relevance = (
            result.keyword_score * 0.35 +
            result.semantic_score * 0.30 +
            result.time_score * 0.25 +
            result.access_score * 0.1 +
            result.diversity_bonus
        )

        return round(relevance, 4)

    def _diversity_rerank(
        self,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Re-rank for diversity using Maximal Marginal Relevance (MMR).

        Balances relevance with diversity to avoid redundant results.

        Args:
            results: Search results to re-rank
            top_k: Number of results to return

        Returns:
            Re-ranked results with diversity consideration
        """
        if len(results) <= top_k:
            return results

        selected = []
        remaining = list(results)

        # MMR parameter (0 = pure diversity, 1 = pure relevance)
        mmr_lambda = 0.7

        while len(selected) < top_k and remaining:
            best_score = -float("inf")
            best_idx = 0

            for i, result in enumerate(remaining):
                # Relevance score
                relevance = result.relevance_score

                # Diversity penalty (similarity to already selected)
                diversity_penalty = 0.0
                if selected:
                    max_similarity = max(
                        self._content_similarity(result.memory, s.memory)
                        for s in selected
                    )
                    diversity_penalty = max_similarity

                # MMR score
                mmr_score = mmr_lambda * relevance - (1 - mmr_lambda) * diversity_penalty

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            # Select best result
            selected.append(remaining.pop(best_idx))

        return selected

    def _content_similarity(
        self,
        memory1: MemoryEntry,
        memory2: MemoryEntry,
    ) -> float:
        """Calculate content similarity between two memories.

        Uses simple Jaccard similarity for efficiency.

        Args:
            memory1: First memory
            memory2: Second memory

        Returns:
            Similarity score (0-1)
        """
        terms1 = set(memory1.content.lower().split())
        terms2 = set(memory2.content.lower().split())

        if not terms1 or not terms2:
            return 0.0

        intersection = len(terms1 & terms2)
        union = len(terms1 | terms2)

        return intersection / max(union, 1)

    def _rank_results(
        self,
        entries: list[SearchResult],
        query: str,
    ) -> list[SearchResult]:
        """Rank search results by combined relevance score.

        Args:
            entries: Search results to rank
            query: Original query

        Returns:
            Ranked results
        """
        # Update scores with query-specific keyword matching
        query_terms = set(query.lower().split())

        for entry in entries:
            # Update keyword score based on term overlap
            content_terms = set(entry.memory.content.lower().split())
            overlap = len(query_terms & content_terms)
            entry.keyword_score = max(
                entry.keyword_score,
                overlap / max(len(query_terms), 1)
            )
            entry.relevance_score = self._calculate_relevance(entry)

        # Sort by relevance descending
        entries.sort(key=lambda x: x.relevance_score, reverse=True)

        # Deduplicate by content similarity
        seen_content: set[str] = set()
        unique: list[SearchResult] = []
        for entry in entries:
            content_key = entry.memory.content[:100].lower()
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique.append(entry)

        return unique

    def invalidate_cache(self) -> None:
        """Clear the retrieval cache."""
        self._cache.invalidate()

    def cache_stats(self) -> dict[str, object]:
        """Return cache statistics."""
        return self._cache.stats()

    def get_search_stats(self) -> dict[str, object]:
        """Return search statistics."""
        return {
            "total_searches": self._search_stats.get("total_searches", 0),
            "cache_hits": self._search_stats.get("cache_hits", 0),
            "cache_hit_rate": (
                self._search_stats["cache_hits"] / max(self._search_stats["total_searches"], 1)
            ),
            "avg_latency_ms": round(self._search_stats.get("avg_latency_ms", 0.0), 2),
        }

    def _update_avg_latency(self, new_latency: float) -> None:
        """Update average latency with new measurement."""
        total = self._search_stats["total_searches"]
        old_avg = self._search_stats["avg_latency_ms"]
        # Running average
        self._search_stats["avg_latency_ms"] = (
            (old_avg * (total - 1) + new_latency) / total
        )
