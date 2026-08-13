"""
Code-Aware Reranker — Deterministic reranking of retrieval candidates using code-specific signals.

ARCHITECTURE:
    The reranker operates AFTER candidate retrieval and deduplication, BEFORE final top_k selection.
    It combines the existing retrieval score with deterministic code-aware signals.

    Pipeline position:
        Keyword + Semantic → candidate pool → deduplicate → CODE-AWARE RERANKER → top_k

SCORE FORMULA:
    final_score = base_relevance_normalized
                  + exact_symbol_bonus
                  + filename_bonus
                  + path_token_bonus
                  + signature_bonus
                  + docstring_bonus
                  + code_overlap_bonus
                  + route_match_bonus
                  + symbol_type_bonus

DETERMINISM:
    Same query + same candidates = identical ordering. No randomness, no ML inference.

SCORE SEMANTICS:
    All component scores are >= 0. Higher final_score = more relevant.
    base_relevance_normalized: original score mapped to [0, 1] range.
    Bonuses: additive [0, weight] contributions.

WHY DETERMINISTIC RERANKING:
    1. Zero external dependencies — no API calls, no model downloads.
    2. Fully reproducible — same inputs always produce same outputs.
    3. Instant — operates on small candidate pools (typically 20-60 items).
    4. Debuggable — every score component is inspectable.
    5. Upgradable — can be replaced with learned reranking in the future.
"""

from pydantic import BaseModel

from app.services.retrieval.models import SearchResult
from app.services.retrieval.query_analyzer import QuerySignals, analyze_query


class CodeAwareRerankerConfig(BaseModel):
    """
    Configuration for code-aware reranking weights.

    Each weight controls the maximum additive bonus for that signal.
    Weights are documented with their rationale.

    DESIGN RATIONALE FOR DEFAULT WEIGHTS:
    - exact_symbol_weight (0.50): Exact symbol name matches are the strongest signal.
      If a user asks about "health_check" and a chunk's symbol IS "health_check",
      that chunk is almost certainly the answer.
    - filename_weight (0.30): Filename matches are strong but less precise than symbol matches.
      Multiple chunks come from the same file, so this boosts all of them equally.
    - path_token_weight (0.15): Path components provide moderate directional signal.
      e.g., query mentioning "retrieval" boosts chunks from retrieval/ directory.
    - signature_weight (0.20): Function signatures contain parameter names and types
      that often match query terms precisely.
    - docstring_weight (0.30): Docstrings describe purpose in natural language,
      providing strong semantic overlap with user questions when multiple tokens match.
    - code_overlap_weight (0.10): Raw code content overlap is a weak but broad signal.
      Prevents over-reliance on metadata when code content is uniquely relevant.
    - route_match_weight (0.45): API route matches are very strong for endpoint queries.
      e.g., query "/health" matching @app.get("/health") is near-certain relevance.
    - symbol_type_weight (0.10): Mild bonus for matching symbol types to query intent.
      e.g., "which class" query slightly prefers class chunks.
    - candidate_pool_multiplier (3): Fetch N*top_k candidates for reranking pool.
    - min_candidate_pool (20): Minimum candidate pool size.
    """

    exact_symbol_weight: float = 0.50
    filename_weight: float = 0.30
    path_token_weight: float = 0.15
    signature_weight: float = 0.20
    docstring_weight: float = 0.30
    code_overlap_weight: float = 0.10
    route_match_weight: float = 0.45
    symbol_type_weight: float = 0.10
    candidate_pool_multiplier: int = 3
    min_candidate_pool: int = 20


class RerankedResult(BaseModel):
    """
    A search result annotated with reranking score breakdown.
    """
    result: SearchResult
    final_score: float
    base_relevance: float
    exact_symbol_bonus: float = 0.0
    filename_bonus: float = 0.0
    path_token_bonus: float = 0.0
    signature_bonus: float = 0.0
    docstring_bonus: float = 0.0
    code_overlap_bonus: float = 0.0
    route_match_bonus: float = 0.0
    symbol_type_bonus: float = 0.0


