"""Behavioral checks for Python audit-candidate extraction."""

import unittest

from audit_python_symbols import symbols


class SymbolExtractionTests(unittest.TestCase):
    """Definitions must remain distinguishable across scopes and redefinitions."""

    def test_scopes_async_and_redefinitions(self):
        source = """
class Invoice:
    def total(self):
        def normalize(value):
            return value
        return normalize(1)
    @property
    def status(self):
        return 1
    @status.setter
    def status(self, value):
        pass
async def save():
    pass
"""
        self.assertEqual(
            symbols(source, "example.py"),
            [
                "Invoice",
                "Invoice.total()",
                "Invoice.total.normalize()",
                "Invoice.status() [línea 8]",
                "Invoice.status() [línea 11]",
                "save()",
            ],
        )

    def test_invalid_source_is_not_silently_accepted(self):
        with self.assertRaises(SyntaxError):
            symbols("def broken(:", "broken.py")


if __name__ == "__main__":
    unittest.main()
