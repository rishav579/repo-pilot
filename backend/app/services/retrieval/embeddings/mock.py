"""
Mock Embedding Provider — Deterministic, offline embedding generator for testing & dev.

HOW IT WORKS:
    Uses SHA-256 hash hashing of text + dimension index to generate normalized
    floating-point vectors. The generated vector is 100% deterministic:
    identical text + model_name always produces the exact same vector.
"""

import hashlib
import math

from app.services.retrieval.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock embedding provider.
    """

    def __init__(self, model_name: str = "mock-384d", dimension: int = 384):
        self._model_name = model_name
        self._dimension = dimension

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> list[float]:
        """Generate a unit-normalized vector deterministically from text content."""
        if not text:
            return [0.0] * self._dimension

        vec: list[float] = []
        for i in range(self._dimension):
            # Combine text, index, and model_name for hash seed
            seed = f"{self._model_name}:{i}:{text}"
            digest = hashlib.sha256(seed.encode("utf-8")).digest()
            # Convert 4 bytes into float in range [-1.0, 1.0]
            val = (int.from_bytes(digest[:4], "big") / (2**32 - 1)) * 2.0 - 1.0
            vec.append(val)

        # Normalize vector to unit length for cosine similarity
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self._generate_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""
        return [self._generate_vector(t) for t in texts]
