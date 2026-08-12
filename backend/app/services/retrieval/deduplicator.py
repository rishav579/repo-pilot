"""
Search Result Deduplicator — Ensures unique, deterministically ordered results.

RULE:
- Deduplicates results by `chunk.chunk_id`.
- If a chunk appears multiple times, keeps the result with the higher relevance score.
- Sorts results deterministically by `score` descending, then `chunk_id` ascending as tiebreaker.
"""

from app.services.retrieval.models import SearchResult


def deduplicate_search_results(results: list[SearchResult]) -> list[SearchResult]:
    """
    Deduplicates search results deterministically by chunk_id.

    Args:
        results: List of SearchResult objects (possibly containing duplicates).

    Returns:
        Deduplicated list sorted by relevance score DESC, then chunk_id ASC.
    """
    if not results:
        return []

    seen: dict[str, SearchResult] = {}

    for res in results:
        cid = res.chunk.chunk_id
        if cid not in seen:
            seen[cid] = res
        else:
            # Keep highest score if duplicate chunk is encountered
            if res.score > seen[cid].score:
                seen[cid] = res
            elif res.score == seen[cid].score:
                # Merge matched_keywords if score is equal
                merged_keywords = sorted(
                    list(set(seen[cid].matched_keywords + res.matched_keywords))
                )
                seen[cid].matched_keywords = merged_keywords

    deduped = list(seen.values())

    # Sort deterministically: score DESC, then chunk_id ASC as tiebreaker
    deduped.sort(key=lambda r: (-r.score, r.chunk.chunk_id))

    return deduped
