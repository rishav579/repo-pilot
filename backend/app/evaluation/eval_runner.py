"""
Offline RAG Evaluation Runner — Evaluates retrieval recall, MRR, citation validity, and insufficient-evidence fallback.

RUN COMMAND:
    python -m app.evaluation.eval_runner
"""

import sys
from pathlib import Path
from pydantic import BaseModel

from app.evaluation.dataset import EVALUATION_DATASET, EvalTestCase
from app.services.rag.engine import RAGService
from app.services.rag.models import RAGRequest


class EvalReport(BaseModel):
    """
    Summary evaluation report metrics.
    """

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


class RAGEvaluator:
    """
    Evaluates RAG pipeline quality offline against curated dataset.
    """

    def __init__(
        self,
        repo_path: str | None = None,
        min_recall_threshold: float = 0.75,
        min_precision_threshold: float = 0.90,
    ):
        # Default to repo root if not provided
        if repo_path:
            self.repo_path = repo_path
        else:
            # Locate root directory relative to this file
            self.repo_path = str(Path(__file__).resolve().parents[3])

        self.min_recall_threshold = min_recall_threshold
        self.min_precision_threshold = min_precision_threshold

    def run_evaluation(self, dataset: list[EvalTestCase] = EVALUATION_DATASET) -> EvalReport:
        """
        Runs evaluation pipeline across dataset.
        """
        service = RAGService(db_path=":memory:")

        pos_count = 0
        neg_count = 0
        recall_hits = 0
        reciprocal_ranks: list[float] = []

        grounded_count = 0
        total_citations = 0
        valid_citations = 0
        correct_insufficient_negatives = 0
        total_latencies: list[float] = []

        try:
            for case in dataset:
                req = RAGRequest(
                    repository_path=self.repo_path,
                    question=case.question,
                    mode="keyword",
                    top_k=8,
                    min_relevance_score=0.005,
                )
                resp = service.query(req)
                total_latencies.append(resp.performance_ms.total_ms)

                if case.is_answerable:
                    pos_count += 1
                    # Check retrieval recall & MRR
                    found_rank = None

                    # Check citations and candidate files
                    retrieved_files = [c.relative_path for c in resp.citations]

                    # Also check search results directly via retrieval
                    candidate_files = [c.relative_path for c in resp.citations]

                    # Normalize paths for comparison
                    norm_candidates = [f.replace("\\", "/") for f in candidate_files]
                    norm_expected = [f.replace("\\", "/") for f in case.expected_files]

                    # Check if any expected file matched
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

        finally:
            service.close()

        recall_at_k = round(recall_hits / pos_count, 4) if pos_count > 0 else 1.0
        mrr = round(sum(reciprocal_ranks) / pos_count, 4) if pos_count > 0 else 1.0
        grounded_rate = round(grounded_count / pos_count, 4) if pos_count > 0 else 1.0
        citation_validity = (
            round(valid_citations / total_citations, 4) if total_citations > 0 else 1.0
        )
        insufficient_precision = (
            round(correct_insufficient_negatives / neg_count, 4) if neg_count > 0 else 1.0
        )
        avg_latency = round(sum(total_latencies) / len(total_latencies), 2) if total_latencies else 0.0

        passed = (
            recall_at_k >= self.min_recall_threshold
            and insufficient_precision >= self.min_precision_threshold
        )

        report = EvalReport(
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

        return report

    def print_report(self, report: EvalReport):
        """Prints a clean ASCII evaluation report."""
        print("==========================================================")
        print("          RepoPilot Offline RAG Evaluation Report         ")
        print("==========================================================")
        print(f" Total Evaluation Cases  : {report.total_cases}")
        print(f" Positive (Answerable)   : {report.positive_cases}")
        print(f" Negative (Unanswerable) : {report.negative_cases}")
        print("----------------------------------------------------------")
        print(f" Retrieval Recall@K      : {report.recall_at_k * 100:.1f}%")
        print(f" Retrieval MRR           : {report.mrr:.4f}")
        print(f" Grounded Answer Rate    : {report.grounded_answer_rate * 100:.1f}%")
        print(f" Citation Validity Rate  : {report.citation_validity_rate * 100:.1f}%")
        print(f" Insufficient Evid Prec  : {report.insufficient_evidence_precision * 100:.1f}%")
        print(f" Avg Total Latency       : {report.avg_latency_ms:.2f} ms")
        print("----------------------------------------------------------")
        status_str = "[PASSED]" if report.passed_thresholds else "[FAILED]"
        print(f" Overall Evaluation      : {status_str}")
        print("==========================================================")


def main():
    """CLI execution entrypoint."""
    evaluator = RAGEvaluator()
    report = evaluator.run_evaluation()
    evaluator.print_report(report)
    if not report.passed_thresholds:
        sys.exit(1)


if __name__ == "__main__":
    main()
