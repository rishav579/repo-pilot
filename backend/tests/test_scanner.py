"""
Tests for the Repository Scanner.

HOW TESTING WORKS:
    - Each function starting with "test_" is a test case
    - pytest discovers and runs them automatically
    - We use "fixtures" (functions decorated with @pytest.fixture)
      to set up temporary test data that is cleaned up automatically
    - The tmp_path fixture (built into pytest) gives us a fresh
      temporary directory for each test

RUN TESTS:
    cd backend
    python -m pytest tests/ -v

    -v = verbose (shows each test name and result)
"""

import os

import pytest

from app.services.ingestion.scanner import (
    ScannerError,
    detect_language,
    is_binary_file,
    is_excluded_directory,
    is_excluded_file,
    scan_file,
    scan_repository,
    validate_repository_path,
)


# ============================================================
# Fixtures — reusable test setup
# ============================================================

# ============================================================
# Tests: Path Validation
# ============================================================

class TestValidateRepositoryPath:
    """Tests for the validate_repository_path function."""

    def test_valid_directory(self, tmp_path):
        """A real directory should pass validation."""
        result = validate_repository_path(str(tmp_path))
        assert result.is_dir()

    def test_missing_path(self):
        """A non-existent path should raise ScannerError."""
        with pytest.raises(ScannerError, match="does not exist"):
            validate_repository_path("/this/path/does/not/exist")

    def test_file_not_directory(self, tmp_path):
        """A file path (not a directory) should raise ScannerError."""
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("hello")
        with pytest.raises(ScannerError, match="not a directory"):
            validate_repository_path(str(file_path))

    def test_require_git_with_git_dir(self, tmp_path):
        """A directory with .git/ should pass when require_git=True."""
        (tmp_path / ".git").mkdir()
        result = validate_repository_path(str(tmp_path), require_git=True)
        assert result.is_dir()

    def test_require_git_without_git_dir(self, tmp_path):
        """A directory without .git/ should fail when require_git=True."""
        with pytest.raises(ScannerError, match="Not a Git repository"):
            validate_repository_path(str(tmp_path), require_git=True)


# ============================================================
# Tests: Exclusion Rules
# ============================================================

class TestExclusionRules:
    """Tests for directory and file exclusion functions."""

    def test_excluded_directories(self):
        """Known excluded directory names should be detected."""
        assert is_excluded_directory("node_modules") is True
        assert is_excluded_directory("__pycache__") is True
        assert is_excluded_directory(".git") is True
        assert is_excluded_directory(".venv") is True
        assert is_excluded_directory("dist") is True

    def test_directory_suffix_excluded(self):
        """Directories matching excluded suffixes like *.egg-info should be detected."""
        assert is_excluded_directory("mypackage.egg-info") is True
        assert is_excluded_directory("repo_pilot.dist-info") is True

    def test_non_excluded_directories(self):
        """Regular directory names should NOT be excluded."""
        assert is_excluded_directory("src") is False
        assert is_excluded_directory("app") is False
        assert is_excluded_directory("tests") is False
        assert is_excluded_directory("backend") is False

    def test_excluded_files(self):
        """Known excluded filenames should be detected."""
        assert is_excluded_file("package-lock.json") is True
        assert is_excluded_file("yarn.lock") is True
        assert is_excluded_file(".DS_Store") is True

    def test_non_excluded_files(self):
        """Regular filenames should NOT be excluded."""
        assert is_excluded_file("main.py") is False
        assert is_excluded_file("package.json") is False
        assert is_excluded_file("README.md") is False


# ============================================================
# Tests: Binary File Detection
# ============================================================

class TestBinaryFileDetection:
    """Tests for binary file detection by extension."""

    def test_binary_extensions(self):
        """Known binary extensions should be detected."""
        assert is_binary_file(".png") is True
        assert is_binary_file(".jpg") is True
        assert is_binary_file(".exe") is True
        assert is_binary_file(".pyc") is True
        assert is_binary_file(".zip") is True
        assert is_binary_file(".pdf") is True
        assert is_binary_file(".woff2") is True

    def test_source_extensions_are_not_binary(self):
        """Source code extensions should NOT be detected as binary."""
        assert is_binary_file(".py") is False
        assert is_binary_file(".js") is False
        assert is_binary_file(".ts") is False
        assert is_binary_file(".html") is False
        assert is_binary_file(".css") is False
        assert is_binary_file(".md") is False

    def test_case_insensitive(self):
        """Extension detection should be case-insensitive."""
        assert is_binary_file(".PNG") is True
        assert is_binary_file(".Jpg") is True


# ============================================================
# Tests: Language Detection
# ============================================================

class TestLanguageDetection:
    """Tests for programming language detection by extension."""

    def test_known_languages(self):
        """Known extensions should map to their language names."""
        assert detect_language(".py") == "Python"
        assert detect_language(".js") == "JavaScript"
        assert detect_language(".ts") == "TypeScript"
        assert detect_language(".tsx") == "TypeScript"
        assert detect_language(".java") == "Java"
        assert detect_language(".rs") == "Rust"
        assert detect_language(".go") == "Go"
        assert detect_language(".md") == "Markdown"

    def test_unknown_extension(self):
        """Unknown extensions should return None."""
        assert detect_language(".xyz") is None
        assert detect_language(".custom") is None
        assert detect_language("") is None


