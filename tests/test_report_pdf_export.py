# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para la exportación PDF server-side de reportes (issue #769).

Cubre:
1. ``pdf`` es un formato de exportación aceptado por reportes financieros y
   operacionales (además de ``csv`` y ``xlsx``).
2. La disponibilidad de PDF se deriva del modo de ejecución: no se ofrece en el
   modo desktop (dónde WeasyPrint y sus dependencias nativas no están
   garantizadas), y se ofrece en el modo cloud.
3. Solicitar ``export=pdf`` en un despliegue sin soporte devuelve HTTP 400 con
   un mensaje claro en lugar de romper la página, dejando XLSX/CSV como
   alternativa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from werkzeug.exceptions import BadRequest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.reportes import helpers


class _FakeRow:
    """Fila mínima compatible con la interfaz de rows de un reporte."""

    def __init__(self, values: dict[str, object]) -> None:
        self.values = values


class _FakeReport:
    """Reporte mínimo con la superficie usada por el exportador."""

    def __init__(self) -> None:
        self.rows = [_FakeRow({"posting_date": date(2026, 5, 1), "debit": Decimal("10")})]
        self.columns = ["posting_date", "debit"]
        self.totals: dict[str, object] = {}
        self.ledger_currency = "NIO"
        self.total_rows = 1
        self.page = 1
        self.page_size = 100


def _make_app(desktop: bool):
    """Aplica de prueba con o sin el modo escritorio."""
    extra = {"MODO_ESCRITORIO": True} if desktop else {}
    app = create_app(
        {
            **configuracion,
            **extra,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    return app


def _filters(app):
    from cacao_accounting.reportes.services import FinancialReportFilters

    return FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-05")


def test_pdf_is_an_accepted_export_format():
    """El set de formatos aceptados incluye PDF."""
    assert "pdf" in helpers._SUPPORTED_EXPORT_FORMATS
    assert helpers._SUPPORTED_EXPORT_FORMATS == {"csv", "xlsx", "pdf"}


def test_pdf_support_reflects_desktop_mode():
    """PDF se considera no disponible en desktop y disponible en cloud."""
    with _make_app(desktop=True).app_context():
        assert helpers._pdf_support_available() is False
    with _make_app(desktop=False).app_context():
        assert helpers._pdf_support_available() is True


@pytest.mark.parametrize("export_fn", ["_export_operational_report", "_export_financial_report"])
def test_pdf_export_aborts_in_unsupported_mode(export_fn):
    """En un despliegue sin soporte, export=pdf devuelve HTTP 400."""
    app = _make_app(desktop=True)
    report = _FakeReport()
    with app.test_request_context("/reports/report?export=pdf"):
        with pytest.raises(BadRequest):
            if export_fn == "_export_operational_report":
                helpers._export_operational_report(report, "op1", "Título", {"company": "cacao"})
            else:
                helpers._export_financial_report(report, "fin1", "Título", _filters(app))


@pytest.mark.parametrize("export_fn", ["_export_operational_report", "_export_financial_report"])
def test_csv_and_xlsx_export_still_work(export_fn):
    """CSV y XLSX continúan exportando en modo desktop (alternativa al PDF)."""
    app = _make_app(desktop=True)
    report = _FakeReport()
    with app.test_request_context("/reports/report?export=csv"):
        if export_fn == "_export_operational_report":
            response = helpers._export_operational_report(report, "op1", "Título", {"company": "cacao"})
        else:
            response = helpers._export_financial_report(report, "fin1", "Título", _filters(app))
        assert response is not None
        assert response.mimetype == "text/csv"

    with app.test_request_context("/reports/report?export=xlsx"):
        if export_fn == "_export_operational_report":
            response = helpers._export_operational_report(report, "op1", "Título", {"company": "cacao"})
        else:
            response = helpers._export_financial_report(report, "fin1", "Título", _filters(app))
        assert response is not None
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
