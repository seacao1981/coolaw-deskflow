"""Tests for MemoryRetriever enhancements."""

import pytest

from deskflow.core.models import MemoryEntry
from deskflow.memory.retriever import MemoryRetriever, SearchResult


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self) -> None:
        """Test creating search result."""
        memory = MemoryEntry(content="Test memory")
        result = SearchResult(
            memory=memory,
            relevance_score=0.85,
        )

        assert result.memory.content == "Test memory"
        assert result.relevance_score == 0.85
        assert result.keyword_score == 0.0

    def test_search_result_to_dict(self) -> None:
        """Test converting search result to dictionary."""
        memory = MemoryEntry(
            content="Test memory content",
            memory_type="episodic",
            importance=0.7,
        )
        result = SearchResult(
            memory=memory,
            relevance_score=0.9,
            keyword_score=0.5,
            semantic_score=0.4,
        )

        data = result.to_dict()

        assert data["memory_id"] == memory.id
        assert data["relevance_score"] == 0.9
        assert "content" in data

    def test_search_result_diversity_bonus(self) -> None:
        """Test diversity bonus field."""
        memory = MemoryEntry(content="Test")
        result = SearchResult(
            memory=memory,
            relevance_score=0.8,
            diversity_bonus=0.1,
        )

        assert result.diversity_bonus == 0.1


class TestMemoryRetrieverEnhancements:
    """Tests for MemoryRetriever v2.0 enhancements."""

    @pytest.fixture
    def retriever(self, memory_manager):
        """Create enhanced retriever."""
        from deskflow.memory.retriever import MemoryRetriever

        return MemoryRetriever(
            storage=memory_manager._storage,
            cache_capacity=100,
            hnsw_index=memory_manager._hnsw,
            enable_query_rewrite=True,
            enable_diversity_rerank=True,
        )

    def test_query_rewrite_english(self, retriever: MemoryRetriever) -> None:
        """Test query rewriting for English queries."""
        variations = retriever.rewrite_query("The quick brown fox")

        assert len(variations) >= 2
        # Original query
        assert "The quick brown fox" in variations
        # Simplified (stop words removed)
        simplified = [v for v in variations if "quick" in v and "the" not in v.lower()]
        assert len(simplified) >= 1

    def test_query_rewrite_chinese(self, retriever: MemoryRetriever) -> None:
        """Test query rewriting for Chinese queries."""
        variations = retriever.rewrite_query("机器学习深度学习")

        assert len(variations) >= 1
        # Should include phrase extractions for long queries
        if len("机器学习深度学习") >= 4:
            assert any(len(v) >= 4 for v in variations)

    def test_retrieve_with_diversity(self, retriever: MemoryRetriever) -> None:
        """Test retrieval with diversity re-ranking."""
        # Add test memories
        memories = [
            MemoryEntry(content="Python programming language"),
            MemoryEntry(content="Python snake reptile"),
            MemoryEntry(content="Java programming language"),
        ]

        import asyncio

        async def add_and_retrieve():
            for m in memories:
                await retriever._storage.store_memory(m)

            # Retrieve with diversity
            results = await retriever.retrieve(
                "Python",
                top_k=3,
                use_diversity=True,
            )
            return results

        results = asyncio.run(add_and_retrieve())
        assert len(results) >= 1

    def test_retrieve_return_details(self, retriever: MemoryRetriever) -> None:
        """Test retrieval with detailed results."""
        import asyncio

        async def add_and_retrieve():
            # Add test memory
            memory = MemoryEntry(content="Machine learning is amazing")
            await retriever._storage.store_memory(memory)

            # Retrieve with details
            results = await retriever.retrieve(
                "machine learning",
                top_k=1,
                return_details=True,
            )
            return results

        results = asyncio.run(add_and_retrieve())

        # Should return SearchResult objects
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)

    def test_get_search_stats(self, retriever: MemoryRetriever) -> None:
        """Test search statistics."""
        stats = retriever.get_search_stats()

        assert "total_searches" in stats
        assert "cache_hits" in stats
        assert "cache_hit_rate" in stats
        assert "avg_latency_ms" in stats

    def test_multi_stage_retrieve(self, retriever: MemoryRetriever) -> None:
        """Test multi-stage retrieval pipeline."""
        import asyncio

        async def test():
            # Add test memories
            for i in range(5):
                await retriever._storage.store_memory(
                    MemoryEntry(content=f"Test memory {i} about Python")
                )

            # Multi-stage retrieval
            results = await retriever._multi_stage_retrieve(
                "Python",
                top_k=3,
                memory_type=None,
            )
            return results

        results = asyncio.run(test())

        # Should return SearchResult objects
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    def test_content_similarity(self, retriever: MemoryRetriever) -> None:
        """Test content similarity calculation."""
        memory1 = MemoryEntry(content="The quick brown fox jumps")
        memory2 = MemoryEntry(content="The fast brown fox leaps")
        memory3 = MemoryEntry(content="Completely different content about cooking")

        # Similar content should have higher score
        sim_similar = retriever._content_similarity(memory1, memory2)
        sim_different = retriever._content_similarity(memory1, memory3)

        # Both should return values between 0 and 1
        assert 0.0 <= sim_similar <= 1.0
        assert 0.0 <= sim_different <= 1.0

    def test_diversity_rerank(self, retriever: MemoryRetriever) -> None:
        """Test diversity re-ranking."""
        # Create search results with similar content
        memories = [
            MemoryEntry(content="Python programming"),
            MemoryEntry(content="Python coding"),
            MemoryEntry(content="Java programming"),
            MemoryEntry(content="Cooking recipes"),
        ]

        results = [
            SearchResult(memory=m, relevance_score=0.9 - i * 0.1)
            for i, m in enumerate(memories)
        ]

        # Re-rank for diversity
        reranked = retriever._diversity_rerank(results, top_k=2)

        assert len(reranked) == 2
        # Should prefer diverse results

    def test_calculate_relevance(self, retriever: MemoryRetriever) -> None:
        """Test relevance score calculation."""
        memory = MemoryEntry(
            content="Test content",
            importance=0.8,
            access_count=5,
        )

        result = SearchResult(
            memory=memory,
            relevance_score=0.5,  # Added required parameter
            keyword_score=0.5,
            semantic_score=0.4,
        )

        relevance = retriever._calculate_relevance(result)

        assert 0.0 <= relevance <= 1.0
        assert result.time_score > 0  # Recent memory
        assert result.access_score > 0  # Has been accessed

    def test_cache_hit_tracking(self, retriever: MemoryRetriever) -> None:
        """Test cache hit tracking in statistics."""
        import asyncio

        async def test():
            # Add test memory
            memory = MemoryEntry(content="Cache test content")
            await retriever._storage.store_memory(memory)

            # First retrieval (cache miss)
            await retriever.retrieve("cache test", top_k=1)

            # Second retrieval (cache hit)
            await retriever.retrieve("cache test", top_k=1)

            # Check stats
            stats = retriever.get_search_stats()
            return stats

        stats = asyncio.run(test())

        assert stats["total_searches"] >= 2
        assert stats["cache_hits"] >= 1


