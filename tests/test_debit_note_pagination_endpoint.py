# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2050: las notas de débito paginan sobre su propio listado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import SalesInvoice, database


def test_paginacion_de_nota_debito_no_apunta_a_devoluciones(app, authenticated_client, entorno_contable):
    """Con más de una página el enlace conserva el endpoint de notas de débito."""
    with app.app_context():
        for indice in range(11):
            database.session.add(
                SalesInvoice(
                    company="cacao",
                    document_type="sales_debit_note",
                    document_no=f"ND-2050-{indice}",
                    posting_date=date(2026, 5, 15),
                    customer_name="Cliente",
                    transaction_currency="NIO",
                    grand_total=Decimal("10"),
                    total=Decimal("10"),
                    outstanding_amount=Decimal("10"),
                )
            )
        database.session.commit()

    respuesta = authenticated_client("admin").get("/sales/sales-invoice/debit-note/list")
    html = respuesta.get_data(as_text=True).replace("&amp;", "&")

    assert "/sales/sales-invoice/debit-note/list?page=2" in html
    assert "/sales/sales-invoice/return/list" not in html
