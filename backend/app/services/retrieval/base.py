"""
Base Retriever Interface — Abstract class for pluggable retrieval strategies.

DESIGN:
    Defines a clean contract (`retrieve`) that any code retrieval strategy
    (keyword/FTS5, vector/semantic, or hybrid/RRF) must implement.
    This enables hybrid search and vector retrieval integration without
    modifying API routers or core service orchestration.
"""

from abc import ABC, abstractmethod

from app.services.retrieval.models import SearchResult


class BaseRetriever(ABC):
    """
    Abstract interface for code retrieval strategies.
    """

    @abstractmethod
    def retrieve(
        self, query: str, repository_id: str | None = None, top_k: int = 10
    ) -> list[SearchResult]:
        """
        Retrieve relevant code chunks for a given search query.

        Args:
            query: Normalized search query string.
            repository_id: Optional repository identifier for isolation.
            top_k: Maximum number of results to retrieve.

        Returns:
            List of SearchResult objects.
        """
        pass
