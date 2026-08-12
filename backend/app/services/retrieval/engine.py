"""
Keyword Search Engine — Orchestrates repository parsing, chunking, indexing, and keyword search.

FLOW:
    1. Parse repository using Phase 3 Tree-sitter parser (`parse_repository`)
    2. Convert parsed files into CodeChunks using symbol & sliding-window strategies (`chunk_parsed_file`)
    3. Index CodeChunks into SQLite FTS5 database (`SQLiteFTSIndex`)
    4. Execute BM25 keyword search queries (`search`)
"""

from pathlib import Path
from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.parsing.parser import parse_repository
from app.services.retrieval.models import CodeChunk, SearchResponse, SearchResult


class KeywordSearchEngine:
    """
    High-level Keyword Search Engine.

    Can operate with an in-memory index or a persistent SQLite index.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.fts_index = SQLiteFTSIndex(db_path=db_path)

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

    def search(self, query_text: str, top_k: int = 10) -> SearchResponse:
        """
        Search indexed code chunks using BM25 keyword matching.

        Args:
            query_text: Keyword search query.
            top_k: Number of top matching chunks to return.

        Returns:
            SearchResponse containing query, total matches, and list of SearchResult items.
        """
        results = self.fts_index.search(query_text, top_k=top_k)
        return SearchResponse(
            query=query_text,
            total_matches=len(results),
            results=results,
        )

    def close(self):
        """Close storage resources."""
        self.fts_index.close()
