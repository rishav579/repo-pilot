"""
Retrieval Strategies — Concrete implementations of BaseRetriever.

INCLUDES:
1. KeywordRetriever: Wraps SQLite FTS5 index for BM25 keyword search.
2. SemanticRetriever: Uses embedding vectors & cosine similarity for concept search.
3. HybridRetriever: Pluggable composite retriever that combines multiple strategy results
   using Reciprocal Rank Fusion (RRF) algorithm.
"""

from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.indexing.sqlite_vector import SQLiteVectorStorage, cosine_similarity
from app.services.retrieval.base import BaseRetriever
from app.services.retrieval.deduplicator import deduplicate_search_results
from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.retrieval.models import CodeChunk, SearchResult
from app.services.retrieval.normalizer import normalize_query


class KeywordRetriever(BaseRetriever):
    """
    Keyword retrieval strategy backed by SQLite FTS5.
    """

    def __init__(self, fts_index: SQLiteFTSIndex):
        self.fts_index = fts_index

    def retrieve(self, query: str, repository_id: str | None = None, top_k: int = 10) -> list[SearchResult]:
        """
        Execute BM25 keyword search via FTS5 index.
        """
        return self.fts_index.search(query, repository_id=repository_id, top_k=top_k)


class SemanticRetriever(BaseRetriever):
    """
    Semantic retrieval strategy using embedding vectors & cosine similarity.
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        vector_storage: SQLiteVectorStorage,
        chunk_map: dict[str, CodeChunk] | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.vector_storage = vector_storage
        self.chunk_map = chunk_map or {}

    def set_chunk_map(self, chunk_map: dict[str, CodeChunk]):
        """Update active in-memory chunk map for metadata lookups."""
        self.chunk_map = chunk_map

    def retrieve(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """
        Execute vector embedding cosine similarity search.
        """
        normalized = normalize_query(query)
        if not normalized:
            return []

        try:
            query_vec = self.embedding_provider.embed_text(normalized)
        except EmbeddingError:
            return []

        all_vectors = self.vector_storage.get_all_embeddings(
            self.embedding_provider.model_name, self.embedding_provider.dimension
        )

        if not all_vectors:
            return []

        results: list[SearchResult] = []
        for cid, chunk_vec in all_vectors.items():
            if cid not in self.chunk_map:
                continue

            sim = cosine_similarity(query_vec, chunk_vec)
            chunk = self.chunk_map[cid]
            results.append(
                SearchResult(
                    chunk=chunk,
                    score=round(sim, 4),
                    score_type="cosine_similarity",
                    matched_keywords=[],
                )
            )

        return deduplicate_search_results(results)[:top_k]


class HybridRetriever(BaseRetriever):
    """
    Composite Hybrid Retriever.

    Combines multiple retrieval strategies (e.g. keyword + semantic) using
    Reciprocal Rank Fusion (RRF):
        RRF_Score(d) = SUM( 1 / (60 + rank_m(d)) ) for each strategy m
    """

    def __init__(self, retrievers: list[BaseRetriever] | None = None, rrf_k: int = 60):
        self.retrievers = retrievers or []
        self.rrf_k = rrf_k

    def add_retriever(self, retriever: BaseRetriever):
        """Add a retrieval strategy to the hybrid pipeline."""
        self.retrievers.append(retriever)

    def retrieve(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """
        Execute all registered retrievers and fuse results via Reciprocal Rank Fusion.
        """
        if not self.retrievers:
            return []

        # If only one retriever is registered (e.g., KeywordRetriever only), delegate directly
        if len(self.retrievers) == 1:
            raw = self.retrievers[0].retrieve(query, top_k=top_k)
            return deduplicate_search_results(raw)[:top_k]

        # Reciprocal Rank Fusion across multiple strategies
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, SearchResult] = {}

        for retriever in self.retrievers:
            results = retriever.retrieve(query, top_k=top_k * 2)
            for rank, res in enumerate(results, start=1):
                cid = res.chunk.chunk_id
                if cid not in chunk_map:
                    chunk_map[cid] = res
                else:
                    # Merge keywords if available
                    chunk_map[cid].matched_keywords = sorted(
                        list(set(chunk_map[cid].matched_keywords + res.matched_keywords))
                    )

                rrf_score = 1.0 / (self.rrf_k + rank)
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_score

        # Re-score search results using RRF score
        fused_results: list[SearchResult] = []
        for cid, rrf_score in rrf_scores.items():
            base_res = chunk_map[cid]
            fused_results.append(
                SearchResult(
                    chunk=base_res.chunk,
                    score=round(rrf_score, 6),
                    score_type="hybrid_rrf",
                    matched_keywords=base_res.matched_keywords,
                )
            )

        return deduplicate_search_results(fused_results)[:top_k]
