"""
Parsing Configuration — Maps language names to Tree-sitter language grammars.

Supported languages in Phase 3:
- Python (.py)
- JavaScript (.js, .jsx, .mjs)
- TypeScript (.ts, .tsx)
"""

from typing import Any
import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript

# Cache of loaded Tree-sitter Language instances
_LANGUAGES: dict[str, tree_sitter.Language] = {}


def get_tree_sitter_language(language_name: str, extension: str = "") -> tree_sitter.Language | None:
    """
    Get the Tree-sitter Language object for a given language name and file extension.

    Args:
        language_name: Canonical language name (e.g. "Python", "JavaScript", "TypeScript")
        extension: Optional file extension to distinguish TypeScript (.ts) vs TSX (.tsx)

    Returns:
        tree_sitter.Language instance, or None if unsupported.
    """
    lang_key = language_name.lower()
    if extension.lower() in (".tsx", ".jsx"):
        lang_key = f"{lang_key}_tsx"

    if lang_key in _LANGUAGES:
        return _LANGUAGES[lang_key]

    try:
        if language_name.lower() == "python":
            lang = tree_sitter.Language(tree_sitter_python.language())
        elif language_name.lower() in ("javascript", "js"):
            if extension.lower() in (".jsx", ".tsx"):
                lang = tree_sitter.Language(tree_sitter_javascript.language())
            else:
                lang = tree_sitter.Language(tree_sitter_javascript.language())
        elif language_name.lower() in ("typescript", "ts"):
            if extension.lower() == ".tsx":
                lang = tree_sitter.Language(tree_sitter_typescript.language_tsx())
            else:
                lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        else:
            return None

        _LANGUAGES[lang_key] = lang
        return lang
    except Exception:
        return None


# Supported language names for easy checking
SUPPORTED_PARSING_LANGUAGES: set[str] = {"Python", "JavaScript", "TypeScript"}
