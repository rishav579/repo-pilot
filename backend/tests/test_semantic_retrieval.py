"""
Tests for Semantic Retrieval, Embedding Persistence, Cache, & Hybrid RRF (Phase 4.3).

Tests cover all required categories:
1. Embedding Abstraction (Mock, Batch, Dimensions)
2. Vector Persistence & Cache (SQLiteVectorStorage, mismatch handling)
3. Indexing Pipeline (Enabled/Disabled, Caching, Error resilience)
4. Semantic Retrieval (Cosine similarity, ranking, score_type)
5. Hybrid Retrieval (RRF fusion, Keyword-only, Semantic-only, Hybrid mode)
6. API & Configuration (Disabled/Enabled, Fallback)
"""

import pytest
from app.services.indexing.sqlite_vector import SQLiteVectorStorage, cosine_similarity
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.retrieval.embeddings.mock import MockEmbeddingProvider
from app.services.retrieval.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.services.retrieval.engine import RetrievalService
from app.services.retrieval.models import CodeChunk, SearchResult
from app.services.retrieval.strategies import HybridRetriever, KeywordRetriever, SemanticRetriever


class FailingEmbeddingProvider(BaseEmbeddingProvider):
    """Failing embedding provider to test network/API exception handling."""

    @property
    def provider_name(self) -> str:
        return "failing"

    @property
    def model_name(self) -> str:
        return "failing-model"

    @property
    def dimension(self) -> int:
        return 384

    def embed_text(self, text: str) -> list[float]:
        raise EmbeddingError("Simulated provider network error")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("Simulated provider network error")


class TestEmbeddingAbstraction:
    """Tests for embedding provider interface contract & mock provider."""

    def test_mock_embedding_provider_contract(self):
        provider = MockEmbeddingProvider(model_name="mock-384", dimension=384)
        assert provider.provider_name == "mock"
        assert provider.model_name == "mock-384"
        assert provider.dimension == 384

        vec = provider.embed_text("def health_check(): pass")
        assert len(vec) == 384
        assert isinstance(vec[0], float)

    def test_mock_embedding_deterministic_output(self):
        """Identical text must produce identical vector."""
        provider = MockEmbeddingProvider(dimension=384)
        v1 = provider.embed_text("def scan_repository(): pass")
        v2 = provider.embed_text("def scan_repository(): pass")
        assert v1 == v2

    def test_batch_embedding(self):
        provider = MockEmbeddingProvider(dimension=128)
        batch = provider.embed_batch(["text one", "text two", "text three"])
        assert len(batch) == 3
        assert all(len(v) == 128 for v in batch)


class TestVectorPersistenceAndCache:
    """Tests for SQLiteVectorStorage persistence and embedding cache."""

    @pytest.fixture
    def vector_storage(self):
        storage = SQLiteVectorStorage(db_path=":memory:")
        yield storage
        storage.close()

    def test_storing_and_loading_embeddings(self, vector_storage):
        vec = [0.1, 0.2, 0.3, 0.4]
        vector_storage.store_chunk_embedding("chunk1", "test-model", 4, vec)

        loaded = vector_storage.get_chunk_embedding("chunk1", "test-model", 4)
        assert loaded == vec

    def test_model_and_dimension_mismatch_handling(self, vector_storage):
        vec = [0.1, 0.2, 0.3, 0.4]
        vector_storage.store_chunk_embedding("chunk1", "test-model-a", 4, vec)

        # Querying with different model name should return None
        assert vector_storage.get_chunk_embedding("chunk1", "test-model-b", 4) is None

        # Querying with different dimension should return None
        assert vector_storage.get_chunk_embedding("chunk1", "test-model-a", 8) is None

    def test_embedding_caching(self, vector_storage):
        vec = [0.5, 0.5]
        text = "def add(a, b): return a + b"

        assert vector_storage.get_cached_embedding(text, "model-x") is None
        vector_storage.cache_embedding(text, "model-x", vec)

        cached = vector_storage.get_cached_embedding(text, "model-x")
        assert cached == vec


