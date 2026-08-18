"""
Unit & Integration Tests for FastEmbed Real Local Embedding Provider.
"""

import math
import pytest

from app.services.indexing.sqlite_vector import cosine_similarity
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.retrieval.embeddings.fastembed import (
    DEFAULT_FASTEMBED_DIMENSION,
    DEFAULT_FASTEMBED_MODEL,
    FastEmbedEmbeddingProvider,
)
from app.services.retrieval.engine import RetrievalService


class TestFastEmbedProviderContract:
    """Verify FastEmbedEmbeddingProvider conforms to BaseEmbeddingProvider interface."""

    def test_provider_properties(self):
        provider = FastEmbedEmbeddingProvider()
        assert isinstance(provider, BaseEmbeddingProvider)
        assert provider.provider_name == "fastembed"
        assert provider.model_name == DEFAULT_FASTEMBED_MODEL
        assert provider.dimension == DEFAULT_FASTEMBED_DIMENSION

    def test_embed_single_text(self):
        provider = FastEmbedEmbeddingProvider()
        text = "def scan_repository(path: str) -> ScanResult: pass"
        vec = provider.embed_text(text)

        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(x, float) for x in vec)

        # Check normalization (L2 norm is approximately 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 0.01

    def test_embed_batch_texts(self):
        provider = FastEmbedEmbeddingProvider()
        texts = [
            "FastAPI endpoint handler",
            "SQLite FTS5 virtual table index",
            "Reciprocal rank fusion algorithm",
        ]
        vectors = provider.embed_batch(texts)

        assert isinstance(vectors, list)
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 384
            assert all(isinstance(x, float) for x in vec)

    def test_embed_empty_and_whitespace(self):
        provider = FastEmbedEmbeddingProvider()
        vec1 = provider.embed_text("")
        vec2 = provider.embed_text("   ")
        assert len(vec1) == 384
        assert len(vec2) == 384

    def test_embed_none_raises_error(self):
        provider = FastEmbedEmbeddingProvider()
        with pytest.raises(EmbeddingError):
            provider.embed_text(None)  # type: ignore

    def test_semantic_similarity_ranking(self):
        """
        Verify real semantic relationships:
        'FastAPI HTTP route handler' should be much more similar to 'Web API endpoint in main.py'
        than to 'Quantum mechanics wavefunction eigenvalue'.
        """
        provider = FastEmbedEmbeddingProvider()
        query_vec = provider.embed_text("FastAPI HTTP route handler")
        related_vec = provider.embed_text("Web API endpoint in main.py")
        unrelated_vec = provider.embed_text("Quantum mechanics wavefunction eigenvalue collapse")

        sim_related = cosine_similarity(query_vec, related_vec)
        sim_unrelated = cosine_similarity(query_vec, unrelated_vec)

        assert sim_related > sim_unrelated
        assert sim_related > 0.25  # Meaningful positive cosine similarity


class TestFastEmbedRetrievalIntegration:
    """Integration of FastEmbedEmbeddingProvider with RetrievalService."""

    @pytest.fixture
    def retrieval_service(self):
        config = RetrievalConfig(
            semantic_enabled=True,
            provider_type="fastembed",
            model_name=DEFAULT_FASTEMBED_MODEL,
            dimension=DEFAULT_FASTEMBED_DIMENSION,
        )
        service = RetrievalService(db_path=":memory:", config=config)
        yield service
        service.close()

    def test_fastembed_search_integration(self, retrieval_service, tmp_path):
        # Create a sample Python repo
        test_file = tmp_path / "routes.py"
        test_file.write_text(
            'def get_health_status():\n    """Health check route."""\n    return {"status": "ok"}\n',
            encoding="utf-8",
        )

        chunk_count = retrieval_service.index_repository(str(tmp_path), enable_semantic=True)
        assert chunk_count > 0

        # Execute semantic search
        res_semantic = retrieval_service.search("system health status probe", mode="semantic", top_k=5)
        assert len(res_semantic.results) > 0
        assert res_semantic.results[0].score_type == "reranked"

        # Execute hybrid search
        res_hybrid = retrieval_service.search("health check", mode="hybrid", top_k=5)
        assert len(res_hybrid.results) > 0
        assert res_hybrid.results[0].score_type == "reranked"
