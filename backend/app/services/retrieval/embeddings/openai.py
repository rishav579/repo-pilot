"""
OpenAI-Compatible Embedding Provider — Calls external HTTP embedding APIs.

Supports OpenAI, Ollama, LocalAI, vLLM, or LMStudio embedding endpoints via httpx.
"""

import httpx

from app.services.retrieval.embeddings.base import BaseEmbeddingProvider, EmbeddingError


class OpenAICompatibleEmbeddingProvider(BaseEmbeddingProvider):
    """
    HTTP client provider for OpenAI-compatible embedding APIs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_base: str = "https://api.openai.com/v1",
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def embed_text(self, text: str) -> list[float]:
        """Embed single text string."""
        results = self.embed_batch([text])
        if not results:
            raise EmbeddingError("Empty response from embedding API")
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings via HTTP POST request."""
        if not texts:
            return []

        url = f"{self.api_base}/embeddings"
        payload = {
            "model": self._model_name,
            "input": texts,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=self._headers())
                if resp.status_code != 200:
                    raise EmbeddingError(
                        f"Embedding API error HTTP {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                data_items = data.get("data", [])
                # Ensure ordered by index
                data_items.sort(key=lambda item: item.get("index", 0))

                vectors = [item["embedding"] for item in data_items]
                return vectors
        except httpx.HTTPError as e:
            raise EmbeddingError(f"HTTP connection error to embedding API: {str(e)}")
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")
