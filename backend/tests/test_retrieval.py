"""
Tests for Retrieval Quality, Normalization, Deduplication, & API Contract (Phase 4.2).

Tests cover all 12 required scenarios:
1. empty query
2. whitespace-only query
3. normal keyword query
4. ranking/order (score DESC, then chunk_id ASC tiebreaker)
5. default top_k
6. custom top_k
7. invalid top_k
8. excessive top_k
9. no-result query
10. duplicate-result handling (deduplication)
11. deterministic results across repeated identical queries
12. API response contract (FastAPI TestClient)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.retrieval.deduplicator import deduplicate_search_results
from app.services.retrieval.engine import RetrievalService
from app.services.retrieval.models import CodeChunk, SearchResult
from app.services.retrieval.normalizer import normalize_query

client = TestClient(app)


class TestQueryNormalizer:
    """Tests for query normalization logic."""

    def test_empty_and_whitespace_query(self):
        """Empty or whitespace-only inputs should return empty string."""
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""
        assert normalize_query("\t \n ") == ""
        assert normalize_query(None) == ""

    def test_normal_query_whitespace_stripping(self):
        """Leading, trailing, and internal repeated whitespace should be collapsed."""
        assert normalize_query("  health_check  ") == "health_check"
        assert normalize_query("health    check\n\tquery") == "health check query"

    def test_excessive_length_query_truncation(self):
        """Queries exceeding MAX_QUERY_LENGTH (500 chars) should be truncated."""
        long_query = "word " * 200  # 1000 chars
        normalized = normalize_query(long_query)
        assert len(normalized) <= 500


class TestDeduplicationAndRanking:
    """Tests for result deduplication and deterministic sorting."""

    def test_deduplication_keeps_highest_score(self):
        """When duplicate chunk_ids exist, deduplication retains the higher score."""
        c1 = CodeChunk(
            chunk_id="app/main.py:L1-L10:func",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=10,
            code_content="def func(): pass",
        )
        res1 = SearchResult(chunk=c1, score=1.5, matched_keywords=["func"])
        res2 = SearchResult(chunk=c1, score=3.8, matched_keywords=["func", "main"])

        deduped = deduplicate_search_results([res1, res2])
        assert len(deduped) == 1
        assert deduped[0].score == 3.8

    def test_deterministic_sorting_with_score_and_chunk_id_tiebreaker(self):
        """Results must sort by score DESC, and chunk_id ASC on tie."""
        c_a = CodeChunk(
            chunk_id="a_file.py:L1-L5:func",
            relative_path="a_file.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def func(): pass",
        )
        c_b = CodeChunk(
            chunk_id="b_file.py:L1-L5:func",
            relative_path="b_file.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def func(): pass",
        )
        # Equal scores
        res_b = SearchResult(chunk=c_b, score=2.0, matched_keywords=["func"])
        res_a = SearchResult(chunk=c_a, score=2.0, matched_keywords=["func"])

        deduped = deduplicate_search_results([res_b, res_a])
        assert len(deduped) == 2
        # On tie (2.0 == 2.0), chunk_id 'a_file.py...' comes before 'b_file.py...'
        assert deduped[0].chunk.chunk_id == "a_file.py:L1-L5:func"
        assert deduped[1].chunk.chunk_id == "b_file.py:L1-L5:func"


class TestRetrievalService:
    """Tests for RetrievalService orchestration."""

    @pytest.fixture
    def service(self):
        srv = RetrievalService(db_path=":memory:")
        yield srv
        srv.close()

    def test_normal_keyword_query(self, service):
        """Normal keyword query returns matching results."""
        chunk = CodeChunk(
            chunk_id="app/main.py:L1-L5:health_check",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def health_check(): return {'status': 'ok'}",
            symbol_name="health_check",
        )
        service.fts_index.index_chunks([chunk])

        response = service.search("health_check")
        assert response.total_matches == 1
        assert response.results[0].chunk.symbol_name == "health_check"

    def test_empty_and_whitespace_query_service(self, service):
        """Searching empty/whitespace queries returns 0 matches safely."""
        response = service.search("   ")
        assert response.total_matches == 0
        assert response.results == []

    def test_no_result_query(self, service):
        """No-result query returns 0 matches."""
        chunk = CodeChunk(
            chunk_id="app/main.py:L1-L5:func",
            relative_path="app/main.py",
            language="Python",
            start_line=1,
            end_line=5,
            code_content="def func(): pass",
        )
        service.fts_index.index_chunks([chunk])

        response = service.search("non_existent_symbol_999")
        assert response.total_matches == 0
        assert response.results == []

    def test_default_top_k(self, service):
        """Default top_k should be 10."""
        chunks = [
            CodeChunk(
                chunk_id=f"file{i}.py:L1-L5:func{i}",
                relative_path=f"file{i}.py",
                language="Python",
                start_line=1,
                end_line=5,
                code_content=f"def func{i}(): common_target()",
                symbol_name=f"func{i}",
            )
            for i in range(15)
        ]
        service.fts_index.index_chunks(chunks)

        response = service.search("common_target")
        assert len(response.results) == 10  # DEFAULT_TOP_K is 10

    def test_custom_top_k(self, service):
        """Custom top_k should be respected."""
        chunks = [
            CodeChunk(
                chunk_id=f"file{i}.py:L1-L5:func{i}",
                relative_path=f"file{i}.py",
                language="Python",
                start_line=1,
                end_line=5,
                code_content=f"def func{i}(): common_target()",
                symbol_name=f"func{i}",
            )
            for i in range(10)
        ]
        service.fts_index.index_chunks(chunks)

        response = service.search("common_target", top_k=3)
        assert len(response.results) == 3

    def test_excessive_top_k_clamped(self, service):
        """Excessive top_k (e.g. 500) should be clamped to MAX_TOP_K (100)."""
        chunks = [
            CodeChunk(
                chunk_id=f"file{i}.py:L1-L5:func{i}",
                relative_path=f"file{i}.py",
                language="Python",
                start_line=1,
                end_line=5,
                code_content=f"def func{i}(): target_token()",
                symbol_name=f"func{i}",
            )
            for i in range(120)
        ]
        service.fts_index.index_chunks(chunks)

        response = service.search("target_token", top_k=500)
        assert len(response.results) <= 100

    def test_deterministic_results_across_repeated_queries(self, service):
        """Repeated identical search queries must produce identical ordered results."""
        chunks = [
            CodeChunk(
                chunk_id=f"file{i}.py:L1-L5:func{i}",
                relative_path=f"file{i}.py",
                language="Python",
                start_line=1,
                end_line=5,
                code_content=f"def func{i}(): common_keyword()",
                symbol_name=f"func{i}",
            )
            for i in range(5)
        ]
        service.fts_index.index_chunks(chunks)

        resp1 = service.search("common_keyword")
        resp2 = service.search("common_keyword")

        assert len(resp1.results) == len(resp2.results)
        for r1, r2 in zip(resp1.results, resp2.results):
            assert r1.chunk.chunk_id == r2.chunk.chunk_id
            assert r1.score == r2.score


class TestRetrievalAPIContract:
    """API Contract tests for POST /repositories/search/keyword using TestClient."""

    def test_api_normal_keyword_search(self, sample_repo):
        """API endpoint should index repo and return valid SearchResponse contract."""
        payload = {
            "path": str(sample_repo),
            "query": "add",
            "top_k": 5,
        }
        res = client.post("/repositories/search/keyword", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert "query" in data
        assert "total_matches" in data
        assert "results" in data
        assert data["query"] == "add"
        assert len(data["results"]) <= 5

        # Check evidence contract fields
        if data["results"]:
            first = data["results"][0]
            assert "chunk" in first
            assert "score" in first
            assert "score_type" in first
            assert first["score_type"] == "bm25"
            c = first["chunk"]
            assert "relative_path" in c
            assert "start_line" in c
            assert "end_line" in c
            assert "code_content" in c

    def test_api_empty_and_whitespace_query(self, sample_repo):
        """API should return HTTP 400 when query is empty or whitespace."""
        payload = {
            "path": str(sample_repo),
            "query": "   ",
            "top_k": 5,
        }
        res = client.post("/repositories/search/keyword", json=payload)
        assert res.status_code == 400
        assert "empty or whitespace" in res.json()["detail"].lower()

    def test_api_invalid_top_k_validation(self, sample_repo):
        """API should return HTTP 422 Unprocessable Entity for invalid top_k (e.g. 0 or > 100)."""
        payload = {
            "path": str(sample_repo),
            "query": "health",
            "top_k": 0,  # ge=1 violation
        }
        res = client.post("/repositories/search/keyword", json=payload)
        assert res.status_code == 422

    def test_api_invalid_repository_path(self):
        """API should return HTTP 400 Bad Request for non-existent path."""
        payload = {
            "path": "/non/existent/repo/path/xyz",
            "query": "health",
            "top_k": 5,
        }
        res = client.post("/repositories/search/keyword", json=payload)
        assert res.status_code == 400
        assert "does not exist" in res.json()["detail"].lower()
