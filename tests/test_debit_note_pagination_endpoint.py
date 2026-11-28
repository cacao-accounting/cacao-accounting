# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2050: las notas de débito paginan sobre su propio listado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import re
from uuid import uuid4

import pytest

from cacao_accounting.database import ApprovalRequest, SalesInvoice, database

pytestmark = pytest.mark.usefixtures("entorno_contable")


def test_lista_de_nota_debito_conserva_paginacion_y_estado(app, authenticated_client, reference_users):
    """La lista conserva endpoint y calcula la aprobación usando su subtipo."""
    suffix = uuid4().hex[:8]
    document_prefix = f"ND-2050-{suffix}"
    with app.app_context():
        for indice in range(11):
            invoice = SalesInvoice(
                company="cacao",
                document_type="sales_debit_note",
                document_no=f"{document_prefix}-{indice}",
                posting_date=date(2026, 5, 15),
                customer_name="Cliente",
                transaction_currency="NIO",
                grand_total=Decimal("10"),
                total=Decimal("10"),
                outstanding_amount=Decimal("10"),
            )
            database.session.add(invoice)
            database.session.flush()
            database.session.add(
                ApprovalRequest(
                    document_type="sales_debit_note",
                    document_id=invoice.id,
                    company_id="cacao",
                    requested_by=reference_users["admin"].id,
                    status="Pending Approval",
                )
            )
        database.session.commit()

    try:
        html = authenticated_client("admin").get("/sales/sales-invoice/debit-note/list").get_data(as_text=True)
        html = html.replace("&amp;", "&")

        assert "/sales/sales-invoice/debit-note/list?page=2" in html
        assert "/sales/sales-invoice/return/list" not in html
        assert any(
            re.search(
                rf"{re.escape(document_prefix)}-{indice}(?:(?!</tr>).)*Pendiente de Aprobación(?:(?!</tr>).)*</tr>",
                html,
                re.DOTALL,
            )
            for indice in range(11)
        )
    finally:
        with app.app_context():
            invoice_ids = database.select(SalesInvoice.id).where(SalesInvoice.document_no.like(f"{document_prefix}-%"))
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.document_id.in_(invoice_ids)))
            database.session.execute(
                database.delete(SalesInvoice).where(SalesInvoice.document_no.like(f"{document_prefix}-%"))
            )
            database.session.commit()
