"""
Query Analyzer — Deterministic extraction of code-aware signals from user queries.

Extracts structured signals for code-aware reranking:
- Identifier-like tokens (snake_case, camelCase, PascalCase)
- Filename-like tokens (tokens with file extensions)
- Route-like tokens (URL path patterns like /health)
- Quoted identifiers (explicitly quoted by user)
- Normalized word tokens (for general matching)

All analysis is deterministic: same query always produces identical output.
"""

import re
from pydantic import BaseModel


class QuerySignals(BaseModel):
    """
    Structured signals extracted from a user query for code-aware reranking.
    """
    raw_query: str
    normalized_tokens: list[str] = []       # All substantive lowercased word tokens
    identifier_tokens: list[str] = []       # snake_case, camelCase, PascalCase identifiers
    filename_tokens: list[str] = []         # Tokens that look like filenames (have extensions)
    route_tokens: list[str] = []            # URL-like path tokens (e.g., /health)
    path_tokens: list[str] = []             # File-path-like tokens (e.g., backend/app/main.py)
    quoted_tokens: list[str] = []           # Tokens explicitly quoted by user


# Tokens too common to be useful for code-aware matching
_STOP_WORDS = frozenset({
    "where", "is", "the", "in", "a", "an", "how", "what", "which",
    "are", "of", "to", "for", "on", "with", "does", "do", "it", "be",
    "defined", "implemented", "show", "me", "find", "get", "can", "you",
    "this", "that", "from", "and", "or", "not", "has", "have", "been",
})

# Pattern for identifiers: snake_case, camelCase, PascalCase, UPPER_CASE
_IDENTIFIER_PATTERN = re.compile(
    r"[a-zA-Z_][a-zA-Z0-9_]*(?:_[a-zA-Z0-9_]+)+"  # snake_case / UPPER_CASE (2+ segments)
    r"|[a-z]+[A-Z][a-zA-Z0-9]*"                      # camelCase
    r"|[A-Z][a-z]+[A-Z][a-zA-Z0-9]*"                  # PascalCase with 2+ words
)

# Pattern for filenames: word.ext
_FILENAME_PATTERN = re.compile(
    r"[a-zA-Z0-9_.-]+\.(?:py|js|ts|jsx|tsx|go|rs|java|c|cpp|h|hpp|rb|md|yaml|yml|json|toml|cfg|ini|sql|html|css)"
)

# Pattern for URL routes: /path or /path/segment
_ROUTE_PATTERN = re.compile(r"/[a-zA-Z0-9_/-]+")

# Pattern for file paths: dir/dir/file.ext or dir/dir/file
_PATH_PATTERN = re.compile(
    r"[a-zA-Z0-9_./-]+/[a-zA-Z0-9_./-]+"
)

# Pattern for quoted strings
_QUOTED_PATTERN = re.compile(r'["\']([^"\']+)["\']|`([^`]+)`')


def analyze_query(query: str) -> QuerySignals:
    """
    Extract structured code-aware signals from a search query.

    Args:
        query: Normalized search query string.

    Returns:
        QuerySignals with extracted tokens categorized by type.
    """
    if not query or not query.strip():
        return QuerySignals(raw_query=query or "")

    signals = QuerySignals(raw_query=query)

    # 1. Extract quoted tokens first (highest priority — user explicitly identified these)
    for match in _QUOTED_PATTERN.finditer(query):
        quoted = match.group(1) or match.group(2)
        if quoted and quoted.strip():
            signals.quoted_tokens.append(quoted.strip())

    # 2. Extract route-like tokens (e.g., /health, /api/repos)
    for match in _ROUTE_PATTERN.finditer(query):
        route = match.group(0)
        if len(route) > 1:  # Skip bare "/"
            signals.route_tokens.append(route)

    # 3. Extract path-like tokens (e.g., backend/app/main.py)
    for match in _PATH_PATTERN.finditer(query):
        path = match.group(0)
        # Avoid duplicating routes already captured
        if not path.startswith("/") and len(path) > 3:
            signals.path_tokens.append(path)

    # 4. Extract filename-like tokens (e.g., main.py, scanner.py)
    for match in _FILENAME_PATTERN.finditer(query):
        signals.filename_tokens.append(match.group(0))

    # 5. Extract identifier-like tokens (e.g., health_check, scan_repository)
    for match in _IDENTIFIER_PATTERN.finditer(query):
        ident = match.group(0)
        # Skip if it looks like a filename (already captured)
        if "." not in ident:
            signals.identifier_tokens.append(ident)

    # 6. Extract normalized word tokens (all substantive lowercased tokens)
    word_tokens = re.findall(r"[a-zA-Z0-9_]+", query)
    signals.normalized_tokens = [
        t.lower() for t in word_tokens
        if t.lower() not in _STOP_WORDS and len(t) > 1
    ]

    # Deduplicate all lists while preserving order
    signals.quoted_tokens = _dedup_preserve_order(signals.quoted_tokens)
    signals.route_tokens = _dedup_preserve_order(signals.route_tokens)
    signals.path_tokens = _dedup_preserve_order(signals.path_tokens)
    signals.filename_tokens = _dedup_preserve_order(signals.filename_tokens)
    signals.identifier_tokens = _dedup_preserve_order(signals.identifier_tokens)
    signals.normalized_tokens = _dedup_preserve_order(signals.normalized_tokens)

    return signals


def _dedup_preserve_order(items: list[str]) -> list[str]:
    """Remove duplicates while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
