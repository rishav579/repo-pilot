"""
Repository Q&A / RAG Service Engine — Orchestrates retrieval, evidence selection, context assembly, LLM generation, citation validation, and performance timing.

PIPELINE:
1. Validate Repository Path & User Question
2. Retrieve Candidate Code Chunks (`RetrievalService`)
3. Select Evidence (`EvidenceSelector`)
4. Assemble Context & Enforce Budget (`ContextBuilder`)
5. Build Grounded Security Prompt (`PromptBuilder`)
6. Generate Answer (`BaseLLMProvider`)
7. Extract & Validate Citations (`CitationValidator`)
8. Format `RAGResponse` (grounded | insufficient_evidence | error | unusable_output)
"""

import time
from app.services.ingestion.scanner import validate_repository_path
from app.services.rag.citation import CitationValidator
from app.services.rag.context import ContextBuilder
from app.services.rag.evidence import EvidenceSelector
from app.services.rag.llm.base import BaseLLMProvider, LLMError
from app.services.rag.llm.mock import MockLLMProvider
from app.services.rag.models import PerformanceMetrics, RAGRequest, RAGResponse
from app.services.rag.prompt import INSUFFICIENT_EVIDENCE_SENTINEL, PromptBuilder
from app.services.retrieval.engine import RetrievalService
from app.services.retrieval.normalizer import normalize_query


from app.services.repository.models import RepositoryStatus
from app.services.repository.service import RepositoryService


