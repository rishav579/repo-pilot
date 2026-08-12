"""
Code Chunker — Converts parsed AST files and raw source files into CodeChunks.

CHUNKING STRATEGY:
    1. Symbol-based chunking (Primary):
       Uses Phase 3 AST parsing to chunk by function, class, method, or interface boundary.
       This preserves exact code scope and symbol names for accurate citations.

    2. Sliding window chunking (Fallback):
       For files without AST symbols (Markdown, text, configs), chunk by 50-line blocks.
"""

from pathlib import Path
from app.services.parsing.models import ParsedFile, SymbolInfo, SymbolKind
from app.services.retrieval.models import CodeChunk


def extract_line_range(lines: list[str], start_line: int, end_line: int) -> str:
    """Extract 1-indexed line range from line list."""
    if start_line < 1:
        start_line = 1
    if end_line > len(lines):
        end_line = len(lines)
    selected = lines[start_line - 1 : end_line]
    return "\n".join(selected)


def build_chunk_id(relative_path: str, start_line: int, end_line: int, symbol_name: str | None = None) -> str:
    """Build a unique chunk identifier."""
    name_part = f":{symbol_name}" if symbol_name else ""
    return f"{relative_path}:L{start_line}-L{end_line}{name_part}"


def chunk_parsed_file(parsed_file: ParsedFile, repo_root: Path) -> list[CodeChunk]:
    """
    Convert a ParsedFile into a list of searchable CodeChunks.

    Args:
        parsed_file: ParsedFile from Phase 3 AST parser.
        repo_root: Absolute path to repository root.

    Returns:
        List of CodeChunk objects.
    """
    abs_path = repo_root / parsed_file.relative_path
    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
    except OSError:
        return []

    chunks: list[CodeChunk] = []

    # Symbol-based chunking for AST symbols
    ast_symbols = [s for s in parsed_file.symbols if s.kind != SymbolKind.IMPORT]

    for sym in ast_symbols:
        snippet = extract_line_range(lines, sym.start_line, sym.end_line)
        if not snippet.strip():
            continue

        cid = build_chunk_id(parsed_file.relative_path, sym.start_line, sym.end_line, sym.name)
        chunks.append(
            CodeChunk(
                chunk_id=cid,
                relative_path=parsed_file.relative_path,
                language=parsed_file.language,
                start_line=sym.start_line,
                end_line=sym.end_line,
                code_content=snippet,
                symbol_name=sym.name,
                symbol_kind=sym.kind.value if isinstance(sym.kind, SymbolKind) else str(sym.kind),
                parent_name=sym.parent_name,
                signature=sym.signature,
                docstring=sym.docstring,
            )
        )

    # Fallback sliding-window chunking if no symbols were extracted (e.g. plain text / markdown / script)
    if not chunks and lines:
        window_size = 50
        step = 40
        total_lines = len(lines)
        for i in range(0, total_lines, step):
            start_l = i + 1
            end_l = min(i + window_size, total_lines)
            snippet = "\n".join(lines[i:end_l])
            if not snippet.strip():
                continue
            cid = build_chunk_id(parsed_file.relative_path, start_l, end_l)
            chunks.append(
                CodeChunk(
                    chunk_id=cid,
                    relative_path=parsed_file.relative_path,
                    language=parsed_file.language,
                    start_line=start_l,
                    end_line=end_l,
                    code_content=snippet,
                )
            )

    return chunks
