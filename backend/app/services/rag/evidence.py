"""
Evidence Selector — Filters, deduplicates, and formats candidate search results for RAG context.

RESPONSIBILITIES:
- Filters out search results below `min_relevance_score`.
- Limits evidence to `max_evidence_chunks`.
- Deduplicates chunk IDs deterministically.
- Assigns 1-indexed reference numbers [1], [2], ... for precise model citations.
"""

from app.services.rag.models import RetrievedEvidence
from app.services.retrieval.models import SearchResult


class EvidenceSelector:
    """
    Filters and selects high-value evidence chunks for context assembly.
    """

    def __init__(self, min_relevance_score: float = 0.01, max_evidence_chunks: int = 8):
        self.min_relevance_score = min_relevance_score
        self.max_evidence_chunks = max_evidence_chunks

    def select_evidence(self, search_results: list[SearchResult]) -> list[RetrievedEvidence]:
        """
        Selects evidence chunks meeting relevance and limit constraints.

        Args:
            search_results: Raw list of SearchResult objects from retrieval layer.

        Returns:
            List of 1-indexed RetrievedEvidence objects.
        """
        if not search_results:
            return []

        # Filter results meeting score threshold
        filtered = [r for r in search_results if r.score >= self.min_relevance_score]
        if not filtered:
            return []

        # Deduplicate deterministically by chunk_id while keeping highest score
        seen_chunks: set[str] = set()
        selected: list[RetrievedEvidence] = []

        # Ensure sorted deterministically: score DESC, chunk_id ASC
        sorted_results = sorted(filtered, key=lambda r: (-r.score, r.chunk.chunk_id))

        idx = 1
        for res in sorted_results:
            cid = res.chunk.chunk_id
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                selected.append(
                    RetrievedEvidence(
                        chunk=res.chunk,
                        score=res.score,
                        score_type=res.score_type,
                        index_number=idx,
                    )
                )
                idx += 1
                if len(selected) >= self.max_evidence_chunks:
                    break

        return selected
