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
    with app.app_context():
        invoices = []
        for indice in range(11):
            invoices.append(
                SalesInvoice(
                    company="cacao",
                    document_type="sales_debit_note",
                    document_no=f"ND-2050-{suffix}-{indice}",
                    posting_date=date(2026, 5, 15),
                    customer_name="Cliente",
                    transaction_currency="NIO",
                    grand_total=Decimal("10"),
                    total=Decimal("10"),
                    outstanding_amount=Decimal("10"),
                )
            )
        database.session.add_all(invoices)
        database.session.flush()
        approval = ApprovalRequest(
            document_type="sales_debit_note",
            document_id=invoices[0].id,
            company_id="cacao",
            requested_by=reference_users["admin"].id,
            status="Pending Approval",
        )
        database.session.add(approval)
        database.session.commit()
        invoice_ids = [invoice.id for invoice in invoices]
        approval_id = approval.id
        pending_invoice_no = invoices[0].document_no

    try:
        html = authenticated_client("admin").get("/sales/sales-invoice/debit-note/list").get_data(as_text=True)
        html = html.replace("&amp;", "&")

        assert "/sales/sales-invoice/debit-note/list?page=2" in html
        assert "/sales/sales-invoice/return/list" not in html
        pending_row = re.search(
            rf"{re.escape(pending_invoice_no)}(?:(?!</tr>).)*Pendiente de Aprobación(?:(?!</tr>).)*</tr>",
            html,
            re.DOTALL,
        )
        assert pending_row is not None
    finally:
        with app.app_context():
            approval_row = database.session.get(ApprovalRequest, approval_id)
            if approval_row is not None:
                database.session.delete(approval_row)
            for invoice_id in invoice_ids:
                invoice = database.session.get(SalesInvoice, invoice_id)
                if invoice is not None:
                    database.session.delete(invoice)
            database.session.commit()
