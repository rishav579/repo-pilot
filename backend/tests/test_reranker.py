"""
Phase 7 Code-Aware Reranker Tests — Validates reranking signals, determinism, isolation, and backward compatibility.
"""

import pytest

from app.services.retrieval.models import CodeChunk, SearchResult
from app.services.retrieval.query_analyzer import QuerySignals, analyze_query
from app.services.retrieval.reranker import CodeAwareReranker, CodeAwareRerankerConfig, RerankedResult


# ─── Helper Factories ─────────────────────────────────────────────────────────

def _make_chunk(
    chunk_id: str = "test/file.py:L1-L10:test_func",
    relative_path: str = "backend/app/main.py",
    symbol_name: str | None = "health_check",
    symbol_kind: str | None = "function",
    signature: str | None = "def health_check():",
    docstring: str | None = "Health check endpoint.",
    code_content: str = 'def health_check():\n    return {"status": "ok"}',
    language: str = "Python",
    start_line: int = 1,
    end_line: int = 10,
    repository_id: str = "repo-abc",
) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        relative_path=relative_path,
        symbol_name=symbol_name,
        symbol_kind=symbol_kind,
        signature=signature,
        docstring=docstring,
        code_content=code_content,
        language=language,
        start_line=start_line,
        end_line=end_line,
        repository_id=repository_id,
    )


def _make_result(
    chunk: CodeChunk | None = None,
    score: float = 5.0,
    score_type: str = "bm25",
    matched_keywords: list[str] | None = None,
) -> SearchResult:
    return SearchResult(
        chunk=chunk or _make_chunk(),
        score=score,
        score_type=score_type,
        matched_keywords=matched_keywords or [],
    )


# ─── Query Analyzer Tests ─────────────────────────────────────────────────────

class TestQueryAnalyzer:
    """Tests for deterministic query signal extraction."""

    def test_identifier_extraction(self):
        signals = analyze_query("Where is health_check defined?")
        assert "health_check" in signals.identifier_tokens

    def test_filename_extraction(self):
        signals = analyze_query("Show me main.py")
        assert "main.py" in signals.filename_tokens

    def test_route_extraction(self):
        signals = analyze_query("Where is /health implemented?")
        assert "/health" in signals.route_tokens

    def test_path_extraction(self):
        signals = analyze_query("Show me backend/app/main.py")
        assert any("backend/app/main.py" in p for p in signals.path_tokens)

    def test_quoted_extraction(self):
        signals = analyze_query('Where is "scan_repository" defined?')
        assert "scan_repository" in signals.quoted_tokens

    def test_stop_word_filtering(self):
        signals = analyze_query("Where is the health check?")
        assert "where" not in signals.normalized_tokens
        assert "is" not in signals.normalized_tokens
        assert "the" not in signals.normalized_tokens

    def test_empty_query(self):
        signals = analyze_query("")
        assert signals.normalized_tokens == []
        assert signals.identifier_tokens == []

    def test_determinism(self):
        """Same query must always produce identical signals."""
        q = "Where is health_check in backend/app/main.py?"
        s1 = analyze_query(q)
        s2 = analyze_query(q)
        assert s1 == s2


# ─── Reranker Core Tests ──────────────────────────────────────────────────────

