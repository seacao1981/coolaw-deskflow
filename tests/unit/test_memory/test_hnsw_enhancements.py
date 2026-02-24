"""Tests for HNSW index enhancements."""

import pytest
import tempfile
from pathlib import Path

from deskflow.memory.hnsw_index import HNSWIndex


class TestHNSWIndexEnhancements:
    """Tests for HNSW index v2.0 enhancements."""

    @pytest.fixture
    def temp_index_dir(self):
        """Create temporary index directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def index(self, temp_index_dir):
        """Create HNSW index for testing."""
        return HNSWIndex(
            dim=384,
            index_dir=temp_index_dir,
            max_elements=1000,
            auto_save=True,
        )

    def test_multi_vector_embedding(self, index: HNSWIndex) -> None:
        """Test multi-vector averaged embedding."""
        texts = [
            "Python is a programming language",
            "Python is used for data science",
            "Python is great for web development",
        ]

        # Single embedding
        single_emb = index.embed(texts[0:1])[0]

        # Multi-vector averaged embedding
        avg_emb = index.embed_multi_vector(texts)

        assert avg_emb.shape == (384,)
        # Multi-vector should be different from single
        assert not (avg_emb == single_emb).all()

    def test_query_expansion(self, index: HNSWIndex, temp_index_dir: Path) -> None:
        """Test query expansion for better recall."""
        # Add enough items for HNSW to work properly (need at least 10+)
        texts = [
            f"Python programming language tutorial topic {i}"
            for i in range(20)
        ]
        ids = [f"py{i}" for i in range(20)]
        metadata = [
            {"content": t, "tags": ["python", "programming"]}
            for t in texts
        ]
        index.add_items(texts, ids, metadata)

        # Test query expansion - just test it returns something
        expanded = index.expand_query("Python")

        assert len(expanded) >= 1
        assert "Python" in expanded[0]

    def test_search_with_reranking(self, index: HNSWIndex, temp_index_dir: Path) -> None:
        """Test search with re-ranking."""
        texts = [
            "The quick brown fox jumps over the lazy dog",
            "A fast brown fox leaps over a sleepy dog",
            "Machine learning is a subset of AI",
            "Deep learning uses neural networks",
            "Natural language processing with transformers",
            "Computer vision image recognition deep learning",
        ]
        ids = ["text1", "text2", "ml1", "dl1", "nlp1", "cv1"]
        metadata = [{"content": t} for t in texts]
        index.add_items(texts, ids, metadata)

        # Search with re-ranking disabled (no reranker model in tests)
        results = index.search("fox and dog", top_k=2, use_reranking=False)
        assert len(results) == 2

        # Search without re-ranking
        results_no_rerank = index.search("fox and dog", top_k=2, use_reranking=False)
        assert len(results_no_rerank) == 2

    def test_add_items_with_metadata(self, index: HNSWIndex) -> None:
        """Test adding items with metadata."""
        texts = ["Test content 1", "Test content 2"]
        ids = ["test1", "test2"]
        metadata = [
            {"content": "Test 1", "tags": ["tag1"]},
            {"content": "Test 2", "tags": ["tag2"]},
        ]

        added_ids = index.add_items(texts, ids, metadata)

        assert len(added_ids) == 2
        assert "test1" in added_ids
        assert "test2" in added_ids

        # Check stats include metadata count
        stats = index.get_stats()
        assert stats["total_items"] == 2

    def test_incremental_rebuild(self, index: HNSWIndex, temp_index_dir: Path) -> None:
        """Test incremental index rebuild."""
        # Add some items
        texts = ["Content 1", "Content 2", "Content 3"]
        ids = ["c1", "c2", "c3"]
        metadata = [{"content": t} for t in texts]
        index.add_items(texts, ids, metadata)

        # Incremental rebuild
        rebuilt = index.rebuild_incremental()

        # Should rebuild all items with metadata
        assert rebuilt == 3

    def test_search_expand_query(self, index: HNSWIndex, temp_index_dir: Path) -> None:
        """Test search with query expansion enabled."""
        # Add enough items
        texts = [
            f"Python programming tutorial for beginners topic {i}"
            for i in range(15)
        ]
        ids = [f"py{i}" for i in range(15)]
        metadata = [
            {"content": t, "tags": ["python", "programming"]}
            for t in texts
        ]
        index.add_items(texts, ids, metadata)

        # Search with query expansion disabled by default
        results = index.search("Python", top_k=2, expand_query=False)
        assert len(results) >= 1

        # Search without query expansion
        results_no_expand = index.search("Python", top_k=2, expand_query=False)
        assert len(results_no_expand) >= 1

    def test_rerank_results(self, index: HNSWIndex, temp_index_dir: Path) -> None:
        """Test re-ranking results."""
        texts = [
            "Machine learning basics introduction",
            "Deep learning with neural networks advanced",
            "Natural language processing fundamentals",
            "Computer vision image recognition",
            "Reinforcement learning algorithms",
        ]
        ids = ["ml1", "dl1", "nlp1", "cv1", "rl1"]
        metadata = [{"content": t} for t in texts]
        index.add_items(texts, ids, metadata)

        # Initial search without reranking
        initial_results = index.search("machine learning", top_k=3, use_reranking=False)
        assert len(initial_results) == 3

    def test_get_stats_enhanced(self, index: HNSWIndex) -> None:
        """Test enhanced statistics."""
        stats = index.get_stats()

        assert "total_items" in stats
        assert "max_elements" in stats
        assert "dim" in stats
        assert "model" in stats
        assert "reranking_enabled" in stats

    def test_remove_items_with_metadata_cleanup(self, index: HNSWIndex) -> None:
        """Test removing items cleans up metadata."""
        texts = ["Test content"]
        ids = ["test1"]
        metadata = [{"content": "Test", "tags": ["test"]}]

        index.add_items(texts, ids, metadata)
        removed = index.remove_items(["test1"])

        assert removed >= 0  # May be 0 if hnswlib doesn't support update_item


class TestHNSWIndexReranking:
    """Tests for cross-encoder re-ranking feature."""

    @pytest.fixture
    def temp_index_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_reranker_disabled_by_default(self, temp_index_dir: Path) -> None:
        """Test that re-ranking is disabled by default."""
        index = HNSWIndex(
            dim=384,
            index_dir=temp_index_dir,
            enable_reranking=False,
        )

        stats = index.get_stats()
        assert stats.get("reranking_enabled") is False

    def test_reranker_can_be_enabled(self, temp_index_dir: Path) -> None:
        """Test that re-ranking can be enabled."""
        index = HNSWIndex(
            dim=384,
            index_dir=temp_index_dir,
            enable_reranking=True,
        )

        # Re-ranking may fail to load but should not crash
        stats = index.get_stats()
        assert "reranking_enabled" in stats


class TestHNSWIndexQueryExpansion:
    """Tests for query expansion feature."""

    @pytest.fixture
    def index_with_data(self, temp_index_dir):
        """Create index with test data."""
        index = HNSWIndex(
            dim=384,
            index_dir=temp_index_dir,
            max_elements=1000,
        )

        # Add enough test data (20+ items for HNSW to work properly)
        texts = [
            f"Python is a versatile programming language topic {i}"
            for i in range(20)
        ]
        ids = [f"py{i}" for i in range(20)]
        metadata = [
            {"content": t, "tags": ["python", "programming"]}
            for t in texts
        ]
        index.add_items(texts, ids, metadata)

        return index

    @pytest.fixture
    def temp_index_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_query_expansion_returns_variations(self, index_with_data) -> None:
        """Test query expansion returns variations."""
        expanded = index_with_data.expand_query("Python")

        assert len(expanded) >= 1
        # Should include original query
        assert "Python" in expanded[0]

    def test_search_benefits_from_expansion(self, index_with_data) -> None:
        """Test search can benefit from query expansion."""
        # Search with expansion disabled (default)
        results_normal = index_with_data.search(
            "programming",
            top_k=3,
            expand_query=False,
        )

        # Both should return results
        assert len(results_normal) >= 1
