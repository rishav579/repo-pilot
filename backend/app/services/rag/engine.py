"""
Repository Q&A / RAG Service Engine — Orchestrates retrieval, evidence selection, context assembly, LLM generation, and citation validation.

PIPELINE:
1. Validate Repository Path & User Question
2. Retrieve Candidate Code Chunks (`RetrievalService`)
3. Select Evidence (`EvidenceSelector`)
4. Assemble Context & Enforce Budget (`ContextBuilder`)
5. Build Grounded Security Prompt (`PromptBuilder`)
6. Generate Answer (`BaseLLMProvider`)
7. Extract & Validate Citations (`CitationValidator`)
8. Format `RAGResponse` (grounded | insufficient_evidence)
"""

from app.services.ingestion.scanner import validate_repository_path
from app.services.rag.citation import CitationValidator
from app.services.rag.context import ContextBuilder
from app.services.rag.evidence import EvidenceSelector
from app.services.rag.llm.base import BaseLLMProvider, LLMError
from app.services.rag.llm.mock import MockLLMProvider
from app.services.rag.models import RAGRequest, RAGResponse
from app.services.rag.prompt import INSUFFICIENT_EVIDENCE_SENTINEL, PromptBuilder
from app.services.retrieval.engine import RetrievalService
from app.services.retrieval.normalizer import normalize_query


class RAGService:
    """
    Core RAG Service Layer for grounded repository question answering.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_provider: BaseLLMProvider | None = None,
        db_path: str = ":memory:",
    ):
        self.retrieval_service = retrieval_service or RetrievalService(db_path=db_path)
        self.llm_provider = llm_provider or MockLLMProvider()

    def query(self, request: RAGRequest) -> RAGResponse:
        """
        Execute grounded RAG pipeline for a repository question.

        Args:
            request: RAGRequest instance containing question, repo path, mode, top_k.

        Returns:
            RAGResponse object.
        """
        # 1. Validate repository path
        validated_repo_path = validate_repository_path(request.repository_path)

        # 2. Normalize question
        normalized_q = normalize_query(request.question)
        if not normalized_q:
            return RAGResponse(
                question=request.question,
                answer="Question cannot be empty or whitespace only.",
                status="error",
                retrieval_mode=request.mode,
                evidence_count=0,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
            )

        # 3. Perform Repository Retrieval
        self.retrieval_service.index_repository(str(validated_repo_path))
        search_res = self.retrieval_service.search(
            normalized_q, mode=request.mode, top_k=request.top_k
        )

        # 4. Evidence Selection
        selector = EvidenceSelector(
            min_relevance_score=request.min_relevance_score,
            max_evidence_chunks=request.top_k,
        )
        selected_evidence = selector.select_evidence(search_res.results)

        if not selected_evidence:
            return RAGResponse(
                question=normalized_q,
                answer=INSUFFICIENT_EVIDENCE_SENTINEL,
                status="insufficient_evidence",
                citations=[],
                retrieval_mode=request.mode,
                evidence_count=0,
                context_truncated=False,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
            )

        # 5. Context Assembly & Budgeting
        context_builder = ContextBuilder(max_context_chars=request.max_context_chars)
        assembled_context, context_blocks, truncated = context_builder.build_context(
            selected_evidence
        )

        # 6. Prompt Construction
        system_instr = PromptBuilder.get_system_instruction()
        user_prompt = PromptBuilder.build_user_prompt(normalized_q, assembled_context)

        # 7. LLM Answer Generation
        try:
            raw_answer = self.llm_provider.generate(
                prompt=user_prompt,
                system_instruction=system_instr,
            )
        except LLMError as e:
            return RAGResponse(
                question=normalized_q,
                answer=f"LLM Provider Error: {str(e)}",
                status="error",
                retrieval_mode=request.mode,
                evidence_count=len(selected_evidence),
                context_truncated=truncated,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
            )

        # Handle explicit insufficient evidence response from LLM
        if INSUFFICIENT_EVIDENCE_SENTINEL in raw_answer or not raw_answer.strip():
            return RAGResponse(
                question=normalized_q,
                answer=INSUFFICIENT_EVIDENCE_SENTINEL,
                status="insufficient_evidence",
                citations=[],
                retrieval_mode=request.mode,
                evidence_count=len(selected_evidence),
                context_truncated=truncated,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
            )

        # 8. Citation Extraction & Validation
        citations = CitationValidator.extract_and_validate(raw_answer, context_blocks)
        # Filter out invalid citations if any exist
        valid_citations = [c for c in citations if c.is_valid]

        return RAGResponse(
            question=normalized_q,
            answer=raw_answer,
            status="grounded",
            citations=valid_citations,
            retrieval_mode=request.mode,
            evidence_count=len(selected_evidence),
            context_truncated=truncated,
            provider_name=self.llm_provider.provider_name,
            model_name=self.llm_provider.model_name,
        )

    def close(self):
        """Close resources."""
        self.retrieval_service.close()
