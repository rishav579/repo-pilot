"""
Repository Scanner — Discovers and catalogs files in a local repository.

This is the core of the ingestion service. It walks through a repository
directory, examines every file, and produces a structured report of what
it found.

HOW IT WORKS:
    1. Validate that the given path exists and is a directory
    2. Optionally check that it looks like a Git repository (.git/ exists)
    3. Walk through every file recursively
    4. For each file, determine:
       - Is it in an excluded directory?
       - Is it an excluded file?
       - Is it binary (based on extension)?
       - Is it too large?
       - What programming language is it?
    5. Collect all results into a ScanResult with a summary

DESIGN DECISIONS:
    - We use os.walk() for directory traversal because it's simple,
      well-documented, and handles nested directories automatically.
    - We classify files by extension (not by reading content) because
      it's fast and works for the vast majority of cases.
    - We don't read file contents at this stage — that happens in
      the parsing phase (Phase 3). Ingestion is just discovery.
"""

import os
from pathlib import Path

from app.services.ingestion.config import (
    BINARY_EXTENSIONS,
    EXCLUDED_DIR_SUFFIXES,
    EXCLUDED_DIRECTORIES,
    EXCLUDED_FILES,
    LANGUAGE_MAP,
    MAX_FILE_SIZE_BYTES,
)
from app.services.ingestion.models import FileInfo, ScanResult, ScanSummary


class ScannerError(Exception):
    """
    Raised when the scanner encounters an unrecoverable problem.

    Examples:
    - The given path does not exist
    - The given path is a file, not a directory
    """

    pass


def validate_repository_path(repo_path: str, require_git: bool = False) -> Path:
    """
    Validate that the given path is a directory (and optionally a Git repo).

    Args:
        repo_path: The path to validate (as a string).
        require_git: If True, also check that .git/ exists inside the directory.

    Returns:
        A resolved Path object pointing to the repository.

    Raises:
        ScannerError: If the path is invalid.

    WHY VALIDATE?
        If someone passes a path that doesn't exist, we want a clear error
        message — not a cryptic traceback from deep inside os.walk().
    """
    path = Path(repo_path).resolve()

    if not path.exists():
        raise ScannerError(f"Path does not exist: {path}")

    if not path.is_dir():
        raise ScannerError(f"Path is not a directory: {path}")

    if require_git:
        git_dir = path / ".git"
        if not git_dir.is_dir():
            raise ScannerError(
                f"Not a Git repository (no .git directory found): {path}"
            )

    return path


def is_excluded_directory(dir_name: str) -> bool:
    """
    Check if a directory name should be excluded from scanning.

    We check the directory NAME, not the full path. This means
    "node_modules" is excluded wherever it appears in the tree:
    - repo/node_modules/  ← excluded
    - repo/packages/frontend/node_modules/  ← also excluded

    Checks both exact directory names and directory suffixes (e.g., ".egg-info").

    Args:
        dir_name: The name of the directory (not the full path).

    Returns:
        True if the directory should be skipped.
    """
    if dir_name in EXCLUDED_DIRECTORIES:
        return True
    return any(dir_name.endswith(suffix) for suffix in EXCLUDED_DIR_SUFFIXES)


def is_excluded_file(filename: str) -> bool:
    """
    Check if a specific filename should be excluded.

    Args:
        filename: The name of the file (not the full path).

    Returns:
        True if the file should be skipped.
    """
    return filename in EXCLUDED_FILES


def is_binary_file(extension: str) -> bool:
    """
    Check if a file extension indicates a binary (non-text) file.

    We use the extension rather than reading the file content because:
    - It's much faster (no I/O needed)
    - It works correctly for 99%+ of files
    - Reading every file's content would be slow on large repos

    Args:
        extension: The file extension including the dot (e.g., ".png").

    Returns:
        True if the extension is in the binary list.
    """
    return extension.lower() in BINARY_EXTENSIONS


def detect_language(extension: str) -> str | None:
    """
    Detect the programming language based on file extension.

    Args:
        extension: The file extension including the dot (e.g., ".py").

    Returns:
        The language name (e.g., "Python"), or None if unrecognized.
    """
    return LANGUAGE_MAP.get(extension.lower())


