"""
Ingestion Models — Typed data structures for scanned repositories and files.

WHY TYPED MODELS?
    Instead of passing around raw dictionaries like {"path": "...", "size": 123},
    we define proper Python classes with type annotations. This gives us:

    1. Auto-completion in editors (your IDE knows what fields exist)
    2. Validation (Pydantic checks types automatically)
    3. Clear documentation (anyone reading the code knows the data shape)
    4. API serialization (FastAPI converts these to JSON automatically)

WHAT IS Pydantic?
    Pydantic is a data validation library that comes with FastAPI.
    When you define a class that inherits from BaseModel, Pydantic:
    - Validates that the data has the right types
    - Converts types where possible (e.g., string "123" → int 123)
    - Serializes to JSON for API responses
"""

from pydantic import BaseModel


class FileInfo(BaseModel):
    """
    Represents a single file discovered during repository scanning.

    Each field stores one piece of metadata about the file:
    - relative_path: path relative to the repository root (e.g., "backend/app/main.py")
    - size_bytes: file size in bytes
    - extension: file extension including the dot (e.g., ".py"), or "" if none
    - language: detected programming language (e.g., "Python"), or None if unknown
    - is_binary: True if the file is a binary (non-text) file
    - is_excluded: True if the file matched an exclusion rule
    - exclusion_reason: why the file was excluded (e.g., "binary file", "excluded directory")
    """

    relative_path: str
    size_bytes: int
    extension: str
    language: str | None = None
    is_binary: bool = False
    is_excluded: bool = False
    exclusion_reason: str | None = None


class ScanSummary(BaseModel):
    """
    Summary of a repository scan — returned by the scan API endpoint.

    This gives a high-level overview without listing every single file,
    which is useful for quick checks and for the frontend to display.
    """

    repository_path: str
    total_files_discovered: int
    source_files: int
    excluded_files: int
    binary_files: int
    languages: dict[str, int]  # e.g., {"Python": 5, "Markdown": 3}
    total_size_bytes: int
    source_size_bytes: int


class ScanResult(BaseModel):
    """
    Full result of a repository scan — includes the summary plus all file details.

    This is the complete output of the scanner. The summary is for quick overview,
    and the files list contains every discovered file with its metadata.
    """

    summary: ScanSummary
    files: list[FileInfo]
