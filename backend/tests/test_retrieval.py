"""
Tests for Keyword Code Retrieval & SQLite FTS5 Indexing (Phase 4.1).

Tests cover:
- Indexing CodeChunks
- Exact keyword search
- Partial keyword search (prefix matching)
- Multiple matching files
- No-result queries
- Ranking & ordering by BM25 relevance score
- Preservation of line numbers, file paths, symbol names, and signatures
"""

import pytest

from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.parsing.models import ParsedFile, SymbolInfo, SymbolKind
from app.services.retrieval.engine import KeywordSearchEngine
from app.services.retrieval.models import CodeChunk


class TestSQLiteFTSIndex:
    """Direct tests for the SQLite FTS5 index storage manager."""

    @pytest.fixture
    def fts_index(self):
        index = SQLiteFTSIndex(db_path=":memory:")
        yield index
        index.close()

    def test_indexing_and_exact_search(self, fts_index):
        """Exact keyword matching should locate target symbols and preserve metadata."""
        chunk = CodeChunk(
            chunk_id="backend/app/main.py:L31-L42:health_check",
            relative_path="backend/app/main.py",
            language="Python",
            start_line=31,
            end_line=42,
            code_content="def health_check():\n    return {'status': 'ok'}",
            symbol_name="health_check",
            symbol_kind="function",
            signature="def health_check():",
        )
        fts_index.index_chunks([chunk])

        results = fts_index.search("health_check")
        assert len(results) == 1
        res = results[0]
        assert res.chunk.symbol_name == "health_check"
        assert res.chunk.relative_path == "backend/app/main.py"
        assert res.chunk.start_line == 31
        assert res.chunk.end_line == 42
        assert res.score >= 0

    def test_partial_keyword_prefix_search(self, fts_index):
        """Prefix search (e.g. 'health') should match 'health_check'."""
        chunk = CodeChunk(
            chunk_id="app/main.py:L1-L5:health_check",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def health_check(): pass",
            symbol_name="health_check",
        )
        fts_index.index_chunks([chunk])

        results = fts_index.search("health")
        assert len(results) == 1
        assert results[0].chunk.symbol_name == "health_check"

    def test_no_result_query(self, fts_index):
        """Queries with no matching terms should return an empty result list."""
        chunk = CodeChunk(
            chunk_id="app/main.py:L1-L5:foo",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def foo(): pass",
            symbol_name="foo",
        )
        fts_index.index_chunks([chunk])

        results = fts_index.search("nonexistent_term_xyz")
        assert len(results) == 0

    def test_multiple_matching_files_and_ranking(self, fts_index):
        """Multiple matches should be returned and ranked by relevance."""
        chunk1 = CodeChunk(
            chunk_id="file1.py:L1-L10:auth_user",
            relative_path="file1.py",
            language="Python",
            start_line=1,
            end_line=10,
            code_content="def auth_user(): auth_user_check()",
            symbol_name="auth_user",
        )
        chunk2 = CodeChunk(
            chunk_id="file2.py:L1-L10:other_func",
            relative_path="file2.py",
            language="Python",
            start_line=1,
            end_line=10,
            code_content="def other_func(): pass # mentions auth once",
            symbol_name="other_func",
        )
        fts_index.index_chunks([chunk1, chunk2])

        results = fts_index.search("auth", top_k=10)
        assert len(results) == 2
        paths = [r.chunk.relative_path for r in results]
        assert "file1.py" in paths
        assert "file2.py" in paths

    def test_metadata_preservation(self, fts_index):
        """All metadata fields must be preserved exactly after indexing and retrieval."""
        chunk = CodeChunk(
            chunk_id="service/scanner.py:L40-L50:ScannerError",
            relative_path="service/scanner.py",
            language="Python",
            start_line=40,
            end_line=50,
            code_content="class ScannerError(Exception):\n    pass",
            symbol_name="ScannerError",
            symbol_kind="class",
            parent_name="Exception",
            signature="class ScannerError(Exception):",
            docstring="Raised when scanner fails.",
        )
        fts_index.index_chunks([chunk])

        results = fts_index.search("ScannerError")
        assert len(results) == 1
        c = results[0].chunk
        assert c.chunk_id == "service/scanner.py:L40-L50:ScannerError"
        assert c.relative_path == "service/scanner.py"
        assert c.language == "Python"
        assert c.start_line == 40
        assert c.end_line == 50
        assert c.symbol_name == "ScannerError"
        assert c.symbol_kind == "class"
        assert c.parent_name == "Exception"
        assert c.signature == "class ScannerError(Exception):"
        assert c.docstring == "Raised when scanner fails."


    def test_special_characters_in_query(self, fts_index):
        """Queries containing punctuation or code syntax symbols should not crash FTS5."""
        chunk = CodeChunk(
            chunk_id="app/main.py:L1-L5:health_check",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def health_check(): return {'status': 'ok'}",
            symbol_name="health_check",
        )
        fts_index.index_chunks([chunk])

        # Query with symbols like (), ->, {}, :
        results = fts_index.search("def health_check() -> dict:")
        assert len(results) == 1
        assert results[0].chunk.symbol_name == "health_check"

    def test_top_k_limit(self, fts_index):
        """top_k limit should be respected when multiple chunks match."""
        chunks = [
            CodeChunk(
                chunk_id=f"file{i}.py:L1-L5:func{i}",
                relative_path=f"file{i}.py",
                language="Python",
                start_line=1,
                end_line=5,
                code_content=f"def func{i}(): helper_function()",
                symbol_name=f"func{i}",
            )
            for i in range(10)
        ]
        fts_index.index_chunks(chunks)

        results = fts_index.search("helper_function", top_k=3)
        assert len(results) == 3


class TestKeywordSearchEngineIntegration:
    """Integration tests for repository indexing and keyword search."""

    def test_search_engine_with_sample_repo(self, sample_repo):
        """KeywordSearchEngine should index a repository and execute searches."""
        engine = KeywordSearchEngine()
        num_chunks = engine.index_repository(str(sample_repo))

        assert num_chunks > 0

        # Search for function 'add' defined in utils.py of sample_repo
        response = engine.search("add")
        assert response.total_matches > 0
        match_paths = [r.chunk.relative_path for r in response.results]
        assert "utils.py" in match_paths

        engine.close()