class CodeAwareReranker:
    """
    Deterministic code-aware reranker for retrieval candidates.

    Operates on a list of SearchResult objects and returns them reordered
    based on combined retrieval score + code-aware signals.
    """

    def __init__(self, config: CodeAwareRerankerConfig | None = None):
        self.config = config or CodeAwareRerankerConfig()

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """
        Rerank candidate search results using code-aware signals.

        Args:
            query: The user's search query (already normalized).
            candidates: List of SearchResult candidates from retrieval.
            top_k: Maximum results to return after reranking.

        Returns:
            Reranked list of SearchResult objects, trimmed to top_k.
        """
        if not candidates:
            return []

        if not query or not query.strip():
            return candidates[:top_k]

        # Analyze query to extract structured signals
        signals = analyze_query(query)

        # Compute score range for normalization
        scores = [r.score for r in candidates]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        # Score each candidate
        reranked: list[RerankedResult] = []
        for result in candidates:
            rr = self._score_candidate(result, signals, min_score, score_range)
            reranked.append(rr)

        # Sort deterministically: final_score DESC, then chunk_id ASC as tiebreaker
        reranked.sort(key=lambda r: (-r.final_score, r.result.chunk.chunk_id))

        # Return SearchResult objects with updated scores
        output: list[SearchResult] = []
        for rr in reranked[:top_k]:
            output.append(
                SearchResult(
                    chunk=rr.result.chunk,
                    score=round(rr.final_score, 6),
                    score_type="reranked",
                    matched_keywords=rr.result.matched_keywords,
                )
            )

        return output

    def _score_candidate(
        self,
        result: SearchResult,
        signals: QuerySignals,
        min_score: float,
        score_range: float,
    ) -> RerankedResult:
        """
        Compute reranking score for a single candidate.
        """
        chunk = result.chunk
        cfg = self.config

        # 1. Normalize base retrieval score to [0, 0.5] using ratio normalization.
        # Ratio normalization (score / max_score) preserves proportional differences:
        # - A candidate with score 5.0 when max is 6.0 gets 0.417, not 0.0
        # - This prevents artificial amplification of small score differences
        # - Code-aware bonuses (max total ~2.1) can meaningfully override
        #   proportional retrieval score differences
        max_score = score_range + min_score  # reconstruct max_score
        if max_score > 0:
            base_relevance = (result.score / max_score) * 0.5
        else:
            base_relevance = 0.25

        # 2. Exact symbol name match
        exact_symbol_bonus = self._compute_symbol_bonus(chunk.symbol_name, signals, cfg)

        # 3. Filename match
        filename_bonus = self._compute_filename_bonus(chunk.relative_path, signals, cfg)

        # 4. Path token match
        path_token_bonus = self._compute_path_token_bonus(chunk.relative_path, signals, cfg)

        # 5. Signature match
        signature_bonus = self._compute_signature_bonus(chunk.signature, signals, cfg)

        # 6. Docstring match
        docstring_bonus = self._compute_docstring_bonus(chunk.docstring, signals, cfg)

        # 7. Code content overlap
        code_overlap_bonus = self._compute_code_overlap_bonus(chunk.code_content, signals, cfg)

        # 8. Route match
        route_match_bonus = self._compute_route_match_bonus(chunk.code_content, signals, cfg)

        # 9. Symbol type relevance
        symbol_type_bonus = self._compute_symbol_type_bonus(chunk.symbol_kind, signals, cfg)

        final_score = (
            base_relevance
            + exact_symbol_bonus
            + filename_bonus
            + path_token_bonus
            + signature_bonus
            + docstring_bonus
            + code_overlap_bonus
            + route_match_bonus
            + symbol_type_bonus
        )

        return RerankedResult(
            result=result,
            final_score=round(final_score, 6),
            base_relevance=round(base_relevance, 6),
            exact_symbol_bonus=round(exact_symbol_bonus, 6),
            filename_bonus=round(filename_bonus, 6),
            path_token_bonus=round(path_token_bonus, 6),
            signature_bonus=round(signature_bonus, 6),
            docstring_bonus=round(docstring_bonus, 6),
            code_overlap_bonus=round(code_overlap_bonus, 6),
            route_match_bonus=round(route_match_bonus, 6),
            symbol_type_bonus=round(symbol_type_bonus, 6),
        )

    @staticmethod
    def _compute_symbol_bonus(
        symbol_name: str | None,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute exact symbol name match bonus.

        Full weight for exact match (case-insensitive).
        Half weight for substring containment.
        """
        if not symbol_name:
            return 0.0

        sym_lower = symbol_name.lower()

        # Check against identifier tokens and quoted tokens (strongest signals)
        all_candidates = signals.identifier_tokens + signals.quoted_tokens
        for token in all_candidates:
            if token.lower() == sym_lower:
                return cfg.exact_symbol_weight  # Full bonus for exact match

        # Check normalized tokens for exact match
        for token in signals.normalized_tokens:
            if token == sym_lower:
                return cfg.exact_symbol_weight  # Full bonus

        # Partial match: any identifier token is a substring of symbol name
        for token in all_candidates:
            if token.lower() in sym_lower or sym_lower in token.lower():
                return cfg.exact_symbol_weight * 0.5

        # Weak match: normalized tokens appearing in symbol name
        matched_count = sum(1 for t in signals.normalized_tokens if t in sym_lower)
        if matched_count > 0:
            ratio = min(matched_count / max(len(signals.normalized_tokens), 1), 1.0)
            return cfg.exact_symbol_weight * 0.3 * ratio

        return 0.0

    @staticmethod
    def _compute_filename_bonus(
        relative_path: str,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute filename match bonus.

        Full weight if a filename token exactly matches the file's basename.
        Half weight for partial match.
        """
        if not relative_path:
            return 0.0

        # Extract basename from path
        path_lower = relative_path.lower().replace("\\", "/")
        parts = path_lower.rsplit("/", 1)
        basename = parts[-1] if parts else path_lower

        for fn_token in signals.filename_tokens:
            if fn_token.lower() == basename:
                return cfg.filename_weight  # Exact filename match
            if fn_token.lower() in basename or basename in fn_token.lower():
                return cfg.filename_weight * 0.5

        # Check if any normalized token matches the filename stem
        stem = basename.rsplit(".", 1)[0] if "." in basename else basename
        for token in signals.normalized_tokens:
            if token == stem:
                return cfg.filename_weight * 0.4

        return 0.0

    @staticmethod
    def _compute_path_token_bonus(
        relative_path: str,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute path token overlap bonus.

        Rewards chunks whose file path contains query terms.
        """
        if not relative_path:
            return 0.0

        path_lower = relative_path.lower().replace("\\", "/")

        # Check explicit path tokens from query
        for path_token in signals.path_tokens:
            if path_token.lower() in path_lower or path_lower.endswith(path_token.lower()):
                return cfg.path_token_weight  # Full match

        # Check normalized word tokens against path components
        path_parts = set(path_lower.replace("/", " ").replace(".", " ").replace("_", " ").split())
        if not path_parts:
            return 0.0

        matched = sum(1 for t in signals.normalized_tokens if t in path_parts)
        if matched > 0:
            ratio = min(matched / max(len(signals.normalized_tokens), 1), 1.0)
            return cfg.path_token_weight * ratio * 0.6

        return 0.0

    @staticmethod
    def _compute_signature_bonus(
        signature: str | None,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute function/method signature match bonus.

        Rewards chunks whose signatures contain query terms.
        """
        if not signature:
            return 0.0

        sig_lower = signature.lower()

        # Check identifier tokens against signature
        for ident in signals.identifier_tokens:
            if ident.lower() in sig_lower:
                return cfg.signature_weight  # Strong signal

        # Check quoted tokens
        for quoted in signals.quoted_tokens:
            if quoted.lower() in sig_lower:
                return cfg.signature_weight

        # Check normalized tokens
        matched = sum(1 for t in signals.normalized_tokens if t in sig_lower)
        if matched > 0:
            ratio = min(matched / max(len(signals.normalized_tokens), 1), 1.0)
            return cfg.signature_weight * ratio * 0.5

        return 0.0

    @staticmethod
    def _compute_docstring_bonus(
        docstring: str | None,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute docstring match bonus.

        Rewards chunks whose docstrings contain query terms.
        """
        if not docstring:
            return 0.0

        doc_lower = docstring.lower()

        # Check identifier tokens
        for ident in signals.identifier_tokens:
            if ident.lower() in doc_lower:
                return cfg.docstring_weight

        # Check normalized tokens — when most/all query tokens appear in the docstring,
        # this is a strong signal that the chunk describes what the user is asking about
        matched = sum(1 for t in signals.normalized_tokens if t in doc_lower)
        if matched > 0:
            ratio = min(matched / max(len(signals.normalized_tokens), 1), 1.0)
            return cfg.docstring_weight * ratio

        return 0.0

    @staticmethod
    def _compute_code_overlap_bonus(
        code_content: str,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute code content token overlap bonus.

        Weak but broad signal. Prevents over-reliance on metadata.
        """
        if not code_content:
            return 0.0

        code_lower = code_content.lower()

        # Check identifier tokens in code (strongest code overlap signal)
        for ident in signals.identifier_tokens:
            if ident.lower() in code_lower:
                return cfg.code_overlap_weight

        # Check quoted tokens
        for quoted in signals.quoted_tokens:
            if quoted.lower() in code_lower:
                return cfg.code_overlap_weight

        # Check normalized tokens
        matched = sum(1 for t in signals.normalized_tokens if t in code_lower)
        if matched > 0:
            ratio = min(matched / max(len(signals.normalized_tokens), 1), 1.0)
            return cfg.code_overlap_weight * ratio * 0.5

        return 0.0

    @staticmethod
    def _compute_route_match_bonus(
        code_content: str,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute API route match bonus.

        Strong signal when code contains an API route decorator matching query routes.
        e.g., query "/health" matching @app.get("/health") in code.
        """
        if not code_content or not signals.route_tokens:
            return 0.0

        code_lower = code_content.lower()

        for route in signals.route_tokens:
            # Check for exact route string in code (e.g., "/health" in @app.get("/health"))
            route_lower = route.lower()
            if route_lower in code_lower:
                return cfg.route_match_weight  # Strong match

            # Check for route as a quoted string in code
            if f'"{route_lower}"' in code_lower or f"'{route_lower}'" in code_lower:
                return cfg.route_match_weight

        return 0.0

    @staticmethod
    def _compute_symbol_type_bonus(
        symbol_kind: str | None,
        signals: QuerySignals,
        cfg: CodeAwareRerankerConfig,
    ) -> float:
        """
        Compute symbol type relevance bonus.

        Mild bonus when the query's intent matches the symbol's type.
        e.g., "which class" query slightly prefers class chunks.
        """
        if not symbol_kind:
            return 0.0

        kind_lower = symbol_kind.lower()
        query_lower = signals.raw_query.lower()

        # Map query intent words to symbol kinds
        intent_map = {
            "function": ["function", "method"],
            "class": ["class"],
            "method": ["method", "function"],
            "endpoint": ["function", "method"],
            "api": ["function", "method"],
            "decorator": ["function", "method"],
        }

        for intent_word, matching_kinds in intent_map.items():
            if intent_word in query_lower:
                if kind_lower in matching_kinds:
                    return cfg.symbol_type_weight

        return 0.0
