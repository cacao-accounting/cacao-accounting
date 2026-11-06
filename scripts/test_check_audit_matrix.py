"""Checks for matrix validation and derived coverage."""

import unittest
from unittest.mock import patch

from check_audit_matrix import HEADER, check, metrics


def row(path, name, state="Pendiente"):
    """Make one complete audit row."""
    return dict(zip(HEADER, [path, name, state, "Falta revisión"]))


class MatrixChecks(unittest.TestCase):
    """Reject stale, missing, invented and duplicated entries."""

    @patch("check_audit_matrix.expected", return_value=["uno()", "dos()"])
    def test_detects_inventory_drift(self, _expected):
        good = [row("a.py", "uno()"), row("a.py", "dos()")]
        self.assertEqual(check(good, ["a.py"]), [])
        for bad in (good[:1], good + [good[0]], [good[0], row("a.py", "inventado()")], good + [row("b.py", "x")]):
            self.assertTrue(check(bad, ["a.py"]))

    @patch("check_audit_matrix.expected", return_value=["uno()"])
    def test_rejects_unknown_state_and_derives_coverage(self, _expected):
        self.assertTrue(check([row("a.py", "uno()", "fixed")], ["a.py"]))
        result = metrics([row("a.py", "uno()", "Completo"), row("b.py", "dos()")])
        self.assertEqual(result["porcentaje_completo"], 50)
        self.assertEqual(result["archivos_completos"], ["a.py"])


class VerificationGaps(unittest.TestCase):
    """The checker must expose units it cannot inspect and invalid issue links."""

    @patch("check_audit_matrix.expected", return_value=["componente Alpine: análisis JS pendiente"])
    def test_unparsed_javascript_is_an_error(self, _expected):
        errors = check([row("a.html", "componente Alpine: análisis JS pendiente")], ["a.html"])
        self.assertTrue(any("JavaScript pendiente" in error for error in errors))

    @patch("check_audit_matrix.subprocess.run")
    def test_missing_issue_is_reported(self, run):
        from check_audit_matrix import check_issues

        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "not found"
        item = row("a.py", "f()")
        item["Comentarios"] = "Falta validar; #123"
        self.assertIn("#123", check_issues([item])[0])


if __name__ == "__main__":
    unittest.main()
