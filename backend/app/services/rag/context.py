"""
Context Assembly & Budgeting — Converts selected evidence into formatted, budget-managed prompt context.

RESPONSIBILITIES:
- Formats evidence items into unambiguous, structured source context blocks.
- Enforces character budget (`max_context_chars`) deterministically.
- Tracks whether evidence was truncated due to budget constraints.
"""

from app.services.rag.models import ContextBlock, RetrievedEvidence


class ContextBuilder:
    """
    Assembles evidence into prompt context within character budget bounds.
    """

    def __init__(self, max_context_chars: int = 8000):
        self.max_context_chars = max_context_chars

    def build_context(
        self, evidence_list: list[RetrievedEvidence]
    ) -> tuple[str, list[ContextBlock], bool]:
        """
        Builds assembled context string and list of ContextBlocks.

        Returns:
            Tuple of (assembled_context_string, list[ContextBlock], is_truncated)
        """
        if not evidence_list:
            return "", [], False

        blocks: list[ContextBlock] = []
        text_parts: list[str] = []
        current_len = 0
        truncated = False

        for ev in evidence_list:
            chunk = ev.chunk
            symbol_info = f"SYMBOL: {chunk.symbol_name}\n" if chunk.symbol_name else ""
            header = (
                f"--- SOURCE BLOCK [{ev.index_number}] ---\n"
                f"FILE: {chunk.relative_path}\n"
                f"CHUNK_ID: {chunk.chunk_id}\n"
                f"LINES: L{chunk.start_line}-L{chunk.end_line}\n"
                f"{symbol_info}\n"
                "CONTENT:\n"
            )
            content_str = chunk.code_content.strip()
            block_str = f"{header}{content_str}\n\n"

            block_len = len(block_str)
            if current_len + block_len > self.max_context_chars:
                # Truncate remaining evidence if budget exceeded
                truncated = True
                break

            current_len += block_len
            text_parts.append(block_str)
            blocks.append(
                ContextBlock(
                    index_number=ev.index_number,
                    relative_path=chunk.relative_path,
                    chunk_id=chunk.chunk_id,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    symbol_name=chunk.symbol_name,
                    formatted_content=block_str,
                )
            )

        assembled_text = "".join(text_parts).strip()
        return assembled_text, blocks, truncated
