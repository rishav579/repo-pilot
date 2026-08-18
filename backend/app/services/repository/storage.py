"""
Repository Database Storage Manager.

Manages SQLite tables for repository registration metadata, lifecycle status,
and incremental file content hashes.
"""

import sqlite3
from app.services.repository.models import RepositoryRecord, RepositoryStatus


class RepositoryStorage:
    """
    SQLite persistence for repository metadata and incremental hashing.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables and apply schema migrations safely."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    repository_id TEXT PRIMARY KEY,
                    canonical_path TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_indexed_at TIMESTAMP,
                    indexed_file_count INTEGER DEFAULT 0,
                    indexed_chunk_count INTEGER DEFAULT 0,
                    embedding_enabled INTEGER DEFAULT 0,
                    error_message TEXT,
                    source_type TEXT DEFAULT 'local',
                    github_url TEXT
                );
                """
            )

            # Ensure columns exist for upgraded SQLite databases
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(repositories);")
            cols = [r["name"] for r in cursor.fetchall()]
            if "source_type" not in cols:
                self.conn.execute("ALTER TABLE repositories ADD COLUMN source_type TEXT DEFAULT 'local';")
            if "github_url" not in cols:
                self.conn.execute("ALTER TABLE repositories ADD COLUMN github_url TEXT;")

            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_content_hashes (
                    repository_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (repository_id, relative_path)
                );
                """
            )

    def save_repository(self, record: RepositoryRecord):
        """Insert or replace a RepositoryRecord."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO repositories (
                    repository_id, canonical_path, display_name, status,
                    created_at, updated_at, last_indexed_at,
                    indexed_file_count, indexed_chunk_count,
                    embedding_enabled, error_message, source_type, github_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.repository_id,
                    record.canonical_path,
                    record.display_name,
                    record.status.value,
                    record.created_at,
                    record.updated_at,
                    record.last_indexed_at,
                    record.indexed_file_count,
                    record.indexed_chunk_count,
                    1 if record.embedding_enabled else 0,
                    record.error_message,
                    record.source_type,
                    record.github_url,
                ),
            )

    def get_repository(self, repository_id: str) -> RepositoryRecord | None:
        """Fetch repository by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM repositories WHERE repository_id = ?;", (repository_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def get_repository_by_path(self, canonical_path: str) -> RepositoryRecord | None:
        """Fetch repository by canonical path."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM repositories WHERE canonical_path = ?;", (canonical_path,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def get_repository_by_github_url(self, github_url: str) -> RepositoryRecord | None:
        """Fetch repository by normalized GitHub URL."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM repositories WHERE github_url = ?;", (github_url,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_repositories(self) -> list[RepositoryRecord]:
        """List all registered repositories."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM repositories ORDER BY created_at DESC;")
        rows = cursor.fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_status(
        self,
        repository_id: str,
        status: RepositoryStatus,
        error_message: str | None = None,
    ):
        """Update repository lifecycle status."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE repositories
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE repository_id = ?;
                """,
                (status.value, error_message, repository_id),
            )

    def delete_repository(self, repository_id: str):
        """Delete repository record and associated file hashes."""
        with self.conn:
            self.conn.execute("DELETE FROM repositories WHERE repository_id = ?;", (repository_id,))
            self.conn.execute("DELETE FROM file_content_hashes WHERE repository_id = ?;", (repository_id,))

    def get_file_hashes(self, repository_id: str) -> dict[str, str]:
        """Retrieve dictionary of relative_path -> content_hash for a repository."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT relative_path, content_hash FROM file_content_hashes WHERE repository_id = ?;",
            (repository_id,),
        )
        rows = cursor.fetchall()
        return {r["relative_path"]: r["content_hash"] for r in rows}

    def save_file_hash(self, repository_id: str, relative_path: str, content_hash: str):
        """Insert or replace file content hash."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO file_content_hashes (repository_id, relative_path, content_hash)
                VALUES (?, ?, ?);
                """,
                (repository_id, relative_path, content_hash),
            )

    def delete_file_hash(self, repository_id: str, relative_path: str):
        """Delete file content hash entry."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM file_content_hashes WHERE repository_id = ? AND relative_path = ?;",
                (repository_id, relative_path),
            )

    def _row_to_record(self, row: sqlite3.Row) -> RepositoryRecord:
        keys = row.keys()
        return RepositoryRecord(
            repository_id=row["repository_id"],
            canonical_path=row["canonical_path"],
            display_name=row["display_name"],
            status=RepositoryStatus(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_indexed_at=str(row["last_indexed_at"]) if row["last_indexed_at"] else None,
            indexed_file_count=int(row["indexed_file_count"]),
            indexed_chunk_count=int(row["indexed_chunk_count"]),
            embedding_enabled=bool(row["embedding_enabled"]),
            error_message=row["error_message"],
            source_type=str(row["source_type"]) if "source_type" in keys and row["source_type"] else "local",
            github_url=str(row["github_url"]) if "github_url" in keys and row["github_url"] else None,
        )

    def close(self):
        """Close database connection."""
        self.conn.close()
