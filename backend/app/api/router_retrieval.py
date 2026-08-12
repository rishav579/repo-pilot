"""
Repository Retrieval API Router

Thin router layer that delegates request normalization, validation, indexing, and retrieval
to the RetrievalService layer.

Endpoints:
- POST /repositories/search/keyword : Indexes repository and executes keyword code retrieval.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ingestion.scanner import ScannerError
from app.services.retrieval.engine import RetrievalService
from app.services.retrieval.models import SearchResponse
from app.services.retrieval.normalizer import normalize_query

router = APIRouter(
    prefix="/repositories",
    tags=["retrieval"],
)


class KeywordSearchRequest(BaseModel):
    """
    Request body for keyword search endpoint.

    Fields:
    - path: Path to local repository root directory
    - query: Keyword search query (e.g. "health_check", "scanner", "validate_path")
    - top_k: Maximum number of results to return (default 10, range 1-100)
    """

    path: str
    query: str
    top_k: int = Field(default=10, ge=1, le=100)


@router.post("/search/keyword", response_model=SearchResponse)
def search_keyword_endpoint(request: KeywordSearchRequest):
    """
    Perform deterministic BM25 keyword search over a repository's source code.

    Delegates to RetrievalService for query normalization, indexing, deduplication, and search.
    """
    normalized = normalize_query(request.query)
    if not normalized:
        raise HTTPException(
            status_code=400, detail="Search query cannot be empty or whitespace only"
        )

    service = RetrievalService()
    try:
        service.index_repository(request.path)
        response = service.search(normalized, top_k=request.top_k)
        return response
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")
    finally:
        service.close()
