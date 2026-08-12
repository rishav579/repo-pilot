"""
SQLite FTS5 Keyword Search Storage & Retrieval Engine.

WHY SQLITE FTS5?
    1. Zero configuration — built into Python's sqlite3 module.
    2. Deterministic BM25 ranking algorithm — fast, accurate keyword matching.
    3. Instant — queries execute in < 1ms even over thousands of chunks.
    4. Storage Abstraction — easy to replace with PostgreSQL (pg_trgm / tsvector) later.
"""

import re
import sqlite3
from typing import Any

from app.services.retrieval.models import CodeChunk, SearchResult


class SQLiteFTSIndex:
    """
    Manages an in-memory or file-backed SQLite FTS5 keyword index for CodeChunks.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Create the FTS5 virtual table if it does not exist."""
        with self.conn:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS code_chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    repository_id UNINDEXED,
                    relative_path UNINDEXED,
                    language UNINDEXED,
                    symbol_name,
                    symbol_kind UNINDEXED,
                    parent_name UNINDEXED,
                    start_line UNINDEXED,
                    end_line UNINDEXED,
                    signature,
                    docstring,
                    code_content,
                    tokenize = 'unicode61'
                );
                """
            )

    def clear(self, repository_id: str | None = None):
        """Clear indexed chunks from the database for a specific repo or all repos."""
        with self.conn:
            if repository_id:
                self.conn.execute(
                    "DELETE FROM code_chunks_fts WHERE repository_id = ?;", (repository_id,)
                )
            else:
                self.conn.execute("DELETE FROM code_chunks_fts;")

    def index_chunks(self, chunks: list[CodeChunk]):
        """
        Insert or replace a list of CodeChunks into the FTS5 index.
        """
        rows = [
            (
                c.chunk_id,
                getattr(c, "repository_id", "default"),
                c.relative_path,
                c.language,
                c.symbol_name or "",
                c.symbol_kind or "",
                c.parent_name or "",
                str(c.start_line),
                str(c.end_line),
                c.signature or "",
                c.docstring or "",
                c.code_content,
            )
            for c in chunks
        ]

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO code_chunks_fts (
                    chunk_id, repository_id, relative_path, language, symbol_name,
                    symbol_kind, parent_name, start_line, end_line,
                    signature, docstring, code_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )

    def search(self, query_text: str, repository_id: str | None = None, top_k: int = 10) -> list[SearchResult]:
        """
        Search indexed code chunks using BM25 keyword matching.

        Args:
            query_text: User search query.
            repository_id: Optional repository_id filter.
            top_k: Maximum number of results to return.

        Returns:
            List of SearchResult objects sorted by BM25 relevance score.
        """
        clean_query = query_text.strip()
        if not clean_query:
            return []

        STOP_WORDS = {
            "where", "is", "the", "in", "a", "an", "how", "what", "which",
            "are", "of", "to", "for", "on", "with", "does", "do", "it", "be",
            "defined", "implemented"
        }
        all_tokens = re.findall(r"\w+", clean_query)
        if not all_tokens:
            return []

        # Filter stop words if non-stop word tokens exist
        substantive_tokens = [t for t in all_tokens if t.lower() not in STOP_WORDS]
        tokens = substantive_tokens if substantive_tokens else all_tokens

        # Build FTS match query with prefix matching (e.g. "scan*" matches "scanner")
        fts_conditions = [f'"{t}" OR {t}*' for t in tokens]
        fts_query = " OR ".join(fts_conditions)

        cursor = self.conn.cursor()
        try:
            if repository_id:
                cursor.execute(
                    """
                    SELECT
                        chunk_id, repository_id, relative_path, language, symbol_name,
                        symbol_kind, parent_name, start_line, end_line,
                        signature, docstring, code_content,
                        bm25(code_chunks_fts) as rank_score
                    FROM code_chunks_fts
                    WHERE code_chunks_fts MATCH ? AND repository_id = ?
                    ORDER BY rank_score ASC
                    LIMIT ?;
                    """,
                    (fts_query, repository_id, top_k),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        chunk_id, repository_id, relative_path, language, symbol_name,
                        symbol_kind, parent_name, start_line, end_line,
                        signature, docstring, code_content,
                        bm25(code_chunks_fts) as rank_score
                    FROM code_chunks_fts
                    WHERE code_chunks_fts MATCH ?
                    ORDER BY rank_score ASC
                    LIMIT ?;
                    """,
                    (fts_query, top_k),
                )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # If MATCH syntax fails on edge case tokens, fallback to simple phrase match
            try:
                if repository_id:
                    cursor.execute(
                        """
                        SELECT
                            chunk_id, repository_id, relative_path, language, symbol_name,
                            symbol_kind, parent_name, start_line, end_line,
                            signature, docstring, code_content,
                            bm25(code_chunks_fts) as rank_score
                        FROM code_chunks_fts
                        WHERE code_chunks_fts MATCH ? AND repository_id = ?
                        ORDER BY rank_score ASC
                        LIMIT ?;
                        """,
                        (f'"{clean_query}"*', repository_id, top_k),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT
                            chunk_id, repository_id, relative_path, language, symbol_name,
                            symbol_kind, parent_name, start_line, end_line,
                            signature, docstring, code_content,
                            bm25(code_chunks_fts) as rank_score
                        FROM code_chunks_fts
                        WHERE code_chunks_fts MATCH ?
                        ORDER BY rank_score ASC
                        LIMIT ?;
                        """,
                        (f'"{clean_query}"*', top_k),
                    )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                return []

        results: list[SearchResult] = []
        for row in rows:
            chunk = CodeChunk(
                chunk_id=row["chunk_id"],
                repository_id=row["repository_id"] if "repository_id" in row.keys() else "default",
                relative_path=row["relative_path"],
                language=row["language"],
                start_line=int(row["start_line"]),
                end_line=int(row["end_line"]),
                code_content=row["code_content"],
                symbol_name=row["symbol_name"] if row["symbol_name"] else None,
                symbol_kind=row["symbol_kind"] if row["symbol_kind"] else None,
                parent_name=row["parent_name"] if row["parent_name"] else None,
                signature=row["signature"] if row["signature"] else None,
                docstring=row["docstring"] if row["docstring"] else None,
            )

            # In FTS5 bm25(), lower/more negative values indicate higher relevance
            # We convert to a positive relevance score for display
            bm25_val = float(row["rank_score"])
            score = round(abs(bm25_val), 4)

            # Identify matching keywords from query tokens present in the content/name
            matched = [
                t for t in tokens
                if t.lower() in (chunk.code_content.lower() + (chunk.symbol_name or "").lower())
            ]

            results.append(
                SearchResult(
                    chunk=chunk,
                    score=score,
                    score_type="bm25",
                    matched_keywords=matched,
                )
            )

        # Deterministic sorting: sort by relevance score DESC, then chunk_id ASC as tiebreaker
        results.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        return results

    def close(self):
        """Close database connection."""
        self.conn.close()
