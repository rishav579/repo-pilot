"""
Tests for Code Parser Service (Tree-sitter AST extraction).

Tests cover:
- Python functions, classes, nested methods, imports, docstrings, line numbers
- JavaScript functions, classes, arrow functions, imports
- TypeScript functions, interfaces, classes, TSX
- Malformed source code (syntax errors detected without crashing)
- Unsupported languages
- Line number accuracy
"""

import pytest

from app.services.parsing.models import SymbolKind
from app.services.parsing.parser import parse_repository, parse_source_code


class TestPythonParsing:
    """Tests for Python source code parsing."""

    def test_python_functions_and_docstrings(self):
        code = b'''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def greet(name: str):
    print("Hello", name)
'''
        symbols, imports, has_errors = parse_source_code(code, "Python", "test.py")

        assert has_errors is False
        funcs = [s for s in symbols if s.kind == SymbolKind.FUNCTION]
        assert len(funcs) == 2

        f1 = funcs[0]
        assert f1.name == "add"
        assert f1.start_line == 2
        assert f1.end_line == 4
        assert f1.docstring == "Add two numbers."
        assert "def add" in f1.signature

        f2 = funcs[1]
        assert f2.name == "greet"
        assert f2.start_line == 6
        assert f2.end_line == 7

    def test_python_class_and_methods(self):
        code = b'''
class Calculator:
    """Simple calculator class."""

    def __init__(self):
        self.val = 0

    def add(self, x: int):
        self.val += x
'''
        symbols, imports, has_errors = parse_source_code(code, "Python", "calc.py")

        assert has_errors is False

        classes = [s for s in symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) == 1
        c = classes[0]
        assert c.name == "Calculator"
        assert c.docstring == "Simple calculator class."

        methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
        assert len(methods) == 2
        m_names = [m.name for m in methods]
        assert "__init__" in m_names
        assert "add" in m_names

        # Check parent relationship
        for m in methods:
            assert m.parent_name == "Calculator"

    def test_python_imports(self):
        code = b'''
import os
import sys
from pathlib import Path
from app.models import SymbolInfo
'''
        symbols, imports, has_errors = parse_source_code(code, "Python", "imports.py")

        assert has_errors is False
        assert len(imports) == 4
        assert "import os" in imports
        assert "from pathlib import Path" in imports

        import_symbols = [s for s in symbols if s.kind == SymbolKind.IMPORT]
        assert len(import_symbols) == 4


class TestJavaScriptParsing:
    """Tests for JavaScript source code parsing."""

    def test_js_functions_and_classes(self):
        code = b'''
import { useState } from 'react';

function calculateTotal(items) {
    return items.reduce((acc, item) => acc + item.price, 0);
}

const formatCurrency = (amount) => {
    return `$${amount}`;
};

class ShoppingCart {
    addItem(item) {
        this.items.push(item);
    }
}
'''
        symbols, imports, has_errors = parse_source_code(code, "JavaScript", "cart.js")

        assert has_errors is False
        assert len(imports) == 1
        assert "import { useState }" in imports[0]

        funcs = [s for s in symbols if s.kind == SymbolKind.FUNCTION]
        func_names = [f.name for f in funcs]
        assert "calculateTotal" in func_names
        assert "formatCurrency" in func_names

        classes = [s for s in symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) == 1
        assert classes[0].name == "ShoppingCart"

        methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
        assert len(methods) == 1
        assert methods[0].name == "addItem"
        assert methods[0].parent_name == "ShoppingCart"


class TestTypeScriptParsing:
    """Tests for TypeScript source code parsing."""

    def test_ts_functions_interfaces_classes(self):
        code = b'''
import { Component } from 'react';

export interface User {
    id: number;
    name: string;
}

export function getUserName(user: User): string {
    return user.name;
}

export class UserService {
    private users: User[] = [];

    public addUser(user: User): void {
        this.users.push(user);
    }
}
'''
        symbols, imports, has_errors = parse_source_code(code, "TypeScript", "user.ts")

        assert has_errors is False

        interfaces = [s for s in symbols if s.kind == SymbolKind.INTERFACE]
        assert len(interfaces) == 1
        assert interfaces[0].name == "User"

        funcs = [s for s in symbols if s.kind == SymbolKind.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].name == "getUserName"

        classes = [s for s in symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
        assert len(methods) == 1
        assert methods[0].name == "addUser"
        assert methods[0].parent_name == "UserService"


class TestEdgeCasesAndErrors:
    """Tests for syntax errors, unsupported languages, and line accuracy."""

    def test_malformed_code(self):
        """Malformed code should flag syntax errors but still extract valid symbols."""
        code = b'''
def valid_func():
    return True

def broken_func(
    print("missing closing paren")
'''
        symbols, imports, has_errors = parse_source_code(code, "Python", "broken.py")

        assert has_errors is True
        funcs = [s for s in symbols if s.kind == SymbolKind.FUNCTION]
        assert len(funcs) >= 1
        assert funcs[0].name == "valid_func"

    def test_unsupported_language(self):
        """Unsupported languages should return empty lists without crashing."""
        code = b"fn main() { println!(\"Hello\"); }"
        symbols, imports, has_errors = parse_source_code(code, "Rust", "main.rs")

        assert symbols == []
        assert imports == []
        assert has_errors is False

    def test_line_number_accuracy(self):
        """Line numbers must match 1-indexed source line positions exactly."""
        code = b'''# Line 1: comment

def target_func():
    pass

# Line 7: another comment
'''
        symbols, imports, has_errors = parse_source_code(code, "Python", "lines.py")

        funcs = [s for s in symbols if s.kind == SymbolKind.FUNCTION]
        assert len(funcs) == 1
        f = funcs[0]
        assert f.name == "target_func"
        assert f.start_line == 3
        assert f.end_line == 4


class TestRepositoryParsingIntegration:
    """Tests for full repository parsing integration."""

    def test_parse_sample_repo(self, sample_repo):
        """Parsing a repo should scan and parse supported source files."""
        result = parse_repository(str(sample_repo))

        assert result.files_parsed > 0
        assert result.total_symbols_extracted > 0
        assert "Python" in result.languages_parsed or "TypeScript" in result.languages_parsed
