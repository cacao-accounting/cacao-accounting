# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1555: los listados de ventas muestran totales cero."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import render_template


class _Consulta:
    def __init__(self, items):
        self.items = items
        self.page = 1
        self.pages = 1
        self.has_prev = False
        self.has_next = False
        self.prev_num = None
        self.next_num = None
        self.total = len(items)
        self.per_page = 25
        self.period_extra_params = {}

    def iter_pages(self, *args, **kwargs):
        del args, kwargs
        return [1]


CASES = [
    ("ventas/solicitud_venta_lista.html", "/sales/sales-request/list", {"document_no": "SR-0"}),
    ("ventas/cotizacion_lista.html", "/sales/quotation/list", {"document_no": "SQ-0"}),
    ("ventas/orden_venta_lista.html", "/sales/sales-order/list", {"document_no": "SO-0"}),
    ("ventas/entrega_lista.html", "/sales/delivery-note/list", {"document_no": "DN-0"}),
    ("ventas/factura_venta_lista.html", "/sales/sales-invoice/list", {"document_no": "SI-0"}),
    (
        "ventas/factura_venta_devolucion_lista.html",
        "/sales/sales-invoice/credit-note/list",
        {"document_no": "SCN-0", "document_type": "sales_credit_note"},
    ),
]


@pytest.mark.parametrize(("template_name", "path", "extra"), CASES)
def test_listados_ventas_muestran_total_cero(app, template_name, path, extra):
    document = SimpleNamespace(
        id="doc-1",
        docstatus=0,
        status=None,
        posting_date="2026-05-15",
        customer_name="Cliente",
        transaction_currency="NIO",
        grand_total=Decimal("0"),
        **extra,
    )
    consulta = _Consulta([document])
    context = {"consulta": consulta, "docstatus": None}
    if template_name.endswith("factura_venta_devolucion_lista.html"):
        context.update(
            {
                "page_heading": "Listado de Notas de Crédito de Venta",
                "new_document_type": "sales_credit_note",
                "new_button_label": "Nueva Nota de Crédito",
                "page_caption": "Listado de notas de crédito de venta.",
                "list_endpoint": "ventas.ventas_factura_venta_devolucion_lista",
                "document_type": "sales_credit_note",
            }
        )
    with app.test_request_context(path):
        html = render_template(template_name, **context)

    assert "NIO 0.00" in html
