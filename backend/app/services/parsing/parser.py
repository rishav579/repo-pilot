"""
Code Parser Service — Extracts structured AST symbols using Tree-sitter.

This service reads source code files and builds Abstract Syntax Trees (ASTs) using
Tree-sitter to extract:
- Functions and methods (with signatures, parent class names, and line ranges)
- Classes and Interfaces (with line ranges)
- Imports (module names and import statements)
- Syntax error flags (if code is malformed)

HOW IT WORKS:
    1. Check if the language is supported (Python, JavaScript, TypeScript)
    2. Get the Tree-sitter Parser and Language grammar object
    3. Parse source code bytes into an AST
    4. Walk AST nodes recursively to find definitions
    5. Extract names, line numbers (1-indexed), signatures, docstrings, and parent relationships
    6. Return a typed ParsedFile model
"""

import os
from pathlib import Path
import tree_sitter

from app.services.ingestion.scanner import scan_repository
from app.services.parsing.config import get_tree_sitter_language
from app.services.parsing.models import (
    ParsedFile,
    ParseResult,
    ParseSummary,
    SymbolInfo,
    SymbolKind,
)


class ParserError(Exception):
    """Raised when parsing fails due to missing files or unresolvable paths."""

    pass


def node_text(node: tree_sitter.Node, code_bytes: bytes) -> str:
    """Extract string content of a Tree-sitter AST node from the source bytes."""
    return code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def check_syntax_errors(node: tree_sitter.Node) -> bool:
    """Recursively check if an AST subtree contains syntax error nodes."""
    if node.is_error or node.type == "ERROR":
        return True
    for child in node.children:
        if check_syntax_errors(child):
            return True
    return False


def extract_python_symbols(
    root_node: tree_sitter.Node, code_bytes: bytes
) -> tuple[list[SymbolInfo], list[str]]:
    """
    Extract symbols from a Python AST.

    Identifies:
    - function_definition -> Function or Method (if inside class)
    - class_definition -> Class
    - import_statement / import_from_statement -> Import
    """
    symbols: list[SymbolInfo] = []
    imports: list[str] = []

    lines = code_bytes.decode("utf-8", errors="replace").splitlines()

    def get_line_snippet(start_line: int) -> str:
        if 1 <= start_line <= len(lines):
            return lines[start_line - 1].strip()
        return ""

    def extract_docstring(body_node: tree_sitter.Node) -> str | None:
        """Extract first docstring inside block if present."""
        if not body_node:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw = node_text(sub, code_bytes).strip()
                        # Strip surrounding quotes (""" or ''')
                        for quote in ('"""', "'''", '"', "'"):
                            if raw.startswith(quote) and raw.endswith(quote) and len(raw) >= 2 * len(quote):
                                return raw[len(quote) : -len(quote)].strip()
                        return raw
                break
        return None

    def visit(node: tree_sitter.Node, current_class: str | None = None):
        nonlocal symbols, imports

        for child in node.children:
            ntype = child.type

            if ntype == "function_definition":
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)
                body_node = child.child_by_field_name("body")
                doc = extract_docstring(body_node)

                kind = SymbolKind.METHOD if current_class else SymbolKind.FUNCTION

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=kind,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        docstring=doc,
                        parent_name=current_class,
                    )
                )

                # Recursively visit function body (e.g., nested functions)
                if body_node:
                    visit(body_node, current_class=current_class)

            elif ntype == "class_definition":
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)
                body_node = child.child_by_field_name("body")
                doc = extract_docstring(body_node)

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        docstring=doc,
                        parent_name=current_class,
                    )
                )

                # Visit class body to extract methods
                if body_node:
                    visit(body_node, current_class=name)

            elif ntype in ("import_statement", "import_from_statement"):
                imp_text = node_text(child, code_bytes).strip()
                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1

                imports.append(imp_text)
                symbols.append(
                    SymbolInfo(
                        name=imp_text,
                        kind=SymbolKind.IMPORT,
                        start_line=start_line,
                        end_line=end_line,
                        signature=imp_text,
                    )
                )
            else:
                # Recurse into other nodes (statements, try blocks, etc.)
                visit(child, current_class=current_class)

    visit(root_node)
    return symbols, imports


