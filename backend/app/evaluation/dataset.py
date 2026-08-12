"""
Curated Offline RAG Evaluation Dataset.

Defines realistic repository questions based on RepoPilot's own codebase structure,
including expected source files and negative/unanswerable test cases.
"""

from pydantic import BaseModel


class EvalTestCase(BaseModel):
    """
    Typed evaluation test case schema.
    """

    id: str
    question: str
    expected_files: list[str]
    is_answerable: bool = True
    description: str


EVALUATION_DATASET: list[EvalTestCase] = [
    EvalTestCase(
        id="eval-001",
        question="Where is the health check endpoint defined?",
        expected_files=["backend/app/main.py", "app/main.py"],
        is_answerable=True,
        description="Tests health check endpoint retrieval.",
    ),
    EvalTestCase(
        id="eval-002",
        question="Where is repository path validation and scanner error handling implemented?",
        expected_files=["backend/app/services/ingestion/scanner.py", "app/services/ingestion/scanner.py"],
        is_answerable=True,
        description="Tests scanner ingestion service retrieval.",
    ),
    EvalTestCase(
        id="eval-003",
        question="Where is Tree-sitter code parser implemented?",
        expected_files=["backend/app/services/parsing/parser.py", "app/services/parsing/parser.py"],
        is_answerable=True,
        description="Tests Tree-sitter parser service retrieval.",
    ),
    EvalTestCase(
        id="eval-004",
        question="Where is BM25 keyword search indexed in SQLite FTS5?",
        expected_files=["backend/app/services/indexing/sqlite_fts.py", "app/services/indexing/sqlite_fts.py"],
        is_answerable=True,
        description="Tests FTS5 keyword indexing retrieval.",
    ),
    EvalTestCase(
        id="eval-005",
        question="Where are vector embeddings stored and cached in SQLite?",
        expected_files=["backend/app/services/indexing/sqlite_vector.py", "app/services/indexing/sqlite_vector.py"],
        is_answerable=True,
        description="Tests vector storage retrieval.",
    ),
    EvalTestCase(
        id="eval-006",
        question="Where is Reciprocal Rank Fusion implemented?",
        expected_files=["backend/app/services/retrieval/strategies.py", "app/services/retrieval/strategies.py"],
        is_answerable=True,
        description="Tests RRF retrieval strategy.",
    ),
    EvalTestCase(
        id="eval-007",
        question="Where is citation validation implemented?",
        expected_files=["backend/app/services/rag/citation.py", "app/services/rag/citation.py"],
        is_answerable=True,
        description="Tests citation validator retrieval.",
    ),
    EvalTestCase(
        id="eval-008",
        question="Where is prompt construction with untrusted evidence isolation handled?",
        expected_files=["backend/app/services/rag/prompt.py", "app/services/rag/prompt.py"],
        is_answerable=True,
        description="Tests prompt builder retrieval.",
    ),
    # Negative Test Cases
    EvalTestCase(
        id="eval-009",
        question="Where is qubit_simulator_quantum_gate_matrix_multiply implemented?",
        expected_files=[],
        is_answerable=False,
        description="Negative test case: unanswerable quantum computing feature question.",
    ),
    EvalTestCase(
        id="eval-010",
        question="Where is kubernetes_helm_chart_k8s_deployment_manifest defined?",
        expected_files=[],
        is_answerable=False,
        description="Negative test case: unanswerable k8s infra question.",
    ),
]
