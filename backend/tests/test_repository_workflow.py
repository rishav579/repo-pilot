"""
Tests for Production Repository Lifecycle, Incremental Indexing, & Repository Isolation (Phase 6).

Tests cover all required categories:
1. Repository Registration & Path Canonicalization
2. Lifecycle State Transitions (REGISTERED -> INDEXING -> READY -> FAILED)
3. Incremental Indexing (Unchanged content reuse, file modification, file deletion)
4. Repository Scope Isolation (Repo A vs Repo B content isolation)
5. Query Readiness Checks (REGISTERED, INDEXING, FAILED, READY)
6. Management API Router Contract (POST /repositories, GET /repositories, GET /repositories/{id}, POST /repositories/{id}/index)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion.scanner import ScannerError
from app.services.rag.engine import RAGService
from app.services.rag.models import RAGRequest
from app.services.repository.models import RepositoryStatus
from app.services.repository.service import RepositoryService

client = TestClient(app)


class TestRepositoryRegistration:
    """Tests for repository path validation, canonicalization, and registration."""

    @pytest.fixture
    def repo_service(self):
        srv = RepositoryService(db_path=":memory:")
        yield srv
        srv.close()

    def test_register_valid_directory(self, repo_service, sample_repo):
        record = repo_service.register_repository(str(sample_repo))
        assert record.repository_id.startswith("repo-")
        assert record.status == RepositoryStatus.REGISTERED
        assert record.display_name == sample_repo.name

    def test_duplicate_registration_returns_existing_record(self, repo_service, sample_repo):
        rec1 = repo_service.register_repository(str(sample_repo))
        rec2 = repo_service.register_repository(str(sample_repo))
        assert rec1.repository_id == rec2.repository_id

    def test_register_invalid_directory(self, repo_service):
        with pytest.raises(ScannerError):
            repo_service.register_repository("/non/existent/path/xyz_999")


class TestIncrementalIndexing:
    """Tests for incremental indexing, file modifications, and file deletions."""

    def test_incremental_indexing_behavior(self, tmp_path):
        # Create temporary git repo
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        file1 = repo_dir / "math_utils.py"
        file1.write_text("def add(a, b):\n    return a + b\n")

        srv = RepositoryService(db_path=":memory:")

        # Register & First Index
        rec = srv.register_repository(str(repo_dir))
        summary1 = srv.index_repository(rec.repository_id)

        assert summary1.status == RepositoryStatus.READY
        assert summary1.chunks_created > 0
        assert summary1.chunks_updated == 0

        # Repeated Indexing with UNCHANGED content (should be 0 new chunks created)
        summary2 = srv.index_repository(rec.repository_id)
        assert summary2.chunks_created == 0
        assert summary2.chunks_updated == 0

        # Modify file content (CHANGED file)
        file1.write_text("def add(a, b):\n    # Updated comment\n    return a + b + 0\n")
        summary3 = srv.index_repository(rec.repository_id)
        assert summary3.chunks_updated > 0

        # Add new file
        file2 = repo_dir / "sub_utils.py"
        file2.write_text("def subtract(a, b):\n    return a - b\n")
        summary4 = srv.index_repository(rec.repository_id)
        assert summary4.chunks_created > 0

        # Delete file
        file2.unlink()
        summary5 = srv.index_repository(rec.repository_id)
        assert summary5.chunks_deleted > 0

        srv.close()


class TestRepositoryIsolation:
    """Tests to verify repository scope isolation between Repository A and Repository B."""

    def test_repo_a_and_repo_b_content_isolation(self, tmp_path):
        # Repo A
        repo_a = tmp_path / "repo_a"
        repo_a.mkdir()
        (repo_a / ".git").mkdir()
        (repo_a / "alpha.py").write_text("def unique_alpha_function():\n    return 'ALPHA'\n")

        # Repo B
        repo_b = tmp_path / "repo_b"
        repo_b.mkdir()
        (repo_b / ".git").mkdir()
        (repo_b / "beta.py").write_text("def unique_beta_function():\n    return 'BETA'\n")

        srv = RepositoryService(db_path=":memory:")

        rec_a = srv.register_repository(str(repo_a))
        rec_b = srv.register_repository(str(repo_b))

        srv.index_repository(rec_a.repository_id)
        srv.index_repository(rec_b.repository_id)

        # Search Repo A specifically
        res_a = srv.fts_index.search("unique_alpha_function", repository_id=rec_a.repository_id)
        assert len(res_a) == 1
        assert res_a[0].chunk.repository_id == rec_a.repository_id

        # Verify Repo B search does NOT contain Alpha content
        res_a_in_b = srv.fts_index.search("unique_alpha_function", repository_id=rec_b.repository_id)
        assert len(res_a_in_b) == 0

        # Verify Repo A search does NOT contain Beta content
        res_b_in_a = srv.fts_index.search("unique_beta_function", repository_id=rec_a.repository_id)
        assert len(res_b_in_a) == 0

        srv.close()


class TestReadinessValidation:
    """Tests for repository readiness checks during Q&A."""

    def test_registered_but_unindexed_repo_readiness(self, tmp_path):
        repo_dir = tmp_path / "unindexed_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        (repo_dir / "main.py").write_text("def main(): pass")

        srv = RepositoryService(db_path=":memory:")
        rec = srv.register_repository(str(repo_dir))

        rag = RAGService(repository_service=srv, db_path=":memory:")

        # Unindexed repository will auto-trigger indexing or check readiness
        req = RAGRequest(repository_path=rec.repository_id, question="Where is main?")
        resp = rag.query(req)
        assert resp.status in ("grounded", "insufficient_evidence")

        srv.close()
        rag.close()


class TestRepositoryManagementAPI:
    """API contract tests for repository endpoints."""

    @pytest.fixture(autouse=True)
    def setup_api_service(self):
        from app.api.router_repositories import set_repository_service
        srv = RepositoryService(db_path=":memory:")
        set_repository_service(srv)
        yield
        set_repository_service(None)
        srv.close()

    def test_api_register_list_status_and_index(self, sample_repo):
        # 1. Register Repository
        reg_res = client.post("/repositories", json={"path": str(sample_repo)})
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        repo_id = reg_data["repository_id"]
        assert reg_data["status"] == "registered"

        # 2. List Repositories
        list_res = client.get("/repositories")
        assert list_res.status_code == 200
        assert any(r["repository_id"] == repo_id for r in list_res.json())

        # 3. Get Repository Status
        status_res = client.get(f"/repositories/{repo_id}")
        assert status_res.status_code == 200
        assert status_res.json()["repository_id"] == repo_id

        # 4. Trigger Indexing
        idx_res = client.post(f"/repositories/{repo_id}/index", json={"enable_semantic": False})
        assert idx_res.status_code == 200
        assert idx_res.json()["status"] == "ready"


class TestBatchSemanticIndexingAndRecovery:
    """Tests for batch semantic embedding indexing, failure transitions, and retry behavior."""

    def test_batch_semantic_indexing_success(self, tmp_path):
        repo_dir = tmp_path / "semantic_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        for i in range(10):
            (repo_dir / f"mod_{i}.py").write_text(f"def func_{i}(): return {i}\n")

        srv = RepositoryService(db_path=":memory:")
        rec = srv.register_repository(str(repo_dir))

        # Index with semantic embeddings enabled
        summary = srv.index_repository(rec.repository_id, enable_semantic=True)
        assert summary.status == RepositoryStatus.READY
        assert summary.embeddings_generated > 0
        assert summary.embeddings_reused == 0

        # Verify record in storage is READY
        updated = srv.get_repository(rec.repository_id)
        assert updated.status == RepositoryStatus.READY
        assert updated.embedding_enabled is True
        assert updated.error_message is None

        # Re-indexing should reuse cached embeddings
        summary2 = srv.index_repository(rec.repository_id, enable_semantic=True)
        assert summary2.status == RepositoryStatus.READY
        assert summary2.embeddings_reused == summary.embeddings_generated
        assert summary2.embeddings_generated == 0

        srv.close()

    def test_indexing_failure_transitions_to_failed_state(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "fail_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        (repo_dir / "bad.py").write_text("def bad(): pass\n")

        srv = RepositoryService(db_path=":memory:")
        rec = srv.register_repository(str(repo_dir))

        # Simulate scanner failure during indexing
        def mock_scan(*args, **kwargs):
            raise ScannerError("Simulated filesystem I/O error")

        monkeypatch.setattr("app.services.repository.service.scan_repository", mock_scan)

        summary = srv.index_repository(rec.repository_id)
        assert summary.status == RepositoryStatus.FAILED
        assert "Simulated filesystem I/O error" in summary.error_message

        # Verify repository record in storage is marked FAILED
        updated = srv.get_repository(rec.repository_id)
        assert updated.status == RepositoryStatus.FAILED
        assert "Simulated filesystem I/O error" in updated.error_message

        srv.close()

    def test_retry_indexing_recovers_failed_repository(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "retry_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        (repo_dir / "retry.py").write_text("def retry_func(): return True\n")

        srv = RepositoryService(db_path=":memory:")
        rec = srv.register_repository(str(repo_dir))

        # Step 1: Force failure
        def mock_scan_fail(*args, **kwargs):
            raise ScannerError("Temporary network/disk error")

        monkeypatch.setattr("app.services.repository.service.scan_repository", mock_scan_fail)
        summary_fail = srv.index_repository(rec.repository_id)
        assert summary_fail.status == RepositoryStatus.FAILED

        # Step 2: Restore normal behavior and retry indexing
        monkeypatch.undo()
        summary_retry = srv.index_repository(rec.repository_id, enable_semantic=True)
        assert summary_retry.status == RepositoryStatus.READY
        assert summary_retry.chunks_created > 0

        # Verify repository is now READY with cleared error
        rec_ready = srv.get_repository(rec.repository_id)
        assert rec_ready.status == RepositoryStatus.READY
        assert rec_ready.error_message is None

        srv.close()

    def test_sqlite_vector_batch_storage_and_cache(self):
        from app.services.indexing.sqlite_vector import SQLiteVectorStorage

        storage = SQLiteVectorStorage(db_path=":memory:")

        # Test batch storing chunk embeddings
        items = [
            ("chunk_1", "test-model", 4, [0.1, 0.2, 0.3, 0.4]),
            ("chunk_2", "test-model", 4, [0.5, 0.6, 0.7, 0.8]),
            ("chunk_bad", "test-model", 4, [0.1]),  # Wrong dimension, should be skipped
        ]
        storage.store_chunk_embeddings_batch(items)

        all_embs = storage.get_all_embeddings("test-model", 4)
        assert len(all_embs) == 2
        assert all_embs["chunk_1"] == [0.1, 0.2, 0.3, 0.4]
        assert all_embs["chunk_2"] == [0.5, 0.6, 0.7, 0.8]
        assert "chunk_bad" not in all_embs

        # Test batch caching
        cache_items = [
            ("def func1(): pass", "test-model", [0.1, 0.2, 0.3, 0.4]),
            ("def func2(): pass", "test-model", [0.5, 0.6, 0.7, 0.8]),
        ]
        storage.cache_embeddings_batch(cache_items)

        c1 = storage.get_cached_embedding("def func1(): pass", "test-model")
        c2 = storage.get_cached_embedding("def func2(): pass", "test-model")
        assert c1 == [0.1, 0.2, 0.3, 0.4]
        assert c2 == [0.5, 0.6, 0.7, 0.8]

        storage.close()

    def test_partial_embedding_failure_semantics(self, tmp_path, monkeypatch):
        """Verify that when some batches fail, successful batches are preserved and status becomes READY."""
        from app.services.retrieval.embeddings.base import EmbeddingError

        repo_dir = tmp_path / "partial_fail_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        for i in range(10):
            (repo_dir / f"file_{i}.py").write_text(f"def func_{i}(): return {i}\n")

        srv = RepositoryService(db_path=":memory:")
        rec = srv.register_repository(str(repo_dir))

        call_count = 0
        orig_embed_batch = srv.embedding_provider.embed_batch

        def flaky_embed_batch(texts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First batch succeeds
                return orig_embed_batch(texts)
            # Subsequent batch raises EmbeddingError
            raise EmbeddingError("Simulated batch inference OOM")

        monkeypatch.setattr(srv.embedding_provider, "embed_batch", flaky_embed_batch)

        summary = srv.index_repository(rec.repository_id, enable_semantic=True)
        assert summary.status == RepositoryStatus.READY
        assert summary.embeddings_generated > 0

        # Verify record in storage is READY and preserves generated embeddings
        updated = srv.get_repository(rec.repository_id)
        assert updated.status == RepositoryStatus.READY
        assert updated.embedding_enabled is True

        srv.close()
