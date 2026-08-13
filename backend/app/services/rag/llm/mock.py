"""
Mock LLM Provider — Deterministic, offline LLM text generator for unit tests & dev.

HOW IT WORKS:
    1. Inspects user prompt for retrieved source blocks (`--- SOURCE BLOCK [n] ---`).
    2. If no evidence blocks exist or prompt contains "NO EVIDENCE RETRIEVED", returns
       the sentinel INSUFFICIENT_EVIDENCE.
    3. Synthesizes a grounded answer referencing the detected source blocks with citations [1], [2].
"""

import re
from app.services.rag.llm.base import BaseLLMProvider
from app.services.rag.prompt import INSUFFICIENT_EVIDENCE_SENTINEL


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider.
    """

    def __init__(self, model_name: str = "mock-gpt-4"):
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self, prompt: str, system_instruction: str = "", temperature: float = 0.2
    ) -> str:
        """Generate deterministic grounded response based on context evidence blocks."""
        if (
            "<untrusted_retrieved_evidence>\nNO EVIDENCE RETRIEVED\n</untrusted_retrieved_evidence>"
            in prompt
            or not prompt
        ):
            return INSUFFICIENT_EVIDENCE_SENTINEL

        # Extract source block references like [1], [2] from prompt
        matches = re.findall(r"--- SOURCE BLOCK \[(\d+)\] ---", prompt)
        if not matches:
            return INSUFFICIENT_EVIDENCE_SENTINEL

        # Extract file paths from prompt
        files = re.findall(r"FILE: ([^\n]+)", prompt)

        citation_refs = ", ".join([f"[{m}]" for m in matches])
        files_summary = ", ".join(set(files)) if files else "source repository"

        return (
            f"Based on the provided codebase evidence in {files_summary}, "
            f"the requested feature/logic is defined in source blocks {citation_refs}.\n\n"
            f"Reference citations: {citation_refs}."
        )
