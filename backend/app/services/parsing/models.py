"""
Parsing Models — Typed data structures for code symbols and parsed files.

WHY TYPED MODELS FOR PARSED CODE?
    When Tree-sitter parses a source file, it produces a tree of AST nodes.
    We convert that raw AST into typed, structured models that are easy to:
    1. Store in a database (in future phases)
    2. Pass to the retrieval engine and LLM prompt builder
    3. Return via API endpoints
    4. Display in a frontend with file path + exact line numbers

CONVENTIONS:
    - Line numbers are 1-indexed (human-readable: Line 1 to Line N).
      Tree-sitter uses 0-indexed (0 to N-1), so we convert during parsing.
"""

from enum import Enum
from pydantic import BaseModel


class SymbolKind(str, Enum):
    """
    Kinds of code symbols extracted from ASTs.
    """

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    IMPORT = "import"


class SymbolInfo(BaseModel):
    """
    Represents a single extracted code symbol (function, class, method, etc.).

    Fields:
    - name: Symbol identifier (e.g. "scan_repository", "ScannerError")
    - kind: SymbolKind ("function", "class", "method", "interface", "import")
    - start_line: 1-indexed starting line number in the source file
    - end_line: 1-indexed ending line number in the source file
    - signature: Optional signature or declaration snippet (e.g. "def scan_repository(repo_path: str)")
    - docstring: Optional docstring or leading comments
    - parent_name: Name of parent class if this symbol is a method (e.g. "TestScanFile")
    """

    name: str
    kind: SymbolKind
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    parent_name: str | None = None


class ParsedFile(BaseModel):
    """
    Represents a source file and all structural symbols extracted from it.

    Fields:
    - relative_path: Path relative to repository root (e.g., "backend/app/main.py")
    - language: Programming language name (e.g. "Python", "TypeScript")
    - symbols: List of extracted symbols (functions, classes, methods, interfaces, imports)
    - imports: List of imported module names or import statements for fast lookup
    - total_symbols: Count of extracted symbols
    - has_syntax_errors: True if Tree-sitter detected syntax errors in the file
    """

    relative_path: str
    language: str
    symbols: list[SymbolInfo]
    imports: list[str]
    total_symbols: int
    has_syntax_errors: bool = False


class ParseSummary(BaseModel):
    """
    Summary of code parsing across a repository or set of files.
    """

    repository_path: str
    files_parsed: int
    total_symbols_extracted: int
    languages_parsed: dict[str, int]
    files: list[ParsedFile]


# Alias ParseResult to ParseSummary
ParseResult = ParseSummary
