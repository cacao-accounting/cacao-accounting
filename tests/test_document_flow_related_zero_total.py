# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1555: la lista de documentos relacionados distingue cero de campo ausente."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from flask import render_template

SPEC = SimpleNamespace(
    key="sales_order",
    label="Orden de venta",
    date_field="posting_date",
    party_field=None,
    total_field="grand_total",
    detail_endpoint=None,
    detail_arg="id",
)


def _render(app, total):
    """Renderiza la plantilla real con un documento y su total."""
    document = SimpleNamespace(
        id="so-1",
        document_no="SO-1",
        docstatus=0,
        status=None,
        posting_date="2026-05-15",
        grand_total=total,
    )
    with app.test_request_context("/document-flow/list/sales_order"):
        return render_template(
            "document_flow_related_list.html",
            spec=SPEC,
            documents=[document],
            related_doctype="",
            related_id="",
            related_no="",
            related_label="",
            titulo="Documentos relacionados",
        )


def test_total_cero_se_muestra_como_importe(app):
    """Un total válido de cero no se confunde con un campo ausente."""
    html = _render(app, Decimal("0"))

    assert "<td>0</td>" in html


def test_total_ausente_se_muestra_vacio(app):
    """Solo el valor None deja la celda vacía."""
    html = _render(app, None)

    assert "<td></td>" in html
