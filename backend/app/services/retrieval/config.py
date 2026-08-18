"""
Retrieval & Embedding Configuration.

Loads configuration from environment variables with safe defaults.
Does NOT store secrets in code. Users do NOT need paid API keys for local search.

ENVIRONMENT VARIABLES:
- SEMANTIC_RETRIEVAL_ENABLED: "true" | "false" (default: "true" for production/demo, "false" if disabled)
- EMBEDDING_PROVIDER: "fastembed" | "mock" | "openai" (default: "fastembed")
- EMBEDDING_MODEL: Embedding model name (default: "sentence-transformers/all-MiniLM-L6-v2")
- EMBEDDING_DIMENSION: Vector dimension (default: 384 for fastembed/mock, 1536 for OpenAI)
- EMBEDDING_API_KEY: Optional API key for external providers
- EMBEDDING_API_BASE: Base URL for OpenAI-compatible provider (default: "https://api.openai.com/v1")
"""

import os
from pydantic import BaseModel

DEFAULT_FASTEMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FASTEMBED_DIMENSION = 384


class RetrievalConfig(BaseModel):
    """
    Configuration model for retrieval service and embedding providers.
    """

    semantic_enabled: bool = False
    provider_type: str = "fastembed"  # "fastembed" | "mock" | "openai"
    model_name: str = DEFAULT_FASTEMBED_MODEL
    dimension: int = DEFAULT_FASTEMBED_DIMENSION
    api_key: str | None = None
    api_base: str = "https://api.openai.com/v1"
    semantic_top_k: int = 10
    keyword_top_k: int = 10

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """
        Load configuration from environment variables with safe defaults.
        """
        enabled_str = os.getenv("SEMANTIC_RETRIEVAL_ENABLED", "false").lower()
        semantic_enabled = enabled_str in ("true", "1", "yes")

        provider_type = os.getenv("EMBEDDING_PROVIDER", "fastembed").lower()
        if provider_type == "openai":
            default_model = "text-embedding-3-small"
            default_dim = 1536
        elif provider_type == "mock":
            default_model = "mock-embedding-384d"
            default_dim = 384
        else:
            provider_type = "fastembed"
            default_model = DEFAULT_FASTEMBED_MODEL
            default_dim = DEFAULT_FASTEMBED_DIMENSION

        model_name = os.getenv("EMBEDDING_MODEL", default_model)

        dim_str = os.getenv("EMBEDDING_DIMENSION", str(default_dim))
        try:
            dimension = int(dim_str)
        except ValueError:
            dimension = default_dim

        api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("EMBEDDING_API_BASE", "https://api.openai.com/v1")

        return cls(
            semantic_enabled=semantic_enabled,
            provider_type=provider_type,
            model_name=model_name,
            dimension=dimension,
            api_key=api_key,
            api_base=api_base,
        )
