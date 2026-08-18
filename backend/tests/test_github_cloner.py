"""
Unit & Integration Tests for Public GitHub URL Ingestion & Isolation.
"""

import shutil
import pytest
from pathlib import Path

from app.services.ingestion.github_cloner import clone_github_repository, validate_github_url
from app.services.ingestion.scanner import ScannerError
from app.services.repository.models import RepositoryRegistrationRequest, RepositoryStatus
from app.services.repository.service import RepositoryService


class TestGitHubUrlValidation:
    """Test validation rules for public HTTPS GitHub repository URLs."""

    def test_valid_github_urls(self):
        urls = [
            "https://github.com/rishav579/repo-pilot",
            "https://github.com/rishav579/repo-pilot.git",
            "https://github.com/rishav579/repo-pilot/",
            "https://github.com/psf/requests",
        ]
        for url in urls:
            canonical, owner, repo = validate_github_url(url)
            assert canonical.startswith("https://github.com/")
            assert owner in ("rishav579", "psf")
            assert repo in ("repo-pilot", "requests")

    def test_invalid_protocol_rejected(self):
        invalid_protocols = [
            "http://github.com/rishav579/repo-pilot",
            "git@github.com:rishav579/repo-pilot.git",
            "ssh://git@github.com/rishav579/repo-pilot.git",
            "file:///etc/passwd",
            "ftp://github.com/repo",
        ]
        for url in invalid_protocols:
            with pytest.raises(ScannerError) as exc:
                validate_github_url(url)
            assert "Only public HTTPS GitHub URLs" in str(exc.value)

    def test_command_injection_rejected(self):
        dangerous_urls = [
            "https://github.com/owner/repo; rm -rf /",
            "https://github.com/owner/repo | cat /etc/passwd",
            "https://github.com/owner/repo`whoami`",
            "https://github.com/owner/repo$(id)",
            "https://github.com/owner/repo & calc.exe",
        ]
        for url in dangerous_urls:
            with pytest.raises(ScannerError) as exc:
                validate_github_url(url)
            assert "forbidden" in str(exc.value).lower() or "format" in str(exc.value).lower()

    def test_invalid_domain_rejected(self):
        with pytest.raises(ScannerError):
            validate_github_url("https://gitlab.com/owner/repo")


class TestGitHubRegistrationRequestModel:
    """Test RepositoryRegistrationRequest validation logic."""

    def test_valid_local_path_request(self):
        req = RepositoryRegistrationRequest(path="/tmp/my-repo")
        assert req.path == "/tmp/my-repo"
        assert req.github_url is None

    def test_valid_github_url_request(self):
        req = RepositoryRegistrationRequest(github_url="https://github.com/rishav579/repo-pilot")
        assert req.github_url == "https://github.com/rishav579/repo-pilot"
        assert req.path is None

    def test_missing_both_rejected(self):
        with pytest.raises(ValueError) as exc:
            RepositoryRegistrationRequest()
        assert "Either 'path' or 'github_url' must be provided" in str(exc.value)

    def test_both_provided_rejected(self):
        with pytest.raises(ValueError) as exc:
            RepositoryRegistrationRequest(
                path="/tmp/my-repo",
                github_url="https://github.com/rishav579/repo-pilot",
            )
        assert "not both" in str(exc.value)


class TestGitHubRepositoryServiceIntegration:
    """Integration test for cloning, registering, indexing, and querying a real public GitHub repository."""

    @pytest.fixture
    def repo_service(self, tmp_path):
        db_file = str(tmp_path / "test_github.db")
        clones_dir = tmp_path / "clones"
        service = RepositoryService(db_path=db_file, clones_dir=clones_dir)
        yield service
        service.close()

    def test_register_and_index_public_github_repo(self, repo_service):
        github_url = "https://github.com/rishav579/repo-pilot"

        # 1. Register GitHub Repository
        record = repo_service.register_repository(github_url=github_url)
        assert record.source_type == "github"
        assert record.github_url == "https://github.com/rishav579/repo-pilot"
        assert record.status == RepositoryStatus.REGISTERED
        assert Path(record.canonical_path).exists()
        assert (Path(record.canonical_path) / "README.md").exists()

        # 2. Trigger Indexing
        summary = repo_service.index_repository(record.repository_id)
        assert summary.status == RepositoryStatus.READY
        assert summary.files_parsed > 0
        assert summary.chunks_created > 0

        # 3. Query Index
        results = repo_service.fts_index.search(
            "scan_repository", repository_id=record.repository_id
        )
        assert len(results) > 0
        assert results[0].chunk.repository_id == record.repository_id

        # 4. Delete & Cleanup Workspace
        canonical_path = record.canonical_path
        deleted = repo_service.delete_repository(record.repository_id)
        assert deleted is True
        assert not Path(canonical_path).exists()
