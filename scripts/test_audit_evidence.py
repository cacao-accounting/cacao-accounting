"""Tests for historical audit evidence lookup."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from audit_evidence import DOCUMENTS, collect_evidence, partial_symbol_evidence


class EvidenceTests(unittest.TestCase):
    """Evidence must be attributed to exact paths without inferring status."""

    def test_references_and_content_hash_are_reported_without_promoting_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a").mkdir()
            (root / "a/thing.py").write_text("value = 1\n", encoding="utf-8")
            digest = hashlib.sha256((root / "a/thing.py").read_bytes()).hexdigest()
            for document in DOCUMENTS:
                (root / document).write_text("", encoding="utf-8")
            (root / DOCUMENTS[0]).write_text(
                f"| `a/thing.py` | Revisado parcialmente; SHA `{digest}` | Parcial |\n"
                "| `b/thing.py` | Revisado completamente | Completo |\n",
                encoding="utf-8",
            )
            result = list(collect_evidence(root, ["a/thing.py"]))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["línea"], 1)
            self.assertTrue(result[0]["sha256_coincide"])
            self.assertNotIn("estado", result[0])

    def test_missing_and_mismatched_files_do_not_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for document in DOCUMENTS:
                (root / document).write_text("", encoding="utf-8")
            (root / DOCUMENTS[0]).write_text("`missing.py` `" + "0" * 64 + "`\n", encoding="utf-8")
            result = list(collect_evidence(root, ["missing.py"]))
            self.assertFalse(result[0]["sha256_coincide"])
            self.assertIsNone(result[0]["sha256_actual"])

    def test_symbol_evidence_requires_explicit_review_and_unambiguous_hash(self):
        entry = {
            "texto": "`check()` revisada; falta validar errores",
            "sha256_mencionados": ["a" * 64],
            "sha256_coincide": True,
        }
        self.assertIs(partial_symbol_evidence("check()", [entry]), entry)
        self.assertIsNone(partial_symbol_evidence("other()", [entry]))
        self.assertIsNone(partial_symbol_evidence("check()", [{**entry, "texto": "`check()` pendiente de revisión"}]))
        self.assertIsNone(partial_symbol_evidence("check()", [{**entry, "sha256_coincide": False}]))
        self.assertIsNone(partial_symbol_evidence("check()", [{**entry, "sha256_mencionados": ["a" * 64, "b" * 64]}]))


if __name__ == "__main__":
    unittest.main()
