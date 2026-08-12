"""
Repository Management API Router

Endpoints:
- POST /repositories : Register a local repository.
- GET /repositories : List all registered repositories.
- GET /repositories/{repository_id} : Get status record for a repository.
- POST /repositories/{repository_id}/index : Trigger repository indexing.
- POST /repositories/scan : (Backward-compatible) Scan a local directory.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ingestion.scanner import ScannerError, scan_repository
from app.services.repository.models import IndexingSummary, RepositoryRecord, RepositoryRegistrationRequest
from app.services.repository.service import RepositoryService

router = APIRouter(
    prefix="/repositories",
    tags=["repositories"],
)

DEFAULT_DB_PATH = ".repopilot_data.db"
_shared_service: RepositoryService | None = None


def get_repository_service() -> RepositoryService:
    """Get or initialize the shared RepositoryService instance for API endpoints."""
    global _shared_service
    if _shared_service is None:
        _shared_service = RepositoryService(db_path=DEFAULT_DB_PATH)
    return _shared_service


def set_repository_service(service: RepositoryService | None):
    """Set custom service instance (useful for unit tests)."""
    global _shared_service
    _shared_service = service


class DirectoryScanRequest(BaseModel):
    path: str
    require_git: bool = False


class TriggerIndexRequest(BaseModel):
    enable_semantic: bool | None = None


@router.post("", response_model=RepositoryRecord)
def register_repository_endpoint(request: RepositoryRegistrationRequest):
    """
    Validate and register a local repository directory.
    """
    service = get_repository_service()
    try:
        record = service.register_repository(request.path)
        return record
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")


@router.get("", response_model=list[RepositoryRecord])
def list_repositories_endpoint():
    """
    List all registered repositories with their lifecycle status and metrics.
    """
    service = get_repository_service()
    return service.list_repositories()


@router.get("/{repository_id}", response_model=RepositoryRecord)
def get_repository_status_endpoint(repository_id: str):
    """
    Get repository record and current lifecycle status.
    """
    service = get_repository_service()
    record = service.get_repository(repository_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")
    return record


@router.post("/{repository_id}/index", response_model=IndexingSummary)
def trigger_indexing_endpoint(repository_id: str, request: TriggerIndexRequest | None = None):
    """
    Trigger scanning, AST parsing, chunking, and indexing for a registered repository.
    """
    service = get_repository_service()
    try:
        enable_semantic = request.enable_semantic if request else None
        summary = service.index_repository(repository_id, enable_semantic=enable_semantic)
        if summary.status.value == "failed":
            raise HTTPException(status_code=500, detail=f"Indexing failed: {summary.error_message}")
        return summary
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")


@router.post("/scan")
def scan_directory_endpoint(request: DirectoryScanRequest):
    """
    (Backward-compatible) Scan a repository path and return file inventory.
    """
    try:
        result = scan_repository(request.path, require_git=request.require_git)
        return result
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scanning error: {str(e)}")