# ============================================================
# Tests: File Metadata Extraction
# ============================================================

class TestScanFile:
    """Tests for individual file scanning."""

    def test_python_file(self, tmp_path):
        """A .py file should be detected as Python with correct metadata."""
        py_file = tmp_path / "example.py"
        py_file.write_text("print('hello')\n")

        result = scan_file(py_file, tmp_path)

        assert result.relative_path == "example.py"
        assert result.extension == ".py"
        assert result.language == "Python"
        assert result.is_binary is False
        assert result.is_excluded is False
        assert result.size_bytes > 0

    def test_binary_file(self, tmp_path):
        """A .png file should be detected as binary and excluded."""
        png_file = tmp_path / "logo.png"
        png_file.write_bytes(b"\x89PNG fake")

        result = scan_file(png_file, tmp_path)

        assert result.extension == ".png"
        assert result.is_binary is True
        assert result.is_excluded is True
        assert "binary" in result.exclusion_reason

    def test_excluded_file(self, tmp_path):
        """An excluded filename should be marked as excluded."""
        lock_file = tmp_path / "package-lock.json"
        lock_file.write_text("{}")

        result = scan_file(lock_file, tmp_path)

        assert result.is_excluded is True
        assert "excluded file" in result.exclusion_reason

    def test_subdirectory_file(self, tmp_path):
        """Files in subdirectories should have correct relative paths."""
        sub = tmp_path / "src" / "components"
        sub.mkdir(parents=True)
        ts_file = sub / "Button.tsx"
        ts_file.write_text("export const Button = () => <button/>;\n")

        result = scan_file(ts_file, tmp_path)

        assert result.relative_path == "src/components/Button.tsx"
        assert result.language == "TypeScript"

    def test_broken_symlink_file(self, tmp_path):
        """A broken symlink should be marked as excluded and not crash the scanner."""
        target = tmp_path / "non_existent.txt"
        symlink = tmp_path / "broken_link.txt"
        try:
            symlink.symlink_to(target)
        except (OSError, NotImplementedError):
            # On Windows without developer mode, symlink creation might fail with OSError
            pytest.skip("Symlink creation not supported on this platform/privilege level")

        result = scan_file(symlink, tmp_path)

        assert result.is_excluded is True
        assert "broken symlink" in result.exclusion_reason

    def test_non_regular_file(self, tmp_path, monkeypatch):
        """Non-regular files (e.g. FIFOs, sockets) should be marked as excluded."""
        dummy_file = tmp_path / "fifo_pipe"
        dummy_file.write_text("fifo data")

        # Simulate is_file() returning False (as it would for FIFOs, sockets, etc.)
        monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
        monkeypatch.setattr("pathlib.Path.is_symlink", lambda self: False)

        result = scan_file(dummy_file, tmp_path)

        assert result.is_excluded is True
        assert "non-regular file" in result.exclusion_reason


# ============================================================
# Tests: Full Repository Scanning
# ============================================================

class TestScanRepository:
    """Tests for the full repository scanning pipeline."""

    def test_scan_valid_repository(self, sample_repo):
        """Scanning a valid repo should discover files and produce a summary."""
        result = scan_repository(str(sample_repo))

        # Should have discovered files
        assert result.summary.total_files_discovered > 0
        assert result.summary.source_files > 0
        assert result.summary.excluded_files > 0

        # Should have detected languages
        assert "Python" in result.summary.languages
        assert "Markdown" in result.summary.languages

        # Binary file (image.png) should be counted
        assert result.summary.binary_files >= 1

        # Sizes should be positive
        assert result.summary.total_size_bytes > 0
        assert result.summary.source_size_bytes > 0

    def test_node_modules_excluded(self, sample_repo):
        """Files inside node_modules/ should NOT appear in the file list."""
        result = scan_repository(str(sample_repo))

        # No file should have a path starting with "node_modules/"
        node_files = [
            f for f in result.files
            if f.relative_path.startswith("node_modules/")
        ]
        assert len(node_files) == 0

    def test_git_directory_excluded(self, sample_repo):
        """Files inside .git/ should NOT appear in the file list."""
        result = scan_repository(str(sample_repo))

        git_files = [
            f for f in result.files
            if f.relative_path.startswith(".git/")
        ]
        assert len(git_files) == 0

    def test_missing_path_raises_error(self):
        """Scanning a non-existent path should raise ScannerError."""
        with pytest.raises(ScannerError):
            scan_repository("/this/does/not/exist")

    def test_scan_with_require_git(self, sample_repo):
        """Scanning with require_git=True should work when .git/ exists."""
        result = scan_repository(str(sample_repo), require_git=True)
        assert result.summary.total_files_discovered > 0

    def test_oversized_file_excluded(self, sample_repo):
        """Files larger than MAX_FILE_SIZE_BYTES should be excluded."""
        result = scan_repository(str(sample_repo))

        big_files = [
            f for f in result.files
            if f.relative_path == "big_file.py"
        ]
        assert len(big_files) == 1
        assert big_files[0].is_excluded is True
        assert "too large" in big_files[0].exclusion_reason

    def test_empty_directory(self, tmp_path):
        """Scanning an empty directory should return zero files."""
        result = scan_repository(str(tmp_path))

        assert result.summary.total_files_discovered == 0
        assert result.summary.source_files == 0
        assert len(result.files) == 0
