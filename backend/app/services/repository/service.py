"""
Repository Ingestion & Incremental Indexing Service.

ORCHESTRATION PIPELINE:
1. Validate Local Path or Public GitHub HTTPS URL
2. Register Repository Record in Database (Local or Cloned Workspace)
3. Scan Files (`scan_repository`)
4. Parse AST Structure (`parse_repository`)
5. Chunk Code (`chunk_parsed_file`) with repository_id isolation
6. Incremental Hashing (Skip unchanged files, update changed files, purge deleted files)
7. Index in FTS5 (`SQLiteFTSIndex`) & Vectors (`SQLiteVectorStorage`)
8. Update Lifecycle Status (`REGISTERED` -> `INDEXING` -> `READY` / `FAILED`)
"""

import hashlib
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.indexing.sqlite_vector import SQLiteVectorStorage
from app.services.ingestion.github_cloner import clone_github_repository, validate_github_url
from app.services.ingestion.scanner import ScannerError, scan_repository, validate_repository_path
from app.services.parsing.parser import parse_repository
from app.services.repository.models import IndexingSummary, RepositoryRecord, RepositoryStatus
from app.services.repository.storage import RepositoryStorage
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.embeddings.base import EmbeddingError
from app.services.retrieval.embeddings.fastembed import FastEmbedEmbeddingProvider
from app.services.retrieval.embeddings.mock import MockEmbeddingProvider
from app.services.retrieval.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.services.retrieval.models import CodeChunk


