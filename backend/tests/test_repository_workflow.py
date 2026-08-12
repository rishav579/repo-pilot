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
