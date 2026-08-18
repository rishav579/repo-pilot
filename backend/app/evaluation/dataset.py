"""
Curated Offline RAG Evaluation Dataset.

Defines realistic repository questions based on RepoPilot's own codebase structure,
including expected source files and negative/unanswerable test cases.
Supports evaluation across keyword, semantic, and hybrid retrieval modes.
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
        question="Where is health check endpoint defined in main?",
        expected_files=["backend/app/main.py"],
        description="Finds FastAPI health check endpoint in main.py.",
    ),
    EvalTestCase(
        id="eval-002",
        question="Where is scan_repository and validate_repository_path defined in scanner?",
        expected_files=["backend/app/services/ingestion/scanner.py"],
        description="Finds repository path validation and scanning in scanner.py.",
    ),
    EvalTestCase(
        id="eval-003",
        question="Where is parse_repository Tree-sitter code parser implemented?",
        expected_files=["backend/app/services/parsing/parser.py"],
        description="Finds Tree-sitter AST parser in parser.py.",
    ),
    EvalTestCase(
        id="eval-004",
        question="Where is SQLiteFTSIndex virtual table create statement defined?",
        expected_files=["backend/app/services/indexing/sqlite_fts.py"],
        description="Finds FTS5 index class in sqlite_fts.py.",
    ),
    EvalTestCase(
        id="eval-005",
        question="Where is store_chunk_embedding and get_cached_embedding defined in sqlite_vector?",
        expected_files=["backend/app/services/indexing/sqlite_vector.py"],
        description="Finds vector persistence storage in sqlite_vector.py.",
    ),
    EvalTestCase(
        id="eval-006",
        question="Where is HybridRetriever Reciprocal Rank Fusion implemented?",
        expected_files=["backend/app/services/retrieval/strategies.py"],
        description="Finds RRF fusion logic in strategies.py.",
    ),
    EvalTestCase(
        id="eval-007",
        question="Where is CitationValidator extract_and_validate defined in citation?",
        expected_files=["backend/app/services/rag/citation.py"],
        description="Finds citation extraction and validation in citation.py.",
    ),
    EvalTestCase(
        id="eval-008",
        question="Where is PromptBuilder build_user_prompt defined in prompt?",
        expected_files=["backend/app/services/rag/prompt.py"],
        description="Finds prompt builder and untrusted evidence isolation in prompt.py.",
    ),
    # Semantic & Concept Retrieval Cases
    EvalTestCase(
        id="eval-009",
        question="Where is FastEmbed local dense embedding provider implemented with sentence-transformers?",
        expected_files=["backend/app/services/retrieval/embeddings/fastembed.py"],
        description="Finds FastEmbed embedding provider in fastembed.py.",
    ),
    EvalTestCase(
        id="eval-010",
        question="Where is validate_github_url and clone_github_repository defined in github_cloner?",
        expected_files=["backend/app/services/ingestion/github_cloner.py"],
        description="Finds public GitHub repository validation and cloner in github_cloner.py.",
    ),
    # Negative Test Cases
    EvalTestCase(
        id="eval-011",
        question="Where is quantum_qubit_superposition_matrix_solver_nonexistent implemented?",
        expected_files=[],
        is_answerable=False,
        description="Negative test case: unanswerable quantum feature question.",
    ),
    EvalTestCase(
        id="eval-012",
        question="Where is k8s_kubernetes_terraform_aws_lambda_nonexistent defined?",
        expected_files=[],
        is_answerable=False,
        description="Negative test case: unanswerable infra question.",
    ),
]