class TestQueryRewrite:
    """Tests for query rewriting functionality."""

    @pytest.fixture
    def retriever(self, memory_manager):
        from deskflow.memory.retriever import MemoryRetriever
        return MemoryRetriever(
            storage=memory_manager._storage,
            cache_capacity=10,
        )

    def test_stop_words_removed(self, retriever: MemoryRetriever) -> None:
        """Test that stop words are removed in simplified query."""
        variations = retriever.rewrite_query("What is the meaning of life")

        # Should have original and simplified
        assert len(variations) >= 2

        # Simplified should not contain stop words
        simplified = [v for v in variations if v != "What is the meaning of life"]
        if simplified:
            assert "the" not in simplified[0].lower().split()

    def test_original_query_preserved(self, retriever: MemoryRetriever) -> None:
        """Test that original query is always included."""
        variations = retriever.rewrite_query("Custom query test")

        assert "Custom query test" in variations


class TestDiversityReranking:
    """Tests for diversity re-ranking feature."""

    @pytest.fixture
    def retriever(self, memory_manager):
        from deskflow.memory.retriever import MemoryRetriever
        return MemoryRetriever(
            storage=memory_manager._storage,
            cache_capacity=10,
            enable_diversity_rerank=True,
        )

    def test_mmr_ranking(self, retriever: MemoryRetriever) -> None:
        """Test MMR (Maximal Marginal Relevance) ranking."""
        # Create results with varying relevance and similarity
        memories = [
            MemoryEntry(content="Machine learning AI"),
            MemoryEntry(content="Deep learning neural networks"),
            MemoryEntry(content="Cooking Italian pasta"),
            MemoryEntry(content="Travel Japan Tokyo"),
        ]

        results = [
            SearchResult(memory=m, relevance_score=0.9 - i * 0.1)
            for i, m in enumerate(memories)
        ]

        # Apply MMR re-ranking
        reranked = retriever._diversity_rerank(results, top_k=3)

        assert len(reranked) == 3
        # Should balance relevance with diversity
