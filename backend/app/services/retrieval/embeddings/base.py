"""
Base Embedding Provider Interface.

Defines a clean contract (`embed_text`, `embed_batch`, `dimension`, `provider_name`, `model_name`)
for any text embedding provider (mock, OpenAI, Ollama, local models).
"""

from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when an embedding provider fails to generate vectors."""

    pass


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface for text embedding providers.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of embedding provider (e.g. "mock", "openai")."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of embedding model (e.g. "text-embedding-3-small", "mock-384d")."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension size (e.g. 384, 1536)."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """
        Convert a single text string into a normalized floating-point embedding vector.

        Args:
            text: Source text to embed.

        Returns:
            List of floats of size `dimension`.
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Convert a batch of text strings into embedding vectors.

        Args:
            texts: List of source text strings.

        Returns:
            List of embedding vectors.
        """
        pass
