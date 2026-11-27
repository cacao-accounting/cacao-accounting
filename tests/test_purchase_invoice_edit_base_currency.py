# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1822: editar una factura de compra refresca su moneda base."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    Accounts,
    Book,
    CompanyParty,
    GLEntry,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    database,
)
from cacao_accounting.fiscal_persistence_service import load_document_fiscal_lines


@pytest.fixture
def factura_con_base_obsoleta(app, entorno_contable):
    """Factura borrador cuya base monetaria quedó desalineada de la compañía."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        configuracion = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if configuracion is None:
            configuracion = PurchaseMatchingConfig(
                company="cacao",
                matching_type="2-way",
                require_purchase_order=False,
                bridge_account_required=False,
                auto_reconcile=False,
            )
            database.session.add(configuracion)
        else:
            configuracion.require_purchase_order = False
        proveedor = Party(
            code=f"PRV-BASE-{sufijo}",
            name=f"Proveedor base {sufijo}",
            is_supplier=True,
        )
        database.session.add(proveedor)
        database.session.flush()
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=proveedor.id,
                is_active=True,
                allow_purchase_invoice_without_order=True,
                allow_purchase_invoice_without_receipt=True,
            )
        )
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"FI-BASE-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="USD",
            exchange_rate=Decimal("1"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("2"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        ids = {
            "factura": factura.id,
            "proveedor": proveedor.id,
            "sufijo": sufijo,
        }
    yield ids


def test_editar_factura_refresca_base_currency_desde_la_compania(app, authenticated_client, factura_con_base_obsoleta):
    """Un snapshot de base monetaria obsoleto no sobrevive a la edición."""
    ids = factura_con_base_obsoleta
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data={
            "supplier_id": ids["proveedor"],
            "company": "cacao",
            "posting_date": "2026-05-15",
            "transaction_currency": "NIO",
            "supplier_invoice_no": f"FAC-{ids['sufijo']}",
            "item_code_0": "ART01",
            "item_name_0": "Articulo Comercial",
            "qty_0": "2",
            "uom_0": "UND",
            "rate_0": "10",
            "amount_0": "20",
        },
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    with app.app_context():
        factura = database.session.get(PurchaseInvoice, ids["factura"])
        assert factura.base_currency == "NIO"
        assert factura.exchange_rate == Decimal("1")
        assert factura.base_grand_total == factura.grand_total


def test_impuesto_manual_en_compra_reconcilia_total_ap_y_gl(
    app,
    authenticated_client,
    factura_con_base_obsoleta,
    entorno_contable,
):
    """Las rutas de crear y editar mantienen manual tax lines in AP and GL totals."""
    ids = factura_con_base_obsoleta
    client = authenticated_client("admin")
    with app.app_context():
        tax_account_id = database.session.execute(
            database.select(Accounts.id).where(Accounts.entity == "cacao", Accounts.code == "2105")
        ).scalar_one()

    def form_data(rate: str, tax_amount: str) -> dict[str, str]:
        """Build one purchase invoice form with an explicit manual tax line."""
        tax_lines = [
            {
                "source_rule_id": "MANUAL-IVA",
                "manual": True,
                "concept": "iva",
                "type": "tax",
                "calculation_method": "fixed",
                "amount": tax_amount,
                "account_id": str(tax_account_id),
            }
        ]
        return {
            "company": "cacao",
            "supplier_id": ids["proveedor"],
            "supplier_invoice_no": f"MANUAL-{ids['sufijo']}",
            "posting_date": "2026-05-15",
            "transaction_currency": "NIO",
            "document_type": "purchase_invoice",
            "item_code_0": "ART01",
            "item_name_0": "Articulo Comercial",
            "qty_0": "1",
            "uom_0": "UND",
            "rate_0": rate,
            "tax_lines_payload": json.dumps(tax_lines),
        }

    created = client.post("/buying/purchase-invoice/new", data=form_data("100", "15"), follow_redirects=True)
    assert created.status_code == 200

    with app.app_context():
        invoice = database.session.execute(
            database.select(PurchaseInvoice).filter_by(supplier_invoice_no=f"MANUAL-{ids['sufijo']}")
        ).scalar_one()
        invoice_id = invoice.id
        assert invoice.grand_total == Decimal("115.00")
        assert invoice.outstanding_amount == Decimal("115.00")

    updated = client.post(
        f"/buying/purchase-invoice/{invoice_id}/edit",
        data=form_data("120", "20"),
        follow_redirects=True,
    )
    assert updated.status_code == 200

    with app.app_context():
        invoice = database.session.get(PurchaseInvoice, invoice_id)
        assert invoice is not None
        assert invoice.grand_total == Decimal("140.00")
        assert invoice.outstanding_amount == Decimal("140.00")
        tax_line = load_document_fiscal_lines(document_type="purchase_invoice", document_id=invoice_id)[0]
        assert tax_line.amount == Decimal("20.0000")

    submitted = client.post(f"/buying/purchase-invoice/{invoice_id}/submit", follow_redirects=True)
    assert submitted.status_code in {200, 302}, submitted.get_data(as_text=True)

    with app.app_context():
        invoice = database.session.get(PurchaseInvoice, invoice_id)
        assert invoice is not None
        assert invoice.docstatus == 1
        assert ARAPLedgerEntry.document_balance("purchase_invoice", invoice_id) == Decimal("140.0000")
        active_books = (
            database.session.execute(database.select(Book.id).where(Book.entity == "cacao", Book.status == "activo"))
            .scalars()
            .all()
        )
        assert active_books
        for book_id in active_books:
            ap_book_entry = database.session.execute(
                database.select(ARAPLedgerBookEntry)
                .join(ARAPLedgerEntry)
                .where(
                    ARAPLedgerEntry.document_id == invoice_id,
                    ARAPLedgerBookEntry.ledger_id == book_id,
                )
            ).scalar_one()
            gl_entry = database.session.get(GLEntry, ap_book_entry.gl_entry_id)
            assert gl_entry is not None
            assert gl_entry.account_code == "2101"
            assert ap_book_entry.credit == Decimal("140.0000")
            assert gl_entry.credit == ap_book_entry.credit
