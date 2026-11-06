#!/usr/bin/env python3
"""List Python audit candidates from tracked files; this does not assign coverage."""

import ast
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


class SymbolVisitor(ast.NodeVisitor):
    """Collect qualified definitions in source order, including nested definitions."""

    def __init__(self):
        """Initialize the definition list and lexical scope stack."""
        self.scope = []
        self.symbols = []

    def _definition(self, node, suffix):
        qualified = ".".join([*self.scope, node.name]) + suffix
        self.symbols.append((node.lineno, qualified))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Lambda(self, node):
        """Record lambda expressions with their containing scope."""
        line = node.lineno
        qualified = ".".join([*self.scope, f"lambda [línea {line}]"])
        self.symbols.append((line, qualified + "()"))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Record a class and traverse its methods and nested definitions."""
        self._definition(node, "")

    def visit_FunctionDef(self, node):
        """Record a function or method and traverse nested definitions."""
        self._definition(node, "()")

    visit_AsyncFunctionDef = visit_FunctionDef


def symbols(source, filename):
    """Parse source and distinguish repeated definitions by their source line."""
    visitor = SymbolVisitor()
    visitor.visit(ast.parse(source, filename=filename))
    counts = Counter(name for _, name in visitor.symbols)
    return [f"{name} [línea {line}]" if counts[name] > 1 else name for line, name in visitor.symbols]


def main():
    """Emit candidates as JSON, failing rather than silently skipping invalid files."""
    paths = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py"]).decode().split("\0")
    for path in filter(None, paths):
        if not path.startswith("cacao_accounting/") and not path.startswith("migrations/"):
            continue
        try:
            names = symbols(Path(path).read_text(encoding="utf-8"), path)
        except (SyntaxError, UnicodeError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            return 1
        print(json.dumps({"archivo": path, "símbolos": names}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