class TestIndexingWithEmbeddings:
    """Tests for indexing pipeline with semantic embeddings enabled/disabled."""

    def test_indexing_with_embeddings_disabled(self, sample_repo):
        config = RetrievalConfig(semantic_enabled=False)
        service = RetrievalService(db_path=":memory:", config=config)

        num_chunks = service.index_repository(str(sample_repo))
        assert num_chunks > 0

        # Vector storage should be empty when semantic indexing is disabled
        vectors = service.vector_storage.get_all_embeddings(
            service.embedding_provider.model_name,
            service.embedding_provider.dimension,
        )
        assert len(vectors) == 0

        service.close()

    def test_indexing_with_embeddings_enabled(self, sample_repo):
        config = RetrievalConfig(semantic_enabled=True, provider_type="mock")
        service = RetrievalService(db_path=":memory:", config=config)

        num_chunks = service.index_repository(str(sample_repo))
        assert num_chunks > 0

        # Vector storage should contain generated embeddings
        vectors = service.vector_storage.get_all_embeddings(
            service.embedding_provider.model_name,
            service.embedding_provider.dimension,
        )
        assert len(vectors) > 0

        service.close()

    def test_embedding_failure_does_not_destroy_keyword_indexing(self, sample_repo):
        """Failing embedding provider should not crash indexing or prevent keyword search."""
        failing_provider = FailingEmbeddingProvider()
        config = RetrievalConfig(semantic_enabled=True)
        service = RetrievalService(
            db_path=":memory:",
            config=config,
            embedding_provider=failing_provider,
        )

        num_chunks = service.index_repository(str(sample_repo))
        assert num_chunks > 0

        # Keyword search must still work perfectly
        response = service.search("add", mode="keyword")
        assert response.total_matches > 0

        service.close()


class TestSemanticRetrieval:
    """Tests for SemanticRetriever strategy."""

    def test_semantic_search_ranking_and_score_type(self):
        provider = MockEmbeddingProvider(dimension=128)
        storage = SQLiteVectorStorage(db_path=":memory:")

        c1 = CodeChunk(
            chunk_id="file1.py:L1-L5:add",
            relative_path="file1.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def add(a, b): return a + b",
            symbol_name="add",
        )
        c2 = CodeChunk(
            chunk_id="file2.py:L1-L5:sub",
            relative_path="file2.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def subtract(a, b): return a - b",
            symbol_name="subtract",
        )

        # Store vectors
        v1 = provider.embed_text(c1.code_content)
        v2 = provider.embed_text(c2.code_content)
        storage.store_chunk_embedding(c1.chunk_id, provider.model_name, 128, v1)
        storage.store_chunk_embedding(c2.chunk_id, provider.model_name, 128, v2)

        retriever = SemanticRetriever(
            embedding_provider=provider,
            vector_storage=storage,
            chunk_map={c1.chunk_id: c1, c2.chunk_id: c2},
        )

        results = retriever.retrieve("def add(a, b): return a + b", top_k=10)
        assert len(results) > 0
        top = results[0]
        assert top.chunk.symbol_name == "add"
        assert top.score_type == "cosine_similarity"
        assert top.score > 0.9

        storage.close()


class TestHybridRetrievalIntegration:
    """Tests for HybridRetriever combining keyword + semantic via RRF."""

    def test_hybrid_mode_rrf_fusion(self, sample_repo):
        config = RetrievalConfig(semantic_enabled=True, provider_type="mock")
        service = RetrievalService(db_path=":memory:", config=config)
        service.index_repository(str(sample_repo))

        response = service.search("add", mode="hybrid")
        assert response.total_matches > 0
        top = response.results[0]
        assert top.score_type == "hybrid_rrf"
        assert top.score > 0

        service.close()

    def test_keyword_only_vs_semantic_only_modes(self, sample_repo):
        config = RetrievalConfig(semantic_enabled=True, provider_type="mock")
        service = RetrievalService(db_path=":memory:", config=config)
        service.index_repository(str(sample_repo))

        kw_resp = service.search("add", mode="keyword")
        sem_resp = service.search("add", mode="semantic")

        assert kw_resp.total_matches > 0
        assert sem_resp.total_matches > 0

        assert kw_resp.results[0].score_type == "bm25"
        assert sem_resp.results[0].score_type == "cosine_similarity"

        service.close()
