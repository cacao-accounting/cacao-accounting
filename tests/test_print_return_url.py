"""#1923: la URL de retorno de la vista previa debe ser interna y segura."""

from __future__ import annotations

from flask import url_for

from cacao_accounting.printing.routes import _safe_return_url


def test_safe_return_url_accepts_internal_paths(app):
    with app.test_request_context("/"):
        home = url_for("cacao_app.pagina_inicio")
        assert _safe_return_url(None) == home
        assert _safe_return_url("") == home
        assert _safe_return_url("/sales/invoice/INV-1") == "/sales/invoice/INV-1"
        assert _safe_return_url("/print/x/1/preview?tab=1") == "/print/x/1/preview?tab=1"


def test_safe_return_url_rejects_external_and_manipulated_destinations(app):
    with app.test_request_context("/"):
        home = url_for("cacao_app.pagina_inicio")
        unsafe_values = [
            "//evil.example/path",
            "/\\evil.example/path",
            "/%5cevil.example/path",
            "/%5Cevil.example/path",
            "https://evil.example/path",
            "javascript:alert(1)",
            "/\x00evil",
            "/path\nInjected: x",
        ]
        for value in unsafe_values:
            assert _safe_return_url(value) == home, value
