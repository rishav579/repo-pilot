"""
Retrieval Domain Models — Typed data structures for code chunks and search results.

WHY CODE CHUNKS?
    Instead of searching whole files (which are too large for precise citation),
    we break code down into discrete, searchable "chunks" aligned with AST symbol
    boundaries (functions, classes, methods).

EVERY SEARCH RESULT PRESERVES:
    1. relative_path — e.g. "backend/app/main.py"
    2. symbol_name — e.g. "health_check"
    3. language — e.g. "Python"
    4. start_line & end_line — 1-indexed line numbers for citations (e.g. L31-L42)
    5. code_content — source snippet
"""

from pydantic import BaseModel


class CodeChunk(BaseModel):
    """
    Represents a searchable slice of source code with preserved metadata.
    """

    chunk_id: str
    relative_path: str
    language: str
    start_line: int
    end_line: int
    code_content: str
    symbol_name: str | None = None
    symbol_kind: str | None = None
    parent_name: str | None = None
    signature: str | None = None
    docstring: str | None = None


class SearchResult(BaseModel):
    """
    Represents a single matching code chunk with relevance score.
    """

    chunk: CodeChunk
    score: float
    score_type: str = "bm25"
    matched_keywords: list[str] = []


class SearchResponse(BaseModel):
    """
    API Response model for code retrieval queries.
    """

    query: str
    total_matches: int
    results: list[SearchResult]
