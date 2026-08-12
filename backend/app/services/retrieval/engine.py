"""
Retrieval Service & Engine — Orchestrates indexing, query normalization, strategy execution, and result formatting.

FLOW:
    1. Parse repository using Phase 3 Tree-sitter parser (`parse_repository`)
    2. Convert parsed files into CodeChunks using symbol & sliding-window strategies (`chunk_parsed_file`)
    3. Index CodeChunks into SQLite FTS5 database (`SQLiteFTSIndex`)
    4. Normalize user query (`normalize_query`)
    5. Execute retrieval strategy (`KeywordRetriever` / `HybridRetriever`)
    6. Deduplicate and rank results deterministically (`deduplicate_search_results`)
    7. Return formatted `SearchResponse`
"""

from pathlib import Path

from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.parsing.parser import parse_repository
from app.services.retrieval.deduplicator import deduplicate_search_results
from app.services.retrieval.models import CodeChunk, SearchResponse, SearchResult
from app.services.retrieval.normalizer import normalize_query
from app.services.retrieval.strategies import HybridRetriever, KeywordRetriever

DEFAULT_TOP_K = 10
MAX_TOP_K = 100


class RetrievalService:
    """
    Service layer for code indexing and retrieval.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.fts_index = SQLiteFTSIndex(db_path=db_path)
        self.keyword_retriever = KeywordRetriever(self.fts_index)
        self.hybrid_retriever = HybridRetriever([self.keyword_retriever])

    def index_repository(self, repo_path: str) -> int:
        """
        Parse and index an entire local repository.

        Args:
            repo_path: Path to repository root directory.

        Returns:
            Number of CodeChunks indexed.
        """
        parse_res = parse_repository(repo_path)
        repo_root = Path(parse_res.repository_path)

        all_chunks: list[CodeChunk] = []

        for parsed_file in parse_res.files:
            file_chunks = chunk_parsed_file(parsed_file, repo_root)
            all_chunks.extend(file_chunks)

        self.fts_index.clear()
        self.fts_index.index_chunks(all_chunks)
        return len(all_chunks)

    def search(self, raw_query: str, top_k: int = DEFAULT_TOP_K) -> SearchResponse:
        """
        Execute search query with normalization, top_k validation, and deduplication.

        Args:
            raw_query: Raw search query string.
            top_k: Number of top matching chunks to return.

        Returns:
            SearchResponse containing query, total matches, and list of SearchResult items.
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

        raw_results = self.hybrid_retriever.retrieve(normalized, top_k=effective_top_k)
        deduped_results = deduplicate_search_results(raw_results)[:effective_top_k]

        return SearchResponse(
            query=normalized,
            total_matches=len(deduped_results),
            results=deduped_results,
        )

    def close(self):
        """Close storage resources."""
        self.fts_index.close()


# Backward-compatible alias for existing imports
KeywordSearchEngine = RetrievalService
