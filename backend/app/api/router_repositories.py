"""
Repository Scan API Router

WHY A SEPARATE ROUTER?
    FastAPI lets you organize endpoints into "routers" — separate files
    that handle related endpoints. This keeps main.py clean.

    Instead of putting every endpoint in main.py (which would become huge),
    we create a router for each feature area:
    - /repositories/* → handled by this router
    - /health → stays in main.py (it's a global endpoint)

    The router is then "included" into the main app in main.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ingestion.models import ScanSummary
from app.services.ingestion.scanner import ScannerError, scan_repository


# Create a router with a prefix — all endpoints in this router
# will start with /repositories
router = APIRouter(
    prefix="/repositories",
    tags=["repositories"],  # Groups endpoints in the API docs
)


class ScanRequest(BaseModel):
    """
    Request body for the scan endpoint.

    The client sends a JSON body like:
        {"path": "/path/to/repository"}

    Pydantic validates that 'path' is present and is a string.
    """

    path: str


@router.post("/scan", response_model=ScanSummary)
def scan_repository_endpoint(request: ScanRequest):
    """
    Scan a local repository and return a summary of discovered files.

    Accepts a local directory path, validates it, walks the file tree,
    and returns a summary including:
    - Total files found
    - Source vs. excluded vs. binary file counts
    - Languages detected with file counts
    - Total and source file sizes

    Does NOT return the full file list (to keep the response small).
    """
    try:
        result = scan_repository(request.path, require_git=False)
        return result.summary
    except ScannerError as e:
        # Return a 400 Bad Request with the error message.
        # HTTP 400 means "the client sent a bad request" (e.g., invalid path).
        raise HTTPException(status_code=400, detail=str(e))
