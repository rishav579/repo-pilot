"""
Repository Q&A / RAG API Router

Thin router layer that delegates request validation, RAG execution, and answer formatting
to the RAGService layer.

Endpoints:
- POST /repositories/query : Grounded repository Q&A endpoint.
"""

from fastapi import APIRouter, HTTPException
from app.services.ingestion.scanner import ScannerError
from app.services.rag.engine import RAGService
from app.services.rag.models import RAGRequest, RAGResponse

router = APIRouter(
    prefix="/repositories",
    tags=["rag"],
)


@router.post("/query", response_model=RAGResponse)
def query_repository_endpoint(request: RAGRequest):
    """
    Perform grounded Repository Q&A over source code chunks using the RAG pipeline.

    Returns grounded answer with validated citations, evidence metadata, and retrieval mode.
    """
    rag_service = RAGService()
    try:
        response = rag_service.query(request)
        return response
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG processing error: {str(e)}")
    finally:
        rag_service.close()
