"""
RAG Domain Models — Typed Pydantic data structures for the Repository Q&A pipeline.

MODELS:
- RetrievedEvidence: Wraps CodeChunk + retrieval score & relevance threshold status.
- ContextBlock: Structured representation of a single code snippet formatted for LLM context.
- Citation: Validated citation linking an LLM answer back to exact file/chunk/line ranges.
- RAGRequest: API request schema for POST /repositories/query.
- RAGResponse: API response schema containing answer, validated citations, and evidence metadata.
"""

from pydantic import BaseModel, Field
from app.services.retrieval.models import CodeChunk


class RetrievedEvidence(BaseModel):
    """
    Selected code chunk evidence with retrieval score and selection metadata.
    """

    chunk: CodeChunk
    score: float
    score_type: str = "bm25"
    index_number: int  # 1-indexed reference number e.g. [1]


class ContextBlock(BaseModel):
    """
    Formatted code context block ready for prompt assembly.
    """

    index_number: int
    relative_path: str
    chunk_id: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    formatted_content: str


class Citation(BaseModel):
    """
    Validated citation reference linking an answer back to source code evidence.
    """

    index_number: int
    relative_path: str
    chunk_id: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    is_valid: bool = True
    snippet_preview: str | None = None


class RAGRequest(BaseModel):
    """
    API request body for POST /repositories/query.
    """

    repository_path: str
    question: str
    mode: str = Field(default="auto", description="Retrieval mode: auto | keyword | semantic | hybrid")
    top_k: int = Field(default=8, ge=1, le=50)
    max_context_chars: int = Field(default=8000, ge=1000, le=32000)
    min_relevance_score: float = Field(default=0.01, ge=0.0)


class RAGResponse(BaseModel):
    """
    API response model for POST /repositories/query.
    """

    question: str
    answer: str
    status: str  # "grounded" | "insufficient_evidence" | "error"
    citations: list[Citation] = []
    retrieval_mode: str
    evidence_count: int
    context_truncated: bool = False
    provider_name: str
    model_name: str
