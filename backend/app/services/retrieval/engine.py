"""
Retrieval Service & Engine — Orchestrates indexing, embeddings, query normalization, strategy execution, and hybrid search.

SUPPORTED RETRIEVAL MODES:
- "keyword": FTS5 BM25 keyword search only.
- "semantic": Embedding vector cosine similarity search only.
- "hybrid": Reciprocal Rank Fusion (RRF) combining keyword + semantic results.
"""

from pathlib import Path

from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.indexing.sqlite_vector import SQLiteVectorStorage
from app.services.parsing.parser import parse_repository
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.deduplicator import deduplicate_search_results
from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.retrieval.embeddings.fastembed import FastEmbedEmbeddingProvider
from app.services.retrieval.embeddings.mock import MockEmbeddingProvider
from app.services.retrieval.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.services.retrieval.models import CodeChunk, SearchResponse, SearchResult
from app.services.retrieval.normalizer import normalize_query
from app.services.retrieval.reranker import CodeAwareReranker, CodeAwareRerankerConfig
from app.services.retrieval.strategies import HybridRetriever, KeywordRetriever, SemanticRetriever

DEFAULT_TOP_K = 10
MAX_TOP_K = 100


class RetrievalService:
    """
    Service layer for code indexing, embedding persistence, and multi-strategy retrieval.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        config: RetrievalConfig | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        fts_index: SQLiteFTSIndex | None = None,
        vector_storage: SQLiteVectorStorage | None = None,
        reranker_config: CodeAwareRerankerConfig | None = None,
    ):
        self.config = config or RetrievalConfig.from_env()
        self.db_path = db_path

        # Database storage instances
        self.fts_index = fts_index or SQLiteFTSIndex(db_path=db_path)
        self.vector_storage = vector_storage or SQLiteVectorStorage(db_path=db_path)

        # In-memory chunk mapping
        self.chunk_map: dict[str, CodeChunk] = {}

        # Embedding Provider Setup
        if embedding_provider is not None:
            self.embedding_provider = embedding_provider
        elif self.config.provider_type == "fastembed":
            self.embedding_provider = FastEmbedEmbeddingProvider(
                model_name=self.config.model_name,
                dimension=self.config.dimension,
            )
        elif self.config.provider_type == "openai":
            self.embedding_provider = OpenAICompatibleEmbeddingProvider(
                api_key=self.config.api_key,
                model_name=self.config.model_name,
                dimension=self.config.dimension,
                api_base=self.config.api_base,
            )
        else:
            self.embedding_provider = MockEmbeddingProvider(
                model_name=self.config.model_name,
                dimension=self.config.dimension,
            )

        # Retrieval Strategies
        self.keyword_retriever = KeywordRetriever(self.fts_index)
        self.semantic_retriever = SemanticRetriever(
            embedding_provider=self.embedding_provider,
            vector_storage=self.vector_storage,
            chunk_map=self.chunk_map,
            fts_index=self.fts_index,
        )
        self.hybrid_retriever = HybridRetriever(
            [self.keyword_retriever, self.semantic_retriever]
        )

        # Code-Aware Reranker (Phase 7)
        self.reranker_config = reranker_config or CodeAwareRerankerConfig()
        self.reranker = CodeAwareReranker(config=self.reranker_config)

    def index_repository(
        self, repo_path: str, enable_semantic: bool | None = None
    ) -> int:
        """
        Parse and index an entire local repository.

        Keyword indexing ALWAYS runs.
        Semantic embedding generation runs if enabled (or if config.semantic_enabled is True).
        """
        should_embed = (
            enable_semantic if enable_semantic is not None else self.config.semantic_enabled
        )

        parse_res = parse_repository(repo_path)
        repo_root = Path(parse_res.repository_path)

        all_chunks: list[CodeChunk] = []
        for parsed_file in parse_res.files:
            file_chunks = chunk_parsed_file(parsed_file, repo_root)
            all_chunks.extend(file_chunks)

        # Update in-memory chunk map
        self.chunk_map = {c.chunk_id: c for c in all_chunks}
        self.semantic_retriever.set_chunk_map(self.chunk_map)

        # 1. Keyword FTS Indexing (Always executes)
        self.fts_index.clear()
        self.fts_index.index_chunks(all_chunks)

        # 2. Semantic Embedding Generation (Executes if enabled)
        if should_embed:
            self._generate_and_store_embeddings(all_chunks)

        return len(all_chunks)

    def _generate_and_store_embeddings(self, chunks: list[CodeChunk]):
        """
        Generate and persist embeddings for chunks, using embedding cache to avoid re-embedding.
        Embedding errors are caught safely without corrupting keyword index.
        """
        for chunk in chunks:
            text = chunk.code_content
            mname = self.embedding_provider.model_name
            dim = self.embedding_provider.dimension

            # Check cache first
            cached_vec = self.vector_storage.get_cached_embedding(text, mname)
            if cached_vec and len(cached_vec) == dim:
                self.vector_storage.store_chunk_embedding(
                    chunk.chunk_id, mname, dim, cached_vec
                )
                continue

            # Generate new embedding
            try:
                vec = self.embedding_provider.embed_text(text)
                self.vector_storage.cache_embedding(text, mname, vec)
                self.vector_storage.store_chunk_embedding(
                    chunk.chunk_id, mname, dim, vec
                )
            except EmbeddingError:
                # Catch embedding provider failures safely — keyword index remains intact
                continue
            except Exception:
                continue

    def search(
        self,
        raw_query: str,
        repository_id: str | None = None,
        mode: str = "auto",
        top_k: int = DEFAULT_TOP_K,
    ) -> SearchResponse:
        """
        Execute search query across keyword, semantic, or hybrid strategies.

        Args:
            raw_query: Raw search query string.
            repository_id: Optional repository ID filter.
            mode: "auto" | "keyword" | "semantic" | "hybrid"
            top_k: Maximum results to return.
        """
        normalized = normalize_query(raw_query)

        # Enforce top_k boundaries
        if top_k < 1:
            effective_top_k = DEFAULT_TOP_K
        elif top_k > MAX_TOP_K:
            effective_top_k = MAX_TOP_K
        else:
            effective_top_k = top_k

        if not normalized:
            return SearchResponse(
                query=raw_query or "",
                total_matches=0,
                results=[],
            )

        # Determine candidate pool size for reranking
        # Fetch more candidates than final top_k so the reranker has room to promote
        candidate_k = max(
            effective_top_k * self.reranker_config.candidate_pool_multiplier,
            self.reranker_config.min_candidate_pool,
        )

        # Determine strategy to execute
        mode_lower = mode.lower()
        if mode_lower == "keyword":
            raw_results = self.keyword_retriever.retrieve(
                normalized, repository_id=repository_id, top_k=candidate_k
            )
        elif mode_lower == "semantic":
            raw_results = self.semantic_retriever.retrieve(
                normalized, repository_id=repository_id, top_k=candidate_k
            )
        elif mode_lower == "hybrid":
            raw_results = self.hybrid_retriever.retrieve(
                normalized, repository_id=repository_id, top_k=candidate_k
            )
        else:
            # "auto" mode: use hybrid if semantic embeddings exist, else keyword
            if self.config.semantic_enabled:
                raw_results = self.hybrid_retriever.retrieve(
                    normalized, repository_id=repository_id, top_k=candidate_k
                )
            else:
                raw_results = self.keyword_retriever.retrieve(
                    normalized, repository_id=repository_id, top_k=candidate_k
                )

        # If repository_id specified, ensure filter
        if repository_id:
            raw_results = [
                r for r in raw_results
                if getattr(r.chunk, "repository_id", "default") in (repository_id, "default")
            ]

        deduped_results = deduplicate_search_results(raw_results)

        # Apply code-aware reranking (Phase 7)
        reranked_results = self.reranker.rerank(
            normalized, deduped_results, top_k=effective_top_k
        )

        return SearchResponse(
            query=normalized,
            total_matches=len(reranked_results),
            results=reranked_results,
        )

    def close(self):
        """Close storage resources."""
        self.fts_index.close()
        self.vector_storage.close()


# Backward-compatible alias for existing imports
KeywordSearchEngine = RetrievalService
