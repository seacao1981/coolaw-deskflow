"""HNSW vector index for approximate nearest neighbor search.

Provides fast approximate nearest neighbor search with configurable accuracy.

Enhancements in v2.0:
- Re-ranking with cross-encoder
- Multi-vector averaging
- Query expansion
- Incremental rebuild
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class HNSWIndex:
    """HNSW (Hierarchical Navigable Small World) index for vector search.

    Provides fast approximate nearest neighbor search with configurable accuracy.

    Enhancements:
    - Multi-vector averaging for better representation
    - Query expansion for improved recall
    - Re-ranking support for better precision
    - Incremental index rebuild
    """

    def __init__(
        self,
        dim: int = 384,  # all-MiniLM-L6-v2 embedding dimension
        model_name: str = "all-MiniLM-L6-v2",
        index_dir: str | None = None,
        max_elements: int = 100000,
        ef_construction: int = 200,
        M: int = 32,  # Increased for better search stability
        auto_save: bool = True,
        enable_reranking: bool = False,
        rerank_model: str = "ms-marco-MiniLM-L-6-v2",
    ):
        """Initialize HNSW index.

        Args:
            dim: Embedding dimension
            model_name: Sentence transformer model name
            index_dir: Directory to save/load index
            max_elements: Maximum number of elements
            ef_construction: Construction time accuracy/speed tradeoff
            M: Max number of connections per layer
            auto_save: Whether to auto-save index on add/remove operations
            enable_reranking: Whether to enable cross-encoder re-ranking
            rerank_model: Cross-encoder model for re-ranking
        """
        self.dim = dim
        self.model_name = model_name
        self.index_dir = Path(index_dir) if index_dir else Path.cwd() / "data" / "hnsw"
        self.max_elements = max_elements
        self._auto_save = auto_save
        self._enable_reranking = enable_reranking

        # Load embedding model
        self._model = SentenceTransformer(model_name)

        # Load re-ranker if enabled
        self._reranker = None
        if enable_reranking:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(rerank_model)
                logger.info("reranker_loaded", model=rerank_model)
            except Exception as e:
                logger.warning("reranker_load_failed", error=str(e))
                self._enable_reranking = False

        # Initialize or load HNSW index
        self._index = self._load_or_create_index(ef_construction, M)

        # ID mapping for metadata lookup
        self._id_to_label: dict[int, str] = {}
        self._label_to_id: dict[str, int] = {}

        # Metadata storage for re-ranking
        self._metadata: dict[str, dict[str, Any]] = {}

        logger.info("hnsw_index_initialized", dim=dim, model=model_name, auto_save=auto_save)

    def _load_or_create_index(self, ef_construction: int, M: int) -> hnswlib.Index:
        """Load existing index or create new one."""
        index_path = self.index_dir / "hnsw_index.bin"
        metadata_path = self.index_dir / "hnsw_metadata.json"

        if index_path.exists() and metadata_path.exists():
            try:
                return self._load_index(index_path, metadata_path)
            except Exception as e:
                logger.warning("hnsw_load_failed", error=str(e), reason="creating_new_index")

        # Create new index
        index = hnswlib.Index(dim=self.dim, space="cosine")
        index.init_index(
            max_elements=self.max_elements,
            ef_construction=ef_construction,
            M=M,
        )
        index.set_ef(max(50, M * 2))  # Search accuracy/speed tradeoff

        logger.info("hnsw_index_created", max_elements=self.max_elements)
        return index

    def _load_index(self, index_path: Path, metadata_path: Path) -> hnswlib.Index:
        """Load index from disk."""
        index = hnswlib.Index(dim=self.dim, space="cosine")
        index.load_index(str(index_path))

        with open(metadata_path) as f:
            metadata = json.load(f)
            self._id_to_label = {int(k): v for k, v in metadata.get("id_to_label", {}).items()}
            self._label_to_id = {k: int(v) for k, v in metadata.get("label_to_id", {}).items()}
            self._metadata = metadata.get("item_metadata", {})

        logger.info("hnsw_index_loaded", elements=len(self._id_to_label))
        return index

    def save_index(self) -> None:
        """Save index to disk."""
        self.index_dir.mkdir(parents=True, exist_ok=True)

        index_path = self.index_dir / "hnsw_index.bin"
        metadata_path = self.index_dir / "hnsw_metadata.json"

        self._index.save_index(str(index_path))

        metadata = {
            "id_to_label": self._id_to_label,
            "label_to_id": self._label_to_id,
            "item_metadata": self._metadata,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("hnsw_index_saved", elements=len(self._id_to_label))

    def embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        if not texts:
            return np.array([]).reshape(0, self.dim)
        return self._model.encode(texts, convert_to_numpy=True)

    def embed_multi_vector(self, texts: list[str]) -> np.ndarray:
        """Generate multi-vector averaged embedding.

        Creates embeddings for each text and averages them for a more robust representation.

        Args:
            texts: List of texts to embed

        Returns:
            Averaged embedding vector
        """
        if not texts:
            return np.zeros(self.dim)

        embeddings = self.embed(texts)
        if len(embeddings) == 0:
            return np.zeros(self.dim)

        # Average embeddings
        avg_embedding = np.mean(embeddings, axis=0)
        return avg_embedding

    def expand_query(self, query: str, top_k: int = 3) -> list[str]:
        """Expand query with related terms for better recall.

        Uses the existing index to find related terms and expands the query.

        Args:
            query: Original query
            top_k: Number of related terms to add

        Returns:
            Expanded query with related terms
        """
        if len(self._label_to_id) == 0:
            return [query]

        # Get initial results - use higher ef for better recall
        results = self.search(query, top_k=top_k, ef_search=max(100, top_k * 10))

        if not results:
            return [query]

        # Extract key terms from results
        expanded = [query]
        for item_id, _ in results[:2]:  # Use top 2 results
            if item_id in self._metadata:
                tags = self._metadata[item_id].get("tags", [])
                expanded.extend(tags[:2])  # Add top 2 tags

        return expanded

    def add_items(
        self,
        texts: list[str],
        ids: list[str] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Add items to the index.

        Args:
            texts: List of texts to embed and add
            ids: Optional list of IDs (auto-generated if not provided)
            metadata: Optional list of metadata dicts for each item

        Returns:
            List of IDs for the added items
        """
        if not texts:
            return []

        # Generate IDs if not provided
        if ids is None:
            start_id = len(self._label_to_id)
            ids = [f"item_{start_id + i}" for i in range(len(texts))]

        # Generate embeddings
        embeddings = self.embed(texts)

        # Add to index
        current_size = self._index.get_current_count()
        new_ids = []

        for i, (item_id, emb) in enumerate(zip(ids, embeddings)):
            if item_id in self._label_to_id:
                # Update existing item - hnswlib doesn't support update_item
                # Instead, we mark it as removed and add a new one
                idx = self._label_to_id[item_id]
                # Mark as removed by setting to zero vector
                zero_emb = np.zeros(self.dim)
                self._index.update_item(idx, emb) if hasattr(self._index, 'update_item') else None
                new_ids.append(item_id)
            else:
                # Add new item
                idx = current_size + len(new_ids)
                if idx >= self.max_elements:
                    logger.warning("hnsw_index_full", idx=idx, max=self.max_elements)
                    continue

                self._index.add_items(emb.reshape(1, -1), [idx])
                self._id_to_label[idx] = item_id
                self._label_to_id[item_id] = idx
                new_ids.append(item_id)

            # Store metadata
            if metadata and i < len(metadata):
                self._metadata[item_id] = metadata[i]
            elif metadata and len(metadata) == 1:
                self._metadata[item_id] = metadata[0]

        logger.info("hnsw_items_added", count=len(new_ids), total=len(self._label_to_id))

        # Auto-save if enabled
        if self._auto_save and new_ids:
            self.save_index()

        return new_ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        ef_search: int = 50,
        use_reranking: bool = True,
        expand_query: bool = False,  # Disabled by default to avoid recursion
    ) -> list[tuple[str, float]]:
        """Search for similar items.

        Args:
            query: Search query text
            top_k: Number of results to return
            ef_search: Search accuracy/speed tradeoff
            use_reranking: Whether to use cross-encoder re-ranking
            expand_query: Whether to expand query with related terms

        Returns:
            List of (id, similarity_score) tuples
        """
        if len(self._label_to_id) == 0:
            return []

        # Set search accuracy - ensure ef is large enough
        ef_search = max(ef_search, top_k * 2)
        self._index.set_ef(ef_search)

        # Generate query embedding
        query_emb = self.embed([query])[0]

        # Search - get more candidates for re-ranking
        rerank_candidates = max(top_k * 3, 10)  # Minimum 10 candidates
        labels, distances = self._index.knn_query(query_emb.reshape(1, -1), k=rerank_candidates)

        # Format results
        results = []
        for idx, dist in zip(labels[0], distances[0]):
            if idx in self._id_to_label:
                item_id = self._id_to_label[idx]
                # Convert distance to similarity (cosine distance -> similarity)
                similarity = 1.0 - dist
                results.append((item_id, similarity))

        # Re-rank with cross-encoder
        if use_reranking and self._reranker and results:
            results = self._rerank_results(query, results, top_k)
        else:
            results = results[:top_k]

        logger.debug("hnsw_search", query=query[:50], results=len(results))
        return results

    def _rerank_results(
        self,
        query: str,
        results: list[tuple[str, float]],
        top_k: int,
    ) -> list[tuple[str, float]]:
        """Re-rank results using cross-encoder.

        Args:
            query: Original query
            results: Initial search results
            top_k: Number of results to return

        Returns:
            Re-ranked results
        """
        if not self._reranker:
            return results[:top_k]

        # Get texts for re-ranking
        pairs = []
        ids = []
        for item_id, _ in results:
            if item_id in self._metadata:
                content = self._metadata[item_id].get("content", "")
                pairs.append([query, content])
                ids.append(item_id)

        if not pairs:
            return results[:top_k]

        # Get cross-encoder scores
        try:
            scores = self._reranker.predict(pairs)

            # Combine with original scores
            reranked = []
            for (item_id, orig_score), new_score in zip(results, scores):
                # Weighted combination
                combined_score = 0.3 * orig_score + 0.7 * float(new_score)
                reranked.append((item_id, combined_score))

            # Sort by combined score
            reranked.sort(key=lambda x: x[1], reverse=True)
            return reranked[:top_k]

        except Exception as e:
            logger.warning("reranking_failed", error=str(e))
            return results[:top_k]

    def remove_items(self, ids: list[str]) -> int:
        """Remove items from the index.

        Note: HNSW doesn't support efficient deletion. We mark items as removed.

        Args:
            ids: List of IDs to remove

        Returns:
            Number of items actually removed
        """
        removed = 0
        for item_id in ids:
            if item_id in self._label_to_id:
                idx = self._label_to_id[item_id]
                # Mark as removed by setting to zero vector
                # Note: hnswlib may not have update_item, so we just remove from mapping
                if hasattr(self._index, 'update_item'):
                    zero_emb = np.zeros(self.dim)
                    try:
                        self._index.update_item(idx, zero_emb)
                    except (AttributeError, NotImplementedError):
                        pass
                del self._id_to_label[idx]
                del self._label_to_id[item_id]
                self._metadata.pop(item_id, None)
                removed += 1

        logger.info("hnsw_items_removed", count=removed, remaining=len(self._label_to_id))

        # Auto-save if enabled
        if self._auto_save and removed > 0:
            self.save_index()

        return removed

    def rebuild_incremental(self) -> int:
        """Incrementally rebuild the index from metadata.

        Useful for recovering from index corruption or migrating to new parameters.

        Returns:
            Number of items rebuilt
        """
        if not self._metadata:
            return 0

        # Create new index
        new_index = hnswlib.Index(dim=self.dim, space="cosine")
        new_index.init_index(
            max_elements=self.max_elements,
            ef_construction=200,
            M=self._index.M if hasattr(self._index, 'M') else 32,
        )
        new_index.set_ef(50)

        # Re-add all items
        rebuilt = 0
        for item_id, meta in self._metadata.items():
            content = meta.get("content", "")
            if content:
                emb = self.embed([content])[0]
                idx = len(self._label_to_id)
                new_index.add_items(emb.reshape(1, -1), [idx])
                rebuilt += 1

        self._index = new_index
        logger.info("hnsw_index_rebuilt_incremental", count=rebuilt)
        return rebuilt

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_items": len(self._label_to_id),
            "max_elements": self.max_elements,
            "dim": self.dim,
            "model": self.model_name,
            "reranking_enabled": self._enable_reranking,
            "index_size_mb": round(
                os.path.getsize(self.index_dir / "hnsw_index.bin") / 1024 / 1024, 2
            ) if (self.index_dir / "hnsw_index.bin").exists() else 0,
        }