def extract_js_ts_symbols(
    root_node: tree_sitter.Node, code_bytes: bytes
) -> tuple[list[SymbolInfo], list[str]]:
    """
    Extract symbols from a JavaScript or TypeScript AST.

    Identifies:
    - function_declaration -> Function
    - method_definition -> Method (inside class)
    - class_declaration -> Class
    - interface_declaration -> Interface (TypeScript)
    - lexical_declaration (const foo = () => {}) -> Function
    - import_statement -> Import
    """
    symbols: list[SymbolInfo] = []
    imports: list[str] = []

    lines = code_bytes.decode("utf-8", errors="replace").splitlines()

    def get_line_snippet(start_line: int) -> str:
        if 1 <= start_line <= len(lines):
            return lines[start_line - 1].strip()
        return ""

    def visit(node: tree_sitter.Node, current_class: str | None = None):
        nonlocal symbols, imports

        for child in node.children:
            ntype = child.type

            if ntype in ("function_declaration", "generator_function_declaration"):
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)
                body_node = child.child_by_field_name("body")

                kind = SymbolKind.METHOD if current_class else SymbolKind.FUNCTION

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=kind,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        parent_name=current_class,
                    )
                )
                if body_node:
                    visit(body_node, current_class=current_class)

            elif ntype == "method_definition":
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)
                body_node = child.child_by_field_name("body")

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=SymbolKind.METHOD,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        parent_name=current_class,
                    )
                )
                if body_node:
                    visit(body_node, current_class=current_class)

            elif ntype == "class_declaration":
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)
                body_node = child.child_by_field_name("body")

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        parent_name=current_class,
                    )
                )
                if body_node:
                    visit(body_node, current_class=name)

            elif ntype == "interface_declaration":
                name_node = child.child_by_field_name("name")
                name = node_text(name_node, code_bytes) if name_node else "anonymous"

                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                sig = get_line_snippet(start_line)

                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=SymbolKind.INTERFACE,
                        start_line=start_line,
                        end_line=end_line,
                        signature=sig,
                        parent_name=current_class,
                    )
                )

            elif ntype == "import_statement":
                imp_text = node_text(child, code_bytes).strip()
                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1

                imports.append(imp_text)
                symbols.append(
                    SymbolInfo(
                        name=imp_text,
                        kind=SymbolKind.IMPORT,
                        start_line=start_line,
                        end_line=end_line,
                        signature=imp_text,
                    )
                )

            elif ntype in ("lexical_declaration", "variable_declaration"):
                # Handle const foo = () => {} or const bar = function() {}
                for decl in child.children:
                    if decl.type == "variable_declarator":
                        val = decl.child_by_field_name("value")
                        if val and val.type in ("arrow_function", "function_expression", "function"):
                            name_node = decl.child_by_field_name("name")
                            if name_node:
                                name = node_text(name_node, code_bytes)
                                start_line = child.start_point[0] + 1
                                end_line = child.end_point[0] + 1
                                sig = get_line_snippet(start_line)

                                kind = SymbolKind.METHOD if current_class else SymbolKind.FUNCTION
                                symbols.append(
                                    SymbolInfo(
                                        name=name,
                                        kind=kind,
                                        start_line=start_line,
                                        end_line=end_line,
                                        signature=sig,
                                        parent_name=current_class,
                                    )
                                )
                visit(child, current_class=current_class)

            else:
                visit(child, current_class=current_class)

    visit(root_node)
    return symbols, imports


def parse_source_code(
    code_bytes: bytes, language_name: str, relative_path: str = ""
) -> tuple[list[SymbolInfo], list[str], bool]:
    """
    Parse source code bytes using Tree-sitter and return extracted symbols, imports, and syntax error flag.

    Args:
        code_bytes: Raw source code content in bytes.
        language_name: Name of language ("Python", "JavaScript", "TypeScript").
        relative_path: File path (used to check extension like .tsx).

    Returns:
        tuple (symbols, imports, has_syntax_errors)
    """
    ext = Path(relative_path).suffix.lower() if relative_path else ""
    ts_lang = get_tree_sitter_language(language_name, extension=ext)

    if not ts_lang:
        # Language unsupported for AST parsing
        return [], [], False

    parser = tree_sitter.Parser(ts_lang)
    tree = parser.parse(code_bytes)

    has_errors = check_syntax_errors(tree.root_node)

    lang_lower = language_name.lower()
    if lang_lower == "python":
        symbols, imports = extract_python_symbols(tree.root_node, code_bytes)
    elif lang_lower in ("javascript", "typescript", "js", "ts"):
        symbols, imports = extract_js_ts_symbols(tree.root_node, code_bytes)
    else:
        symbols, imports = [], []

    return symbols, imports, has_errors


def parse_file(file_path: Path, repo_root: Path, language_name: str) -> ParsedFile:
    """
    Read and parse a single file from disk.

    Args:
        file_path: Absolute path to source file.
        repo_root: Absolute path to repository root.
        language_name: Language name (e.g. "Python").

    Returns:
        ParsedFile object populated with extracted symbols.
    """
    relative_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

    try:
        code_bytes = file_path.read_bytes()
    except OSError:
        code_bytes = b""

    symbols, imports, has_errors = parse_source_code(
        code_bytes, language_name, relative_path=relative_path
    )

    return ParsedFile(
        relative_path=relative_path,
        language=language_name,
        symbols=symbols,
        imports=imports,
        total_symbols=len(symbols),
        has_syntax_errors=has_errors,
    )


def parse_repository(
    repo_path: str, relative_paths: list[str] | None = None
) -> ParseResult:
    """
    Integrate ingestion scanning with Tree-sitter code parsing.

    Discovers source files using the Phase 2 ingestion scanner, then parses all
    included source files matching supported languages (Python, JavaScript, TypeScript).

    Args:
        repo_path: Path to local repository root.
        relative_paths: Optional list of specific relative paths to parse (if None, parses all).

    Returns:
        ParseResult containing summary and parsed file details.
    """
    scan_res = scan_repository(repo_path, require_git=False)
    repo_root = Path(scan_res.summary.repository_path)

    parsed_files: list[ParsedFile] = []
    languages_parsed: dict[str, int] = {}
    total_symbols = 0

    target_files = scan_res.files
    if relative_paths is not None:
        rel_set = set(relative_paths)
        target_files = [f for f in target_files if f.relative_path in rel_set]

    for file_info in target_files:
        if file_info.is_excluded or not file_info.language:
            continue

        if file_info.language not in ("Python", "JavaScript", "TypeScript"):
            continue

        abs_file_path = repo_root / file_info.relative_path
        parsed_file = parse_file(abs_file_path, repo_root, file_info.language)

        parsed_files.append(parsed_file)
        total_symbols += parsed_file.total_symbols
        languages_parsed[file_info.language] = (
            languages_parsed.get(file_info.language, 0) + 1
        )

    return ParseResult(
        repository_path=str(repo_root),
        files_parsed=len(parsed_files),
        total_symbols_extracted=total_symbols,
        languages_parsed=languages_parsed,
        files=parsed_files,
    )
