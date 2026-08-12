"""
Repository Retrieval API Router

Endpoints:
- POST /repositories/search/keyword : Indexes repo and performs BM25 keyword search.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ingestion.scanner import ScannerError
from app.services.retrieval.engine import KeywordSearchEngine
from app.services.retrieval.models import SearchResponse

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

    Indexes the repository code chunks on-the-fly and returns matching code chunks
    with file paths, line ranges, symbol names, and signatures preserved.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    engine = KeywordSearchEngine()
    try:
        engine.index_repository(request.path)
        response = engine.search(request.query, top_k=request.top_k)
        return response
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")
    finally:
        engine.close()
