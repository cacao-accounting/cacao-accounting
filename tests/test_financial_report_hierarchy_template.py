# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El reporte financiero entrega al árbol DOM las relaciones correctas."""

from __future__ import annotations

import re

from flask import render_template

from cacao_accounting.reportes.helpers import _build_display_rows, _build_row_metadata, _group_rows_by_field
from cacao_accounting.reportes.services import FinancialReportFilters


def _render_financial_report(app, display_rows: list[dict], report_code: str = "trial-balance"):
    """Renderiza la tabla financiera con un conjunto de filas ya preparado."""
    filters = FinancialReportFilters(company="cacao")
    with app.test_request_context("/reports/trial-balance"):
        return render_template(
            "reportes/financial_report.html",
            titulo="Balance de comprobación",
            report_title="Balance de comprobación",
            report_code=report_code,
            report_filters=filters,
            period_from="",
            period_to="",
            period_from_label="",
            period_to_label="",
            context_summary={"company": "cacao", "ledger": "", "period": "", "status": "", "records": 2},
            unclassified_warning=None,
            pdf_supported=False,
            group_by="",
            columns=["account_code"],
            display_headers={"account_code": "Cuenta"},
            right_align_columns=set(),
            display_rows=display_rows,
            totals={},
        )


def test_template_financiero_renderiza_seccion_drilldown_y_script_tree(app):
    """La página conserva la sección, el enlace de cuenta y el script del árbol."""
    source_rows = [
        {"section": "balance", "account_code": "1", "account_name": "Activos"},
        {"section": "balance", "account_code": "1.1", "account_name": "Caja"},
    ]
    filters = FinancialReportFilters(company="cacao")
    with app.app_context(), app.test_request_context("/reports/trial-balance"):
        row_metadata = _build_row_metadata(source_rows, filters)
        display_rows = _build_display_rows(source_rows, row_metadata, ["account_code"], None)
        html = _render_financial_report(app, display_rows)

    assert 'data-tree-section="balance"' in html
    assert re.search(r'<a href="[^"]*account_code=1">1</a>', html)
    assert 'src="/static/js/financial-report-tree.js"' in html


def test_reporte_agrupado_renderiza_ambitos_de_arbol_independientes(app):
    """El mismo padre e hijo en dos grupos reciben scopes diferentes."""
    source_rows = [
        {"account_code": "1", "account_name": "Activos", "segment": "Norte"},
        {"account_code": "1.1", "account_name": "Caja", "segment": "Norte"},
        {"account_code": "1", "account_name": "Activos", "segment": "Sur"},
        {"account_code": "1.1", "account_name": "Caja", "segment": "Sur"},
    ]
    filters = FinancialReportFilters(company="cacao")
    with app.app_context(), app.test_request_context("/reports/account-movement"):
        row_metadata = _build_row_metadata(source_rows, filters)
        display_rows = _build_display_rows(source_rows, row_metadata, ["account_code"], None)
        grouped_rows = _group_rows_by_field(display_rows, source_rows, "segment", None)
        html = _render_financial_report(app, grouped_rows, report_code="account-movement")

    assert html.count('data-tree-section="group-0"') == 2
    assert html.count('data-tree-section="group-1"') == 2