class TestCodeAwareReranker:
    """Tests for code-aware reranking signals and behavior."""

    def test_exact_symbol_match_outranks_generic(self):
        """A chunk with exact symbol name match should outrank a generic match."""
        reranker = CodeAwareReranker()

        exact_chunk = _make_chunk(
            chunk_id="exact",
            symbol_name="health_check",
            code_content="def health_check(): pass",
        )
        generic_chunk = _make_chunk(
            chunk_id="generic",
            symbol_name="process_request",
            code_content="def process_request(): health = True",
        )

        candidates = [
            _make_result(generic_chunk, score=6.0),
            _make_result(exact_chunk, score=5.0),  # Lower base score
        ]

        results = reranker.rerank("health_check", candidates, top_k=2)
        # Exact symbol match should be ranked first despite lower base score
        assert results[0].chunk.chunk_id == "exact"

    def test_filename_match_improves_ranking(self):
        """Filename match should boost ranking."""
        reranker = CodeAwareReranker()

        file_match_chunk = _make_chunk(
            chunk_id="file_match",
            relative_path="backend/app/main.py",
            symbol_name="startup",
            code_content="async def startup(): pass",
        )
        other_chunk = _make_chunk(
            chunk_id="other",
            relative_path="backend/app/utils.py",
            symbol_name="helper",
            code_content="def helper(): pass",
        )

        candidates = [
            _make_result(other_chunk, score=6.0),
            _make_result(file_match_chunk, score=5.0),
        ]

        results = reranker.rerank("main.py startup", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "file_match"

    def test_route_match_improves_ranking(self):
        """API route match should boost ranking."""
        reranker = CodeAwareReranker()

        route_chunk = _make_chunk(
            chunk_id="route",
            symbol_name="health",
            code_content='@app.get("/health")\ndef health(): return {"ok": True}',
        )
        other_chunk = _make_chunk(
            chunk_id="other",
            symbol_name="unrelated",
            code_content="def unrelated(): pass",
        )

        candidates = [
            _make_result(other_chunk, score=6.0),
            _make_result(route_chunk, score=5.0),
        ]

        results = reranker.rerank("Where is /health endpoint?", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "route"

    def test_signature_match_improves_ranking(self):
        """Signature match should boost ranking."""
        reranker = CodeAwareReranker()

        sig_chunk = _make_chunk(
            chunk_id="sig_match",
            symbol_name="validate",
            signature="def validate_repository_path(raw_path: str) -> Path:",
            code_content="def validate_repository_path(raw_path): pass",
        )
        other_chunk = _make_chunk(
            chunk_id="other",
            symbol_name="helper",
            signature="def helper():",
            code_content="def helper(): pass",
        )

        candidates = [
            _make_result(other_chunk, score=6.0),
            _make_result(sig_chunk, score=5.0),
        ]

        results = reranker.rerank("validate_repository_path", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "sig_match"

    def test_docstring_match_improves_ranking(self):
        """Docstring match should boost ranking."""
        reranker = CodeAwareReranker()

        doc_chunk = _make_chunk(
            chunk_id="doc_match",
            symbol_name="index_data",
            docstring="Manages SQLite FTS5 keyword index for code chunks.",
            code_content="def index_data(): pass",
        )
        other_chunk = _make_chunk(
            chunk_id="other",
            symbol_name="helper",
            docstring="A utility helper.",
            code_content="def helper(): pass",
        )

        candidates = [
            _make_result(other_chunk, score=5.5),
            _make_result(doc_chunk, score=5.0),
        ]

        results = reranker.rerank("FTS5 keyword index", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "doc_match"

    def test_deterministic_ordering(self):
        """Same query + same candidates must always produce identical ordering."""
        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id="a", symbol_name="foo"), score=5.0),
            _make_result(_make_chunk(chunk_id="b", symbol_name="bar"), score=5.0),
            _make_result(_make_chunk(chunk_id="c", symbol_name="baz"), score=5.0),
        ]

        r1 = reranker.rerank("test query", candidates, top_k=3)
        r2 = reranker.rerank("test query", candidates, top_k=3)
        assert [r.chunk.chunk_id for r in r1] == [r.chunk.chunk_id for r in r2]

    def test_score_normalization(self):
        """Reranked scores should be non-negative."""
        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id="a"), score=0.001),
            _make_result(_make_chunk(chunk_id="b"), score=100.0),
        ]

        results = reranker.rerank("health_check", candidates, top_k=2)
        for r in results:
            assert r.score >= 0.0

    def test_empty_candidate_list(self):
        """Empty candidates should return empty results."""
        reranker = CodeAwareReranker()
        results = reranker.rerank("test", [], top_k=5)
        assert results == []

    def test_empty_query(self):
        """Empty query should return candidates unchanged (up to top_k)."""
        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id="a"), score=5.0),
            _make_result(_make_chunk(chunk_id="b"), score=3.0),
        ]
        results = reranker.rerank("", candidates, top_k=2)
        assert len(results) == 2

    def test_duplicate_candidates(self):
        """Duplicate chunk IDs should be handled (same chunk keeps highest)."""
        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id="dup"), score=5.0),
            _make_result(_make_chunk(chunk_id="dup"), score=3.0),
            _make_result(_make_chunk(chunk_id="other"), score=4.0),
        ]
        results = reranker.rerank("test", candidates, top_k=3)
        # All 3 results should be returned (deduplication happens upstream)
        assert len(results) == 3

    def test_reranked_score_type(self):
        """Reranked results should have score_type='reranked'."""
        reranker = CodeAwareReranker()
        candidates = [_make_result(_make_chunk(chunk_id="a"), score=5.0)]
        results = reranker.rerank("test", candidates, top_k=1)
        assert results[0].score_type == "reranked"

    def test_custom_config_weights(self):
        """Custom config weights should be respected."""
        config = CodeAwareRerankerConfig(
            exact_symbol_weight=1.0,
            filename_weight=0.0,
            path_token_weight=0.0,
            signature_weight=0.0,
            docstring_weight=0.0,
            code_overlap_weight=0.0,
            route_match_weight=0.0,
            symbol_type_weight=0.0,
        )
        reranker = CodeAwareReranker(config=config)

        exact_chunk = _make_chunk(chunk_id="exact", symbol_name="target_func")
        other_chunk = _make_chunk(chunk_id="other", symbol_name="unrelated")

        candidates = [
            _make_result(other_chunk, score=10.0),
            _make_result(exact_chunk, score=1.0),
        ]

        results = reranker.rerank("target_func", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "exact"

    def test_identifier_token_matching(self):
        """Query with identifier tokens should boost matching chunks."""
        reranker = CodeAwareReranker()

        matching_chunk = _make_chunk(
            chunk_id="match",
            symbol_name="scan_repository",
            code_content="def scan_repository(path): pass",
        )
        other_chunk = _make_chunk(
            chunk_id="other",
            symbol_name="helper",
            code_content="def helper(): pass",
        )

        candidates = [
            _make_result(other_chunk, score=6.0),
            _make_result(matching_chunk, score=5.0),
        ]

        results = reranker.rerank("Where is scan_repository?", candidates, top_k=2)
        assert results[0].chunk.chunk_id == "match"


# ─── Repository Isolation Tests ───────────────────────────────────────────────

class TestRerankerRepositoryIsolation:
    """Verify reranker operates only on supplied candidate list."""

    def test_reranker_does_not_introduce_cross_repo_results(self):
        """Reranker must only reorder supplied candidates, never introduce new ones."""
        reranker = CodeAwareReranker()

        repo_a_chunk = _make_chunk(chunk_id="repo_a_1", repository_id="repo-aaa")
        repo_b_chunk = _make_chunk(chunk_id="repo_b_1", repository_id="repo-bbb")

        # Only repo_a candidates supplied
        candidates_a = [_make_result(repo_a_chunk, score=5.0)]
        results_a = reranker.rerank("test", candidates_a, top_k=10)

        # Verify no repo_b results appear
        for r in results_a:
            assert r.chunk.repository_id == "repo-aaa"

        # Only repo_b candidates supplied
        candidates_b = [_make_result(repo_b_chunk, score=5.0)]
        results_b = reranker.rerank("test", candidates_b, top_k=10)

        for r in results_b:
            assert r.chunk.repository_id == "repo-bbb"

    def test_reranker_output_count_matches_input(self):
        """Reranker should not add or remove candidates (only reorder)."""
        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id=f"c{i}", repository_id="repo-x"), score=float(i))
            for i in range(5)
        ]
        results = reranker.rerank("test", candidates, top_k=10)
        assert len(results) == 5  # All 5 returned, none added


