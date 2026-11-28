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
    Currency,
    GLEntry,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    User,
    database,
)
from cacao_accounting.fiscal_persistence_service import load_document_fiscal_lines


@pytest.fixture
def factura_con_base_obsoleta(entorno_contable_aislado):
    """Factura borrador aislada cuya base monetaria quedó desalineada de la compañía."""
    app = entorno_contable_aislado.app
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
            "version": factura.version,
            "proveedor": proveedor.id,
            "sufijo": sufijo,
        }
    yield ids


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        admin_id, auth_version = admin.id, admin.auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def _form(ids, currency: str) -> dict[str, str]:
    """Payload HTTP completo para editar la factura borrador."""
    return {
        "version": str(ids["version"]),
        "supplier_id": ids["proveedor"],
        "company": "cacao",
        "posting_date": "2026-05-15",
        "transaction_currency": currency,
        "supplier_invoice_no": f"FAC-{ids['sufijo']}",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }


def test_editar_factura_refresca_base_currency_desde_la_compania(entorno_contable_aislado, factura_con_base_obsoleta):
    """Un snapshot de base monetaria obsoleto no sobrevive a la edición."""
    ids = factura_con_base_obsoleta
    app = entorno_contable_aislado.app
    cliente = _cliente(app)

    respuesta = cliente.post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data=_form(ids, "NIO"),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    with app.app_context():
        factura = database.session.get(PurchaseInvoice, ids["factura"])
        assert factura.base_currency == "NIO"
        assert factura.exchange_rate == Decimal("1")
        assert factura.base_grand_total == factura.grand_total


def test_impuesto_manual_en_compra_reconcilia_total_ap_y_gl(entorno_contable_aislado, factura_con_base_obsoleta):
    """Las rutas de crear y editar mantienen manual tax lines in AP and GL totals."""
    ids = factura_con_base_obsoleta
    app = entorno_contable_aislado.app
    client = _cliente(app)
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
        invoice_version = invoice.version
        assert invoice.grand_total == Decimal("115.00")
        assert invoice.outstanding_amount == Decimal("115.00")

    update_data = form_data("120", "20")
    update_data["version"] = str(invoice_version)
    updated = client.post(
        f"/buying/purchase-invoice/{invoice_id}/edit",
        data=update_data,
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


def test_editar_factura_acepta_moneda_activa_y_recalcula_base(entorno_contable_aislado, factura_con_base_obsoleta):
    """Cambiar a una moneda activa persiste la moneda y su tasa histórica."""
    ids = factura_con_base_obsoleta
    app = entorno_contable_aislado.app
    response = _cliente(app).post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data=_form(ids, "USD"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Factura de compra actualizada correctamente." in response.get_data(as_text=True)
    with app.app_context():
        invoice = database.session.get(PurchaseInvoice, ids["factura"])
        assert invoice.transaction_currency == "USD"
        assert invoice.base_currency == "NIO"
        assert invoice.exchange_rate == Decimal("36.5")
        assert invoice.base_grand_total == invoice.grand_total * invoice.exchange_rate


def test_editar_factura_rechaza_moneda_inactiva_sin_mutar(entorno_contable_aislado, factura_con_base_obsoleta):
    """Una moneda inactiva no reemplaza el snapshot ni las líneas del borrador."""
    ids = factura_con_base_obsoleta
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(Currency(code="OFF1822", name="Inactiva 1822", decimals=2, active=False, default=False))
        database.session.commit()

    response = _cliente(app).post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data=_form(ids, "OFF1822"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "La moneda seleccionada no existe o no está activa." in response.get_data(as_text=True)
    with app.app_context():
        invoice = database.session.get(PurchaseInvoice, ids["factura"])
        assert invoice.transaction_currency == "NIO"
        assert invoice.base_currency == "USD"
        assert invoice.version == 1
        active_items = (
            database.session.execute(
                database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id, is_superseded=False)
            )
            .scalars()
            .all()
        )
        assert len(active_items) == 1


def test_editar_factura_sin_tasa_revierte_cambio(entorno_contable_aislado, factura_con_base_obsoleta):
    """La falta de tasa bloquea la edición y restaura cabecera y líneas."""
    ids = factura_con_base_obsoleta
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(Currency(code="NEW1822", name="Sin tasa 1822", decimals=2, active=True, default=False))
        database.session.commit()

    response = _cliente(app).post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data=_form(ids, "NEW1822"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "No existe tipo de cambio" in response.get_data(as_text=True)
    with app.app_context():
        invoice = database.session.get(PurchaseInvoice, ids["factura"])
        assert invoice.transaction_currency == "NIO"
        assert invoice.base_currency == "USD"
        assert invoice.version == 1
        active_items = (
            database.session.execute(
                database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id, is_superseded=False)
            )
            .scalars()
            .all()
        )
        assert len(active_items) == 1
