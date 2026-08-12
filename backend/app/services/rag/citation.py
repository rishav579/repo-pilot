"""
Citation Parser & Validator — Extracts and validates citation references against supplied evidence.

VALIDATION CONTRACT:
- Extracts bracketed citation references like `[1]`, `[2]` from generated LLM text.
- Validates that every extracted citation index maps to an actual supplied `ContextBlock`.
- If an index does not exist in the context supplied to the model, marks `is_valid=False`.
- Prevents hallucinated or unverified file citations from reaching the client.
"""

import re
from app.services.rag.models import Citation, ContextBlock


class CitationValidator:
    """
    Parses and validates citations against context blocks.
    """

    @staticmethod
    def extract_and_validate(
        generated_text: str, context_blocks: list[ContextBlock]
    ) -> list[Citation]:
        """
        Parses citation index numbers [1], [2] from text and validates against context blocks.

        Args:
            generated_text: LLM generated answer text.
            context_blocks: List of ContextBlock objects supplied in prompt.

        Returns:
            List of validated Citation objects.
        """
        if not generated_text or not context_blocks:
            return []

        # Map index_number -> ContextBlock
        block_map: dict[int, ContextBlock] = {b.index_number: b for b in context_blocks}

        # Find all bracketed numbers e.g. [1], [2], [1, 2]
        raw_matches = re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", generated_text)
        cited_indices: set[int] = set()

        for match in raw_matches:
            parts = match.split(",")
            for part in parts:
                try:
                    num = int(part.strip())
                    cited_indices.add(num)
                except ValueError:
                    continue

        citations: list[Citation] = []
        for idx in sorted(cited_indices):
            if idx in block_map:
                b = block_map[idx]
                citations.append(
                    Citation(
                        index_number=b.index_number,
                        relative_path=b.relative_path,
                        chunk_id=b.chunk_id,
                        start_line=b.start_line,
                        end_line=b.end_line,
                        symbol_name=b.symbol_name,
                        is_valid=True,
                        snippet_preview=b.formatted_content[:150] + "..."
                        if len(b.formatted_content) > 150
                        else b.formatted_content,
                    )
                )
            else:
                # Citation number was referenced by model but NOT in supplied evidence!
                citations.append(
                    Citation(
                        index_number=idx,
                        relative_path="UNKNOWN_UNVALIDATED_PATH",
                        chunk_id=f"invalid:L0-L0:index_{idx}",
                        start_line=0,
                        end_line=0,
                        is_valid=False,
                        snippet_preview="Unvalidated hallucinated citation index",
                    )
                )

        return citations