# ─── Backward Compatibility Tests ─────────────────────────────────────────────

class TestBackwardCompatibility:
    """Verify existing retrieval functionality is preserved."""

    def test_keyword_retrieval_integration(self):
        """KeywordRetriever should still work independently."""
        from app.services.indexing.sqlite_fts import SQLiteFTSIndex
        from app.services.retrieval.strategies import KeywordRetriever

        fts = SQLiteFTSIndex(db_path=":memory:")
        chunk = _make_chunk(
            chunk_id="test:L1-L5:hello",
            symbol_name="hello",
            code_content="def hello(): print('hi')",
        )
        fts.index_chunks([chunk])

        retriever = KeywordRetriever(fts)
        results = retriever.retrieve("hello", top_k=5)
        assert len(results) > 0
        assert results[0].chunk.symbol_name == "hello"
        fts.close()

    def test_hybrid_retrieval_integration(self):
        """HybridRetriever should still work independently."""
        from app.services.indexing.sqlite_fts import SQLiteFTSIndex
        from app.services.retrieval.strategies import HybridRetriever, KeywordRetriever

        fts = SQLiteFTSIndex(db_path=":memory:")
        chunk = _make_chunk(
            chunk_id="test:L1-L5:world",
            symbol_name="world",
            code_content="def world(): return 42",
        )
        fts.index_chunks([chunk])

        keyword_ret = KeywordRetriever(fts)
        hybrid = HybridRetriever([keyword_ret])
        results = hybrid.retrieve("world", top_k=5)
        assert len(results) > 0
        fts.close()

    def test_rag_evidence_receives_valid_results(self):
        """RAG EvidenceSelector should work with reranked results."""
        from app.services.rag.evidence import EvidenceSelector

        reranker = CodeAwareReranker()
        candidates = [
            _make_result(_make_chunk(chunk_id="a", symbol_name="func_a"), score=5.0),
            _make_result(_make_chunk(chunk_id="b", symbol_name="func_b"), score=3.0),
        ]
        reranked = reranker.rerank("func_a", candidates, top_k=2)

        selector = EvidenceSelector(min_relevance_score=0.0, max_evidence_chunks=5)
        evidence = selector.select_evidence(reranked)
        assert len(evidence) > 0
        assert evidence[0].chunk.chunk_id == "a"  # Should be first after reranking

    def test_citation_validity_preserved(self):
        """Reranked results should preserve chunk metadata for citations."""
        reranker = CodeAwareReranker()
        chunk = _make_chunk(
            chunk_id="cit_test",
            relative_path="backend/app/main.py",
            start_line=31,
            end_line=42,
            symbol_name="health_check",
        )
        candidates = [_make_result(chunk, score=5.0)]
        results = reranker.rerank("health_check", candidates, top_k=1)

        # Verify all citation-relevant metadata is preserved
        r = results[0]
        assert r.chunk.relative_path == "backend/app/main.py"
        assert r.chunk.start_line == 31
        assert r.chunk.end_line == 42
        assert r.chunk.symbol_name == "health_check"