def scan_file(file_path: Path, repo_root: Path) -> FileInfo:
    """
    Examine a single file and produce its metadata.

    This function does NOT read the file's content — it only checks:
    - The file's path, size, and extension
    - Whether it should be excluded
    - What language it likely is

    Args:
        file_path: Absolute path to the file.
        repo_root: Absolute path to the repository root (for computing relative paths).

    Returns:
        A FileInfo object with all metadata populated.
    """
    relative_path = str(file_path.relative_to(repo_root))
    # Normalize path separators to forward slashes (for consistency across OS)
    relative_path = relative_path.replace("\\", "/")

    extension = file_path.suffix.lower()  # e.g., ".py", ".ts", ""
    filename = file_path.name

    # Rule 0: Is this a regular file? (Excludes broken symlinks, sockets, FIFOs)
    try:
        if not file_path.is_file():
            is_symlink = file_path.is_symlink()
            reason = "broken symlink" if is_symlink else "non-regular file"
            return FileInfo(
                relative_path=relative_path,
                size_bytes=0,
                extension=extension,
                is_excluded=True,
                exclusion_reason=reason,
            )
    except OSError:
        return FileInfo(
            relative_path=relative_path,
            size_bytes=0,
            extension=extension,
            is_excluded=True,
            exclusion_reason="inaccessible or non-regular file",
        )

    # Get file size
    try:
        size_bytes = file_path.stat().st_size
    except OSError:
        size_bytes = 0

    # Rule 1: Is this file in the excluded files list?
    if is_excluded_file(filename):
        return FileInfo(
            relative_path=relative_path,
            size_bytes=size_bytes,
            extension=extension,
            is_excluded=True,
            exclusion_reason=f"excluded file: {filename}",
        )

    # Rule 2: Is this a binary file?
    if is_binary_file(extension):
        return FileInfo(
            relative_path=relative_path,
            size_bytes=size_bytes,
            extension=extension,
            is_binary=True,
            is_excluded=True,
            exclusion_reason=f"binary file: {extension}",
        )

    # Rule 3: Is this file too large?
    if size_bytes > MAX_FILE_SIZE_BYTES:
        return FileInfo(
            relative_path=relative_path,
            size_bytes=size_bytes,
            extension=extension,
            is_excluded=True,
            exclusion_reason=f"file too large: {size_bytes} bytes "
            f"(limit: {MAX_FILE_SIZE_BYTES})",
        )

    # File is included — detect its language
    language = detect_language(extension)

    return FileInfo(
        relative_path=relative_path,
        size_bytes=size_bytes,
        extension=extension,
        language=language,
    )


def scan_repository(repo_path: str, require_git: bool = False) -> ScanResult:
    """
    Scan an entire repository and produce a structured result.

    This is the main entry point for the ingestion service.
    It validates the path, walks the directory tree, examines each file,
    and produces a ScanResult containing both a summary and full file list.

    Args:
        repo_path: Path to the repository root directory.
        require_git: If True, verify that .git/ exists.

    Returns:
        A ScanResult with the scan summary and list of all discovered files.

    Raises:
        ScannerError: If the path is invalid.

    HOW os.walk() WORKS:
        os.walk(path) yields (dirpath, dirnames, filenames) for every
        directory in the tree. By modifying 'dirnames' in-place, we can
        prevent os.walk from descending into excluded directories.
        This is a standard Python pattern for efficient directory traversal.
    """
    repo_root = validate_repository_path(repo_path, require_git=require_git)

    all_files: list[FileInfo] = []

    # os.walk yields (current_directory, subdirectory_names, file_names)
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # IMPORTANT: Modify dirnames IN-PLACE to prevent os.walk from
        # descending into excluded directories. This is much faster than
        # letting it walk into node_modules/ and then ignoring the results.
        dirnames[:] = [
            d for d in dirnames
            if not is_excluded_directory(d)
        ]

        # Sort for consistent ordering across different operating systems
        dirnames.sort()

        # Process each file in the current directory
        for filename in sorted(filenames):
            file_path = Path(dirpath) / filename
            file_info = scan_file(file_path, repo_root)
            all_files.append(file_info)

    # Build the summary from the collected file data
    source_files = [f for f in all_files if not f.is_excluded]
    excluded_files = [f for f in all_files if f.is_excluded]
    binary_files = [f for f in all_files if f.is_binary]

    # Count files per language
    language_counts: dict[str, int] = {}
    for f in source_files:
        if f.language:
            language_counts[f.language] = language_counts.get(f.language, 0) + 1

    # Sort languages by count (most common first)
    language_counts = dict(
        sorted(language_counts.items(), key=lambda item: item[1], reverse=True)
    )

    summary = ScanSummary(
        repository_path=str(repo_root),
        total_files_discovered=len(all_files),
        source_files=len(source_files),
        excluded_files=len(excluded_files),
        binary_files=len(binary_files),
        languages=language_counts,
        total_size_bytes=sum(f.size_bytes for f in all_files),
        source_size_bytes=sum(f.size_bytes for f in source_files),
    )

    return ScanResult(summary=summary, files=all_files)
