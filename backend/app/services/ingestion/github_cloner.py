"""
Public GitHub Repository Validator & Secure Cloner.

Validates public HTTPS GitHub URLs and clones repositories into isolated temporary workspaces
for the Public Demo Adaptation.

SECURITY INVARIANTS:
- Accepts ONLY https://github.com/<owner>/<repo> format.
- Blocks non-HTTPS protocols (http, git@, ssh, file).
- Rejects command-injection characters ($ | & ; ` ' " < >).
- Executes shallow clones (--depth 1) with bounded timeout.
- Ensures workspace isolation under data/clones/<repo_id>.
"""

import re
import shutil
import subprocess
from pathlib import Path

from app.services.ingestion.scanner import ScannerError

# Strict pattern for public HTTPS GitHub repo URLs
_GITHUB_URL_REGEX = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)

# Forbidden characters that might indicate command injection
_FORBIDDEN_CHARS_REGEX = re.compile(r"[\$`\|;&'\"><\s]")


def validate_github_url(url: str) -> tuple[str, str, str]:
    """
    Validate a public HTTPS GitHub repository URL.

    Args:
        url: Raw URL string from user/API request.

    Returns:
        Tuple of (canonical_url, owner, repo_name).

    Raises:
        ScannerError: If URL format is invalid, uses unsupported protocol, or contains dangerous characters.
    """
    if not url or not url.strip():
        raise ScannerError("GitHub URL cannot be empty.")

    clean_url = url.strip()

    if _FORBIDDEN_CHARS_REGEX.search(clean_url):
        raise ScannerError("Invalid GitHub URL: Contains forbidden shell or format characters.")

    if not clean_url.startswith("https://github.com/"):
        raise ScannerError(
            "Invalid repository URL: Only public HTTPS GitHub URLs (https://github.com/owner/repo) are supported."
        )

    match = _GITHUB_URL_REGEX.match(clean_url)
    if not match:
        raise ScannerError(
            "Invalid GitHub URL format. Expected 'https://github.com/owner/repository' (e.g. https://github.com/rishav579/repo-pilot)."
        )

    owner, repo = match.group(1), match.group(2)
    # Strip any trailing .git from repo name for display
    clean_repo = repo[:-4] if repo.endswith(".git") else repo
    canonical_url = f"https://github.com/{owner}/{clean_repo}"

    return canonical_url, owner, clean_repo


def clone_github_repository(github_url: str, dest_dir: Path, timeout_seconds: int = 120) -> Path:
    """
    Clone a public GitHub repository using shallow clone (--depth 1) into an isolated destination directory.

    Args:
        github_url: Validated public HTTPS GitHub URL.
        dest_dir: Destination path on local filesystem.
        timeout_seconds: Bounded execution timeout.

    Returns:
        Path to cloned repository root directory.

    Raises:
        ScannerError: If git clone fails or times out.
    """
    canonical_url, _, _ = validate_github_url(github_url)

    # Ensure parent directory exists
    dest_dir.parent.mkdir(parents=True, exist_ok=True)

    # If destination directory exists and is non-empty, remove it first
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)

    try:
        cmd = ["git", "clone", "--depth", "1", canonical_url, str(dest_dir)]
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return dest_dir
    except subprocess.TimeoutExpired:
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        raise ScannerError(
            f"Cloning GitHub repository timed out after {timeout_seconds}s for '{canonical_url}'."
        )
    except subprocess.CalledProcessError as e:
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        err_msg = e.stderr.strip() if e.stderr else str(e)
        raise ScannerError(
            f"Failed to clone GitHub repository '{canonical_url}': {err_msg}"
        )
    except Exception as e:
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        raise ScannerError(f"Unexpected error while cloning GitHub repository: {str(e)}")