class RAGService:
    """
    Core RAG Service Layer for grounded repository question answering with performance timing instrumentation.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_provider: BaseLLMProvider | None = None,
        repository_service: RepositoryService | None = None,
        db_path: str = ":memory:",
    ):
        self.db_path = db_path
        self.repository_service = repository_service or RepositoryService(db_path=db_path)
        self.retrieval_service = retrieval_service or RetrievalService(
            db_path=db_path,
            config=self.repository_service.config,
            embedding_provider=self.repository_service.embedding_provider,
            fts_index=self.repository_service.fts_index,
            vector_storage=self.repository_service.vector_storage,
        )
        self.llm_provider = llm_provider or MockLLMProvider()

    def query(self, request: RAGRequest) -> RAGResponse:
        """
        Execute grounded RAG pipeline for a repository question.

        Args:
            request: RAGRequest instance containing question, repo path or repository_id, mode, top_k.

        Returns:
            RAGResponse object with performance timing metrics.
        """
        t_start = time.perf_counter()
        metrics = PerformanceMetrics()

        # 1. Validate / Register repository path & check readiness
        repo_record = self.repository_service.get_repository(request.repository_path)
        if not repo_record:
            # Register path on-the-fly for backward compatibility
            try:
                repo_record = self.repository_service.register_repository(request.repository_path)
            except Exception as e:
                validated_repo_path = validate_repository_path(request.repository_path)
                repo_record = self.repository_service.get_repository(str(validated_repo_path))

        # Check repository readiness status
        if repo_record and repo_record.status == RepositoryStatus.INDEXING:
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=request.question,
                answer="Repository is currently indexing. Please wait until indexing completes.",
                status="error",
                retrieval_mode=request.mode,
                evidence_count=0,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )
        elif repo_record and repo_record.status == RepositoryStatus.FAILED:
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=request.question,
                answer=f"Repository indexing failed: {repo_record.error_message}",
                status="error",
                retrieval_mode=request.mode,
                evidence_count=0,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )

        # Ensure repository is indexed into the FTS index if pending
        if repo_record and (
            repo_record.status == RepositoryStatus.REGISTERED
            or repo_record.indexed_chunk_count == 0
        ):
            self.repository_service.index_repository(repo_record.repository_id)
            repo_record = self.repository_service.get_repository(repo_record.repository_id)

        # 2. Normalize question
        normalized_q = normalize_query(request.question)
        if not normalized_q:
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=request.question,
                answer="Question cannot be empty or whitespace only.",
                status="error",
                retrieval_mode=request.mode,
                evidence_count=0,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )

        # 3. Perform Repository Retrieval (Scoped to repository_id if registered)
        t_ret_start = time.perf_counter()
        repo_id_filter = repo_record.repository_id if repo_record else None
        search_res_obj = self.retrieval_service.search(
            normalized_q, repository_id=repo_id_filter, mode=request.mode, top_k=request.top_k
        )
        search_results_list = search_res_obj.results

        metrics.retrieval_ms = round((time.perf_counter() - t_ret_start) * 1000, 2)
        total_candidates = len(search_results_list)

        # 4. Evidence Selection
        t_sel_start = time.perf_counter()
        selector = EvidenceSelector(
            min_relevance_score=request.min_relevance_score,
            max_evidence_chunks=request.top_k,
        )
        selected_evidence = selector.select_evidence(search_results_list)
        metrics.evidence_selection_ms = round((time.perf_counter() - t_sel_start) * 1000, 2)

        # Case A / B: No candidates or all candidates below threshold
        if not selected_evidence:
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=normalized_q,
                answer=INSUFFICIENT_EVIDENCE_SENTINEL,
                status="insufficient_evidence",
                citations=[],
                retrieval_mode=request.mode,
                retrieved_candidate_count=total_candidates,
                evidence_count=0,
                context_truncated=False,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )

        # 5. Context Assembly & Budgeting
        t_ctx_start = time.perf_counter()
        context_builder = ContextBuilder(max_context_chars=request.max_context_chars)
        assembled_context, context_blocks, truncated = context_builder.build_context(
            selected_evidence
        )
        metrics.context_assembly_ms = round((time.perf_counter() - t_ctx_start) * 1000, 2)

        # 6. Prompt Construction
        system_instr = PromptBuilder.get_system_instruction()
        user_prompt = PromptBuilder.build_user_prompt(normalized_q, assembled_context)

        # 7. LLM Answer Generation (Case C: LLM failure handling)
        t_llm_start = time.perf_counter()
        try:
            raw_answer = self.llm_provider.generate(
                prompt=user_prompt,
                system_instruction=system_instr,
            )
        except LLMError as e:
            metrics.llm_generation_ms = round((time.perf_counter() - t_llm_start) * 1000, 2)
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=normalized_q,
                answer=f"LLM Provider Error: {str(e)}",
                status="error",
                retrieval_mode=request.mode,
                retrieved_candidate_count=total_candidates,
                evidence_count=len(selected_evidence),
                context_character_count=len(assembled_context),
                context_truncated=truncated,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )
        metrics.llm_generation_ms = round((time.perf_counter() - t_llm_start) * 1000, 2)

        # Case E: Empty / whitespace / unusable LLM output
        if not raw_answer or not raw_answer.strip():
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=normalized_q,
                answer="LLM returned an empty or unusable response.",
                status="unusable_output",
                retrieval_mode=request.mode,
                retrieved_candidate_count=total_candidates,
                evidence_count=len(selected_evidence),
                context_character_count=len(assembled_context),
                context_truncated=truncated,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )

        # Handle explicit insufficient evidence response from LLM
        if INSUFFICIENT_EVIDENCE_SENTINEL in raw_answer:
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return RAGResponse(
                question=normalized_q,
                answer=INSUFFICIENT_EVIDENCE_SENTINEL,
                status="insufficient_evidence",
                citations=[],
                retrieval_mode=request.mode,
                retrieved_candidate_count=total_candidates,
                evidence_count=len(selected_evidence),
                context_character_count=len(assembled_context),
                context_truncated=truncated,
                provider_name=self.llm_provider.provider_name,
                model_name=self.llm_provider.model_name,
                performance_ms=metrics,
            )

        # 8. Citation Extraction & Validation (Case D: Hallucinated citations)
        all_citations = CitationValidator.extract_and_validate(raw_answer, context_blocks)
        valid_citations = [c for c in all_citations if c.is_valid]
        invalid_citations = [c for c in all_citations if not c.is_valid]

        metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        return RAGResponse(
            question=normalized_q,
            answer=raw_answer,
            status="grounded",
            citations=valid_citations,
            retrieval_mode=request.mode,
            retrieved_candidate_count=total_candidates,
            evidence_count=len(selected_evidence),
            valid_citation_count=len(valid_citations),
            invalid_citation_count=len(invalid_citations),
            context_character_count=len(assembled_context),
            context_truncated=truncated,
            provider_name=self.llm_provider.provider_name,
            model_name=self.llm_provider.model_name,
            performance_ms=metrics,
        )

    def close(self):
        """Close resources."""
        self.retrieval_service.close()
        self.repository_service.close()
