# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1792: notas de compra/venta conservan endpoint y doctype al paginar."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import render_template
from sqlalchemy import select

from cacao_accounting.database import ApprovalRequest, User, database

FECHA = date(2026, 5, 15)
CASOS = (
    (
        "compras/factura_compra_devolucion_lista.html",
        "/buying/purchase-invoice/debit-note/list",
        "purchase_debit_note",
    ),
    (
        "compras/factura_compra_devolucion_lista.html",
        "/buying/purchase-invoice/credit-note/list",
        "purchase_credit_note",
    ),
    (
        "ventas/factura_venta_devolucion_lista.html",
        "/sales/sales-invoice/debit-note/list",
        "sales_debit_note",
    ),
    (
        "ventas/factura_venta_devolucion_lista.html",
        "/sales/sales-invoice/credit-note/list",
        "sales_credit_note",
    ),
    (
        "ventas/factura_venta_devolucion_lista.html",
        "/sales/sales-invoice/return/list",
        "sales_return",
    ),
)


class _Consulta:
    """Consulta paginada mínima para ejercitar el macro compartido."""

    def __init__(self, items):
        self.items = items
        self.page = 1
        self.pages = 2
        self.has_prev = False
        self.has_next = True
        self.prev_num = None
        self.next_num = 2
        self.total = len(items)
        self.per_per_page = 10
        self.period_extra_params = {}
        self.periods = []


@pytest.mark.parametrize("template_name,path,doctype", CASOS)
def test_paginacion_y_estado_usan_endpoint_y_doctype_reales(entorno_contable_aislado, template_name, path, doctype):
    """El enlace siguiente conserva la lista y el badge consulta la nota correcta."""
    app = entorno_contable_aislado.app
    document_id = f"DOC-1792-{uuid4().hex[:8]}"
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        database.session.add(
            ApprovalRequest(
                document_type=doctype,
                document_id=document_id,
                company_id="cacao",
                requested_by=admin.id,
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
        document = SimpleNamespace(
            id=document_id,
            document_no=f"NOTE-{doctype}",
            document_type=doctype,
            docstatus=0,
            posting_date=FECHA,
            supplier_name="Proveedor",
            customer_name="Cliente",
            transaction_currency="NIO",
            grand_total=Decimal("0"),
        )
        context = {
            "consulta": _Consulta([document]),
            "document_type": doctype,
            "new_document_type": doctype,
            "page_heading": "Listado de notas",
            "new_button_label": "Nueva nota",
            "page_caption": "Listado de notas.",
        }
        with app.test_request_context(path):
            html = render_template(template_name, **context)

    assert f"{path}?page=2" in html
    assert "Pendiente de Aprobación" in html
