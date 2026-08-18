"""
FastEmbed Local Embedding Provider — Real local embeddings using FastEmbed & ONNX Runtime.

MODEL:
    sentence-transformers/all-MiniLM-L6-v2 (384-dimensional dense vectors)

FEATURES:
    1. Zero external API calls or paid credentials required.
    2. ONNX Runtime acceleration for fast CPU inference.
    3. Fully reproducible, normalized 384-dimensional floating-point embeddings.
    4. Conforms strictly to BaseEmbeddingProvider interface.
"""

from typing import Any
from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError

DEFAULT_FASTEMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FASTEMBED_DIMENSION = 384


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local embedding provider backed by FastEmbed and ONNX Runtime.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_FASTEMBED_MODEL,
        dimension: int = DEFAULT_FASTEMBED_DIMENSION,
        threads: int | None = None,
        **kwargs: Any,
    ):
        self._model_name = model_name or DEFAULT_FASTEMBED_MODEL
        self._dimension = dimension or DEFAULT_FASTEMBED_DIMENSION
        self._threads = threads
        self._kwargs = kwargs
        self._model: Any = None

    @property
    def provider_name(self) -> str:
        return "fastembed"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_model(self) -> Any:
        """Lazy-load the FastEmbed TextEmbedding model on first usage."""
        if self._model is None:
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(
                    model_name=self._model_name,
                    threads=self._threads,
                    **self._kwargs,
                )
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to initialize FastEmbed model '{self._model_name}': {str(e)}"
                ) from e
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """
        Convert a single text string into a 384-dimensional embedding vector.
        """
        if text is None:
            raise EmbeddingError("Cannot embed None text.")

        clean_text = text.strip() or " "
        try:
            model = self._get_model()
            embeddings = list(model.embed([clean_text]))
            if not embeddings:
                raise EmbeddingError("FastEmbed returned empty embedding list.")
            vec = [float(x) for x in embeddings[0]]
            return vec
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"FastEmbed text embedding generation failed: {str(e)}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Convert a batch of text strings into embedding vectors.
        """
        if not texts:
            return []

        cleaned = [t.strip() or " " for t in texts]
        try:
            model = self._get_model()
            embeddings = list(model.embed(cleaned))
            return [[float(x) for x in emb] for emb in embeddings]
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"FastEmbed batch embedding generation failed: {str(e)}") from e
