"""
SQLite Vector Storage & Embedding Cache Manager.

WHY SQLITE VECTOR STORAGE?
    1. Zero configuration — uses Python's built-in sqlite3.
    2. Model & Dimension Verification — ensures embeddings match current model & dimension.
    3. Lightweight Caching — sha256(text + model_name) cache avoids re-embedding unchanged code.
    4. Dependency-free Cosine Similarity — pure Python vector dot product & normalization.
"""

import hashlib
import json
import math
import sqlite3


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Compute cosine similarity between two vector lists.

    Cosine similarity = (v1 . v2) / (||v1|| * ||v2||)

    Returns:
        float score in range [-1.0, 1.0].
    """
    if len(v1) != len(v2) or not v1:
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot / (norm1 * norm2)


class SQLiteVectorStorage:
    """
    Manages vector storage and embedding cache in SQLite.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Create vector storage and embedding cache tables."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    vector_json TEXT NOT NULL
                );
                """
            )

    def clear(self):
        """Clear vector storage and cache."""
        with self.conn:
            self.conn.execute("DELETE FROM chunk_embeddings;")
            self.conn.execute("DELETE FROM embedding_cache;")

    def compute_cache_key(self, text: str, model_name: str) -> str:
        """Compute sha256 cache key for text and model."""
        return hashlib.sha256(f"{model_name}:{text}".encode("utf-8")).hexdigest()

    def get_cached_embedding(self, text: str, model_name: str) -> list[float] | None:
        """Get cached embedding vector if it exists."""
        ckey = self.compute_cache_key(text, model_name)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT vector_json FROM embedding_cache WHERE cache_key = ?;", (ckey,)
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["vector_json"])
            except Exception:
                return None
        return None

    def cache_embedding(self, text: str, model_name: str, vector: list[float]):
        """Cache embedding vector for a text string."""
        ckey = self.compute_cache_key(text, model_name)
        vec_json = json.dumps(vector)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache (cache_key, model_name, vector_json)
                VALUES (?, ?, ?);
                """,
                (ckey, model_name, vec_json),
            )

    def store_chunk_embedding(
        self, chunk_id: str, model_name: str, dimension: int, vector: list[float]
    ):
        """Store chunk embedding vector."""
        if len(vector) != dimension:
            raise ValueError(
                f"Vector dimension {len(vector)} does not match model dimension {dimension}"
            )
        vec_json = json.dumps(vector)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO chunk_embeddings (chunk_id, model_name, dimension, vector_json)
                VALUES (?, ?, ?, ?);
                """,
                (chunk_id, model_name, dimension, vec_json),
            )

    def get_chunk_embedding(
        self, chunk_id: str, model_name: str, dimension: int
    ) -> list[float] | None:
        """Retrieve vector for a chunk_id, verifying model and dimension."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT vector_json, model_name, dimension
            FROM chunk_embeddings
            WHERE chunk_id = ? AND model_name = ? AND dimension = ?;
            """,
            (chunk_id, model_name, dimension),
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["vector_json"])
            except Exception:
                return None
        return None

    def get_all_embeddings(
        self, model_name: str, dimension: int
    ) -> dict[str, list[float]]:
        """
        Retrieve all chunk embeddings matching the specified model and dimension.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT chunk_id, vector_json
            FROM chunk_embeddings
            WHERE model_name = ? AND dimension = ?;
            """,
            (model_name, dimension),
        )
        rows = cursor.fetchall()
        result: dict[str, list[float]] = {}
        for row in rows:
            try:
                result[row["chunk_id"]] = json.loads(row["vector_json"])
            except Exception:
                continue
        return result

    def close(self):
        """Close SQLite connection."""
        self.conn.close()
