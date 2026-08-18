"""
Offline RAG Evaluation Runner — Evaluates retrieval recall, MRR, citation validity, and insufficient-evidence fallback across Keyword, Semantic, and Hybrid retrieval modes.

RUN COMMAND:
    python -m app.evaluation.eval_runner
"""

import sys
from pathlib import Path
from pydantic import BaseModel

from app.evaluation.dataset import EVALUATION_DATASET, EvalTestCase
from app.services.rag.engine import RAGService
from app.services.rag.models import RAGRequest
from app.services.repository.service import RepositoryService
from app.services.retrieval.config import RetrievalConfig


class EvalReport(BaseModel):
    """
    Summary evaluation report metrics for a specific retrieval mode.
    """

    mode: str
    total_cases: int
    positive_cases: int
    negative_cases: int
    recall_at_k: float
    mrr: float
    grounded_answer_rate: float
    citation_validity_rate: float
    insufficient_evidence_precision: float
    avg_latency_ms: float
    passed_thresholds: bool


class MultiModeEvalReport(BaseModel):
    """
    Full multi-mode evaluation report.
    """

    keyword_report: EvalReport
    semantic_report: EvalReport
    hybrid_report: EvalReport
    passed_all: bool


class RAGEvaluator:
    """
    Evaluates RAG pipeline quality offline against curated dataset across all retrieval modes.
    """

    def __init__(
        self,
        repo_path: str | None = None,
        min_recall_threshold: float = 0.75,
        min_precision_threshold: float = 0.90,
    ):
        if repo_path:
            self.repo_path = repo_path
        else:
            self.repo_path = str(Path(__file__).resolve().parents[3])

        self.min_recall_threshold = min_recall_threshold
        self.min_precision_threshold = min_precision_threshold

    def run_mode_evaluation(
        self,
        service: RAGService,
        mode: str = "keyword",
        dataset: list[EvalTestCase] = EVALUATION_DATASET,
    ) -> EvalReport:
        """
        Runs evaluation pipeline across dataset for a specific retrieval mode.
        """
        pos_count = 0
        neg_count = 0
        recall_hits = 0
        reciprocal_ranks: list[float] = []

        grounded_count = 0
        total_citations = 0
        valid_citations = 0
        correct_insufficient_negatives = 0
        total_latencies: list[float] = []

        for case in dataset:
            req = RAGRequest(
                repository_path=self.repo_path,
                question=case.question,
                mode=mode,  # type: ignore
                top_k=8,
                min_relevance_score=0.005,
            )
            resp = service.query(req)
            total_latencies.append(resp.performance_ms.total_ms)

            if case.is_answerable:
                pos_count += 1
                found_rank = None

                candidate_files = [c.relative_path for c in resp.citations]
                norm_candidates = [f.replace("\\", "/") for f in candidate_files]
                norm_expected = [f.replace("\\", "/") for f in case.expected_files]

                hit = False
                for idx, cand in enumerate(norm_candidates, start=1):
                    if any(exp in cand for exp in norm_expected):
                        hit = True
                        if found_rank is None:
                            found_rank = idx
                        break

                if hit:
                    recall_hits += 1
                    reciprocal_ranks.append(1.0 / found_rank if found_rank else 1.0)
                else:
                    reciprocal_ranks.append(0.0)

                if resp.status == "grounded":
                    grounded_count += 1

                for cit in resp.citations:
                    total_citations += 1
                    if cit.is_valid:
                        valid_citations += 1

            else:
                neg_count += 1
                if resp.status == "insufficient_evidence":
                    correct_insufficient_negatives += 1

        recall_at_k = round(recall_hits / pos_count, 4) if pos_count > 0 else 1.0
        mrr = round(sum(reciprocal_ranks) / pos_count, 4) if pos_count > 0 else 1.0
        grounded_rate = round(grounded_count / pos_count, 4) if pos_count > 0 else 1.0
        citation_validity = (
            round(valid_citations / total_citations, 4) if total_citations > 0 else 1.0
        )
        insufficient_precision = (
            round(correct_insufficient_negatives / neg_count, 4) if neg_count > 0 else 1.0
        )
        avg_latency = (
            round(sum(total_latencies) / len(total_latencies), 2)
            if total_latencies
            else 0.0
        )

        passed = (
            recall_at_k >= self.min_recall_threshold
            and insufficient_precision >= self.min_precision_threshold
        )

        return EvalReport(
            mode=mode,
            total_cases=len(dataset),
            positive_cases=pos_count,
            negative_cases=neg_count,
            recall_at_k=recall_at_k,
            mrr=mrr,
            grounded_answer_rate=grounded_rate,
            citation_validity_rate=citation_validity,
            insufficient_evidence_precision=insufficient_precision,
            avg_latency_ms=avg_latency,
            passed_thresholds=passed,
        )

    def run_evaluation(
        self, dataset: list[EvalTestCase] = EVALUATION_DATASET
    ) -> MultiModeEvalReport:
        """
        Runs comprehensive evaluation across Keyword, Semantic, and Hybrid retrieval modes.
        """
        config = RetrievalConfig(
            semantic_enabled=True,
            provider_type="fastembed",
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
        )
        repo_service = RepositoryService(db_path=":memory:", config=config)
        rag_service = RAGService(repository_service=repo_service, db_path=":memory:")

        # Warm-up and index repository with FastEmbed semantic embeddings
        reg_record = repo_service.register_repository(self.repo_path)
        repo_service.index_repository(reg_record.repository_id, enable_semantic=True)

        try:
            kw_report = self.run_mode_evaluation(rag_service, mode="keyword", dataset=dataset)
            sem_report = self.run_mode_evaluation(rag_service, mode="semantic", dataset=dataset)
            hyb_report = self.run_mode_evaluation(rag_service, mode="hybrid", dataset=dataset)
        finally:
            rag_service.close()
            repo_service.close()

        passed_all = (
            kw_report.passed_thresholds
            and sem_report.passed_thresholds
            and hyb_report.passed_thresholds
        )

        return MultiModeEvalReport(
            keyword_report=kw_report,
            semantic_report=sem_report,
            hybrid_report=hyb_report,
            passed_all=passed_all,
        )

    def print_report(self, multi_report: MultiModeEvalReport):
        """Prints formatted benchmark comparison table."""
        print("================================================================================")
        print("                 RepoPilot Multi-Strategy Retrieval Benchmark                   ")
        print("                 (FastEmbed sentence-transformers/all-MiniLM-L6-v2)             ")
        print("================================================================================")
        print(f" Total Evaluation Cases  : {multi_report.keyword_report.total_cases}")
        print(f" Positive (Answerable)   : {multi_report.keyword_report.positive_cases}")
        print(f" Negative (Unanswerable) : {multi_report.keyword_report.negative_cases}")
        print("--------------------------------------------------------------------------------")
        print(f"{'Metric':<32} | {'Keyword (BM25)':<14} | {'Semantic (384d)':<15} | {'Hybrid (RRF)':<14}")
        print("--------------------------------------------------------------------------------")

        kw = multi_report.keyword_report
        sem = multi_report.semantic_report
        hyb = multi_report.hybrid_report

        print(f"{'Recall@K':<32} | {kw.recall_at_k * 100:>13.1f}% | {sem.recall_at_k * 100:>14.1f}% | {hyb.recall_at_k * 100:>13.1f}%")
        print(f"{'Mean Reciprocal Rank (MRR)':<32} | {kw.mrr:>14.4f} | {sem.mrr:>15.4f} | {hyb.mrr:>14.4f}")
        print(f"{'Grounded Answer Rate':<32} | {kw.grounded_answer_rate * 100:>13.1f}% | {sem.grounded_answer_rate * 100:>14.1f}% | {hyb.grounded_answer_rate * 100:>13.1f}%")
        print(f"{'Citation Validity Rate':<32} | {kw.citation_validity_rate * 100:>13.1f}% | {sem.citation_validity_rate * 100:>14.1f}% | {hyb.citation_validity_rate * 100:>13.1f}%")
        print(f"{'Insufficient Evidence Precision':<32} | {kw.insufficient_evidence_precision * 100:>13.1f}% | {sem.insufficient_evidence_precision * 100:>14.1f}% | {hyb.insufficient_evidence_precision * 100:>13.1f}%")
        print(f"{'Average Query Latency':<32} | {kw.avg_latency_ms:>11.2f} ms | {sem.avg_latency_ms:>12.2f} ms | {hyb.avg_latency_ms:>11.2f} ms")
        print("--------------------------------------------------------------------------------")
        status_str = "[PASSED ALL MODES]" if multi_report.passed_all else "[FAILED]"
        print(f" Overall Benchmark Verdict      : {status_str}")
        print("================================================================================")


def main():
    """CLI execution entrypoint."""
    evaluator = RAGEvaluator()
    multi_report = evaluator.run_evaluation()
    evaluator.print_report(multi_report)
    if not multi_report.passed_all:
        sys.exit(1)


if __name__ == "__main__":
    main()
