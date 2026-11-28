# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2147: el listado de costos enlaza al detalle del documento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ImportLandedCost, PurchaseInvoice, database


def test_listado_de_costos_enlaza_al_detalle(app, entorno_contable, authenticated_client):
    """Cada fila expone el endpoint de detalle con su identificador."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no=f"PI-LC-{suffix}",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        cost = ImportLandedCost(
            company="cacao",
            purchase_invoice_id=invoice.id,
            document_no=f"LC-{suffix}",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            grand_total=Decimal("10"),
        )
        database.session.add(cost)
        database.session.commit()
        cost_id = cost.id
        document_no = cost.document_no

    response = authenticated_client().get("/buying/import-landed-cost/list")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert document_no in html
    assert f"/buying/import-landed-cost/{cost_id}" in html
