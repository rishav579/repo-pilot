"""
Embedding Providers package.
"""

from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.retrieval.embeddings.fastembed import (
    DEFAULT_FASTEMBED_DIMENSION,
    DEFAULT_FASTEMBED_MODEL,
    FastEmbedEmbeddingProvider,
)
from app.services.retrieval.embeddings.mock import MockEmbeddingProvider
from app.services.retrieval.embeddings.openai import OpenAICompatibleEmbeddingProvider

__all__ = [
    "BaseEmbeddingProvider",
    "EmbeddingError",
    "FastEmbedEmbeddingProvider",
    "MockEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "DEFAULT_FASTEMBED_MODEL",
    "DEFAULT_FASTEMBED_DIMENSION",
]
