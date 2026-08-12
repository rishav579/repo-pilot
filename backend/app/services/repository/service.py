"""
Repository Ingestion & Incremental Indexing Service.

ORCHESTRATION PIPELINE:
1. Validate & Canonicalize Path (`validate_repository_path`)
2. Register Repository Record in Database
3. Scan Files (`scan_repository`)
4. Parse AST Structure (`parse_repository`)
5. Chunk Code (`chunk_parsed_file`) with repository_id isolation
6. Incremental Hashing (Skip unchanged files, update changed files, purge deleted files)
7. Index in FTS5 (`SQLiteFTSIndex`) & Vectors (`SQLiteVectorStorage`)
8. Update Lifecycle Status (`REGISTERED` -> `INDEXING` -> `READY` / `FAILED`)
"""

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from app.services.indexing.chunker import chunk_parsed_file
from app.services.indexing.sqlite_fts import SQLiteFTSIndex
from app.services.indexing.sqlite_vector import SQLiteVectorStorage
from app.services.ingestion.scanner import ScannerError, scan_repository, validate_repository_path
from app.services.parsing.parser import parse_repository
from app.services.repository.models import IndexingSummary, RepositoryRecord, RepositoryStatus
from app.services.repository.storage import RepositoryStorage
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.embeddings.base import EmbeddingError
from app.services.retrieval.embeddings.mock import MockEmbeddingProvider
from app.services.retrieval.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.services.retrieval.models import CodeChunk


class RepositoryService:
    """
    Service layer managing repository registration, lifecycle state, incremental indexing,
    and repository content isolation.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        config: RetrievalConfig | None = None,
    ):
        self.db_path = db_path
        self.config = config or RetrievalConfig.from_env()
        self.storage = RepositoryStorage(db_path=db_path)
        self.fts_index = SQLiteFTSIndex(db_path=db_path)
        self.vector_storage = SQLiteVectorStorage(db_path=db_path)

        # Setup Embedding Provider
        if self.config.provider_type == "openai":
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

    def register_repository(self, raw_path: str) -> RepositoryRecord:
        """
        Validates, canonicalizes, and registers a local repository.

        Args:
            raw_path: Path string to repository directory.

        Returns:
            RepositoryRecord instance.
        """
        validated_path = validate_repository_path(raw_path)
        canonical = str(validated_path.resolve()).replace("\\", "/")

        # Check if already registered
        existing = self.storage.get_repository_by_path(canonical)
        if existing:
            return existing

        # Generate stable repository_id
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
        )
        self.storage.save_repository(record)
        return record

    def get_repository(self, repository_id_or_path: str) -> RepositoryRecord | None:
        """Fetch repository by ID or path."""
        rec = self.storage.get_repository(repository_id_or_path)
        if rec:
            return rec
        # Try path canonicalization lookup
        try:
            canonical = str(Path(repository_id_or_path).resolve()).replace("\\", "/")
            return self.storage.get_repository_by_path(canonical)
        except Exception:
            return None

    def list_repositories(self) -> list[RepositoryRecord]:
        """List all registered repositories."""
        return self.storage.list_repositories()

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
