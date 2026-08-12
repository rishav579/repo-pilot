"""
Repository Parsing API Router

Handles code parsing requests for ingested repositories.

Endpoints:
- POST /repositories/parse : Parses source files in a repository and returns extracted AST symbols.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ingestion.scanner import ScannerError
from app.services.parsing.models import ParseResult
from app.services.parsing.parser import parse_repository

router = APIRouter(
    prefix="/repositories",
    tags=["parsing"],
)


class ParseRequest(BaseModel):
    """
    Request body for the repository code parsing endpoint.

    Fields:
    - path: Local repository root directory path
    - relative_paths: Optional list of relative file paths to parse (parses all supported files if omitted)
    """

    path: str
    relative_paths: list[str] | None = None


@router.post("/parse", response_model=ParseResult)
def parse_repository_endpoint(request: ParseRequest):
    """
    Parse source files in a repository using Tree-sitter and return extracted symbols.

    Accepts a local repository path, scans the repo using ingestion rules, and extracts:
    - Functions, methods, classes, interfaces, and imports
    - Signatures and line ranges for every symbol
    - Syntax error flags for malformed files

    Supports Python, JavaScript, and TypeScript files.
    """
    try:
        result = parse_repository(request.path, relative_paths=request.relative_paths)
        return result
    except ScannerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
