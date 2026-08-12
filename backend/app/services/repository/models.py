"""
Repository Domain Models & Lifecycle Enum.

LIFECYCLE STATES:
- REGISTERED: Path validated and registered in RepoPilot, indexing pending.
- INDEXING: Scanning, parsing, chunking, and embedding generation in progress.
- READY: Repository indexing completed successfully; ready for Q&A queries.
- FAILED: Indexing encountered an unrecoverable error.
- STALE: Files changed or deleted since last successful indexing.
"""

from enum import Enum
from pydantic import BaseModel, Field


class RepositoryStatus(str, Enum):
    REGISTERED = "registered"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"


class RepositoryRecord(BaseModel):
    """
    Persisted metadata record for a registered repository.
    """

    repository_id: str
    canonical_path: str
    display_name: str
    status: RepositoryStatus = RepositoryStatus.REGISTERED
    created_at: str
    updated_at: str
    last_indexed_at: str | None = None
    indexed_file_count: int = 0
    indexed_chunk_count: int = 0
    embedding_enabled: bool = False
    error_message: str | None = None


class IndexingSummary(BaseModel):
    """
    Summary observability report produced by indexing job.
    """

    repository_id: str
    status: RepositoryStatus
    files_discovered: int = 0
    files_parsed: int = 0
    files_skipped: int = 0
    chunks_created: int = 0
    chunks_updated: int = 0
    chunks_deleted: int = 0
    embeddings_generated: int = 0
    embeddings_reused: int = 0
    duration_ms: float = 0.0
    error_message: str | None = None


class RepositoryRegistrationRequest(BaseModel):
    """
    Request payload for POST /repositories.
    """

    path: str = Field(description="Local filesystem path to repository root directory")