class RepositoryService:
    """
    Service layer managing repository registration (local filesystem or public GitHub URLs),
    lifecycle state, incremental indexing, and content isolation.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        config: RetrievalConfig | None = None,
        clones_dir: str | Path | None = None,
    ):
        self.db_path = db_path
        self.config = config or RetrievalConfig.from_env()
        self.storage = RepositoryStorage(db_path=db_path)
        self.fts_index = SQLiteFTSIndex(db_path=db_path)
        self.vector_storage = SQLiteVectorStorage(db_path=db_path)

        # Default clones workspace directory
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.clones_dir = Path(clones_dir) if clones_dir else base_dir / "data" / "clones"

        # Setup Embedding Provider
        if self.config.provider_type == "fastembed":
            self.embedding_provider = FastEmbedEmbeddingProvider(
                model_name=self.config.model_name,
                dimension=self.config.dimension,
            )
        elif self.config.provider_type == "openai":
            self.embedding_provider = OpenAICompatibleEmbeddingProvider(
                api_key=self.config.api_key,
                model_name=self.config.model_name,
                dimension=self.config.dimension,
                api_base=self.config.api_base,
            )
        else:
            self.embedding_provider = MockEmbeddingProvider(
                model_name=self.config.model_name,
                dimension=self.config.dimension,
            )

    def register_repository(
        self,
        path: str | None = None,
        github_url: str | None = None,
    ) -> RepositoryRecord:
        """
        Validates and registers a local directory path OR a public GitHub HTTPS URL.

        Args:
            path: Local filesystem path string.
            github_url: Public HTTPS GitHub repository URL string.

        Returns:
            RepositoryRecord instance.
        """
        if github_url and github_url.strip():
            return self._register_github_repository(github_url.strip())
        elif path and path.strip():
            return self._register_local_repository(path.strip())
        else:
            raise ScannerError("Either 'path' or 'github_url' must be provided for repository registration.")

    def _register_local_repository(self, raw_path: str) -> RepositoryRecord:
        """Register a local filesystem repository."""
        validated_path = validate_repository_path(raw_path)
        canonical = str(validated_path.resolve()).replace("\\", "/")

        # Check if already registered
        existing = self.storage.get_repository_by_path(canonical)
        if existing:
            return existing

        path_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        repo_id = f"repo-{path_hash}"
        display_name = validated_path.name or "repository"
        now_str = datetime.now(timezone.utc).isoformat()

        record = RepositoryRecord(
            repository_id=repo_id,
            canonical_path=canonical,
            display_name=display_name,
            status=RepositoryStatus.REGISTERED,
            created_at=now_str,
            updated_at=now_str,
            embedding_enabled=self.config.semantic_enabled,
            source_type="local",
        )
        self.storage.save_repository(record)
        return record

    def _register_github_repository(self, raw_github_url: str) -> RepositoryRecord:
        """Validate, clone, and register a public GitHub HTTPS repository."""
        canonical_url, owner, repo_name = validate_github_url(raw_github_url)

        # Check if already registered by URL
        existing = self.storage.get_repository_by_github_url(canonical_url)
        if existing and Path(existing.canonical_path).exists():
            return existing

        url_hash = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:12]
        repo_id = f"repo-gh-{url_hash}"
        dest_dir = self.clones_dir / repo_id

        # Execute shallow clone into isolated destination directory
        cloned_path = clone_github_repository(canonical_url, dest_dir)
        canonical_local = str(cloned_path.resolve()).replace("\\", "/")
        now_str = datetime.now(timezone.utc).isoformat()

        record = RepositoryRecord(
            repository_id=repo_id,
            canonical_path=canonical_local,
            display_name=f"{owner}/{repo_name}",
            status=RepositoryStatus.REGISTERED,
            created_at=now_str,
            updated_at=now_str,
            embedding_enabled=self.config.semantic_enabled,
            source_type="github",
            github_url=canonical_url,
        )
        self.storage.save_repository(record)
        return record

    def get_repository(self, repository_id_or_path: str) -> RepositoryRecord | None:
        """Fetch repository by ID, local path, or GitHub URL."""
        rec = self.storage.get_repository(repository_id_or_path)
        if rec:
            return rec
        try:
            canonical = str(Path(repository_id_or_path).resolve()).replace("\\", "/")
            rec_path = self.storage.get_repository_by_path(canonical)
            if rec_path:
                return rec_path
        except Exception:
            pass
        return self.storage.get_repository_by_github_url(repository_id_or_path)

    def list_repositories(self) -> list[RepositoryRecord]:
        """List all registered repositories."""
        return self.storage.list_repositories()

    def delete_repository(self, repository_id: str) -> bool:
        """
        Delete repository record, purge index data, and cleanup cloned workspace if applicable.
        """
        record = self.storage.get_repository(repository_id)
        if not record:
            return False

        # Clear search indexes
        self.fts_index.clear(repository_id=repository_id)
        self.storage.delete_repository(repository_id)

        # Cleanup cloned workspace disk folder if GitHub source
        if record.source_type == "github" and Path(record.canonical_path).exists():
            def _remove_readonly(func, path, _):
                import stat
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            try:
                shutil.rmtree(record.canonical_path, onerror=_remove_readonly)
            except Exception:
                shutil.rmtree(record.canonical_path, ignore_errors=True)

        return True

    def index_repository(
        self, repository_id: str, enable_semantic: bool | None = None
    ) -> IndexingSummary:
        """
        Orchestrates repository scanning, AST parsing, chunking, incremental hashing,
        FTS indexing, and vector embedding generation.
        """
        t_start = time.perf_counter()
        record = self.storage.get_repository(repository_id)
        if not record:
            raise ScannerError(f"Repository ID '{repository_id}' is not registered.")

        # Update status to INDEXING
        self.storage.update_status(repository_id, RepositoryStatus.INDEXING)

        should_embed = (
            enable_semantic
            if enable_semantic is not None
            else self.config.semantic_enabled
        )

        try:
            # 1. Scan Repository
            scan_res = scan_repository(record.canonical_path)
            files_discovered = scan_res.summary.total_files_discovered
            files_skipped = scan_res.summary.excluded_files

            # 2. Parse Repository
            parse_res = parse_repository(record.canonical_path)
            files_parsed = len(parse_res.files)

            # 3. Incremental Hashing & Chunking
            previous_hashes = self.storage.get_file_hashes(repository_id)
            current_hashes: dict[str, str] = {}
            all_chunks: list[CodeChunk] = []

            chunks_created = 0
            chunks_updated = 0
            chunks_deleted = 0
            embeddings_gen = 0
            embeddings_reused = 0

            repo_root = Path(parse_res.repository_path)

            for parsed_file in parse_res.files:
                rel_path = parsed_file.relative_path.replace("\\", "/")
                full_path = repo_root / parsed_file.relative_path
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    content = str(parsed_file.symbols)

                chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                current_hashes[rel_path] = chash

                # Generate chunks for parsed file
                file_chunks = chunk_parsed_file(parsed_file, repo_root)
                for chunk in file_chunks:
                    # Enforce Repository Scope Isolation
                    chunk.repository_id = repository_id
                    all_chunks.append(chunk)

                if rel_path not in previous_hashes:
                    chunks_created += len(file_chunks)
                elif previous_hashes[rel_path] != chash:
                    chunks_updated += len(file_chunks)

                # Save new/updated file hash
                self.storage.save_file_hash(repository_id, rel_path, chash)

            # Detect deleted files
            deleted_files = set(previous_hashes.keys()) - set(current_hashes.keys())
            for del_file in deleted_files:
                self.storage.delete_file_hash(repository_id, del_file)
                chunks_deleted += 1

            # 4. FTS Indexing (Scoped to repository_id)
            self.fts_index.clear(repository_id=repository_id)
            self.fts_index.index_chunks(all_chunks)

            # 5. Semantic Embedding Generation (if enabled)
            if should_embed:
                for chunk in all_chunks:
                    text = chunk.code_content
                    mname = self.embedding_provider.model_name
                    dim = self.embedding_provider.dimension

                    # Check cache
                    cached_vec = self.vector_storage.get_cached_embedding(text, mname)
                    if cached_vec and len(cached_vec) == dim:
                        self.vector_storage.store_chunk_embedding(
                            chunk.chunk_id, mname, dim, cached_vec
                        )
                        embeddings_reused += 1
                        continue

                    # Generate new embedding
                    try:
                        vec = self.embedding_provider.embed_text(text)
                        self.vector_storage.cache_embedding(text, mname, vec)
                        self.vector_storage.store_chunk_embedding(
                            chunk.chunk_id, mname, dim, vec
                        )
                        embeddings_gen += 1
                    except EmbeddingError:
                        continue

            # Update Repository Record to READY
            now_str = datetime.now(timezone.utc).isoformat()
            record.status = RepositoryStatus.READY
            record.last_indexed_at = now_str
            record.updated_at = now_str
            record.indexed_file_count = files_parsed
            record.indexed_chunk_count = len(all_chunks)
            record.embedding_enabled = should_embed
            record.error_message = None
            self.storage.save_repository(record)

            duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

            return IndexingSummary(
                repository_id=repository_id,
                status=RepositoryStatus.READY,
                files_discovered=files_discovered,
                files_parsed=files_parsed,
                files_skipped=files_skipped,
                chunks_created=chunks_created,
                chunks_updated=chunks_updated,
                chunks_deleted=chunks_deleted,
                embeddings_generated=embeddings_gen,
                embeddings_reused=embeddings_reused,
                duration_ms=duration_ms,
            )

        except Exception as e:
            err_msg = str(e)
            self.storage.update_status(repository_id, RepositoryStatus.FAILED, error_message=err_msg)
            duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return IndexingSummary(
                repository_id=repository_id,
                status=RepositoryStatus.FAILED,
                duration_ms=duration_ms,
                error_message=err_msg,
            )

    def close(self):
        """Close storage resources."""
        self.storage.close()
        self.fts_index.close()
        self.vector_storage.close()
