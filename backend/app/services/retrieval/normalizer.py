"""
Query Normalizer — Cleans and normalizes user search queries.

FUNCTIONS:
- Strips leading and trailing whitespace.
- Collapses repeated internal whitespace.
- Truncates queries exceeding MAX_QUERY_LENGTH (500 characters).
- Returns empty string for whitespace-only queries.
"""

import re

MAX_QUERY_LENGTH = 500


def normalize_query(raw_query: str | None) -> str:
    """
    Normalizes user search queries cleanly and deterministically.

    Args:
        raw_query: Raw input string from user or API request.

    Returns:
        Normalized query string, or empty string if invalid/empty.
    """
    if not raw_query:
        return ""

    # Strip leading and trailing whitespace
    normalized = raw_query.strip()

    if not normalized:
        return ""

    # Truncate extremely long queries to protect FTS performance and prevent buffer abuse
    if len(normalized) > MAX_QUERY_LENGTH:
        normalized = normalized[:MAX_QUERY_LENGTH].strip()

    # Collapse multiple whitespace characters into a single space
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized
