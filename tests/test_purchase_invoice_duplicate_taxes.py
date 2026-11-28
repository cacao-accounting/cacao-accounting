# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2099: duplicar factura de compra recalcula el bruto con impuestos reales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyParty,
    GLEntry,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    database,
)

FECHA = date(2026, 5, 15)


def _plantilla_impuesto(sufijo: str) -> TaxTemplate:
    """Crea un impuesto real de 15% y su plantilla de compra."""
    cuenta_iva = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
    impuesto = Tax(
        id=f"TAX-DUP-{sufijo}",
        name=f"IVA {sufijo}",
        rate=15,
        tax_type="percentage",
        applies_to="purchase",
        is_active=True,
        account_id=cuenta_iva.id,
    )
    plantilla = TaxTemplate(
        name=f"Plantilla duplicado {sufijo}",
        company="cacao",
        template_type="buying",
        currency="NIO",
        is_active=True,
    )
    database.session.add_all([impuesto, plantilla])
    database.session.flush()
    database.session.add(
        TaxTemplateItem(
            tax_template_id=plantilla.id,
            tax_id=impuesto.id,
            sequence=10,
            calculation_base="net_document",
            behavior="additive",
            is_inclusive=False,
        )
    )
    database.session.flush()
    return plantilla


def _cliente_aislado(escenario):
    """Autentica un cliente en la app aislada del escenario."""
    from sqlalchemy import inspect

    app = escenario.app
    user_id = str(inspect(escenario.admin_user).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_duplicado_recalcula_el_total_fiscal(entorno_contable_aislado):
    """El borrador duplicado usa la plantilla real y conserva el total al enviarse."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:8]
    with app.app_context():
        matching = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching is None:
            matching = PurchaseMatchingConfig(
                company="cacao",
                matching_type="2-way",
                require_purchase_order=False,
                bridge_account_required=False,
                auto_reconcile=False,
            )
            database.session.add(matching)
        else:
            matching.require_purchase_order = False
        proveedor = Party(
            code=f"PRV-DUP-{sufijo}",
            name=f"Proveedor duplicado {sufijo}",
            is_supplier=True,
            is_active=True,
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
        plantilla = _plantilla_impuesto(sufijo)
        origen = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PI-DUP-{sufijo}",
            document_type="purchase_invoice",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            tax_template_id=plantilla.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=f"PI-DUP-{sufijo}",
            grand_total=Decimal("115"),
        )
        database.session.add(origen)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=origen.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
        )
        database.session.commit()
        origen_id = origen.id
        plantilla_id = plantilla.id

    client = _cliente_aislado(entorno_contable_aislado)
    respuesta = client.post(f"/buying/purchase-invoice/{origen_id}/duplicate")

    assert respuesta.status_code == 302
    with app.app_context():
        copia = database.session.execute(
            database.select(PurchaseInvoice).filter_by(remarks=f"PI-DUP-{sufijo}", docstatus=0)
        ).scalar_one()
        copia_id = copia.id
        assert copia.tax_template_id == plantilla_id
        assert copia.total == Decimal("100")
        assert copia.grand_total == Decimal("115.00")
        assert copia.outstanding_amount == Decimal("115.00")
        assert copia.base_grand_total == Decimal("115.00")

    submit = client.post(f"/buying/purchase-invoice/{copia_id}/submit", follow_redirects=True)
    assert submit.status_code in {302, 200}, submit.get_data(as_text=True)
    with app.app_context():
        enviada = database.session.get(PurchaseInvoice, copia_id)
        assert enviada.docstatus == 1, "La copia no se contabilizó"
        assert enviada.grand_total == Decimal("115.00")
        assert enviada.outstanding_amount == Decimal("115.00")

        libros = (
            database.session.execute(database.select(Book.id).where(Book.entity == "cacao", Book.status == "activo"))
            .scalars()
            .all()
        )
        assert libros
        for libro in libros:
            filas = (
                database.session.execute(
                    database.select(GLEntry).where(GLEntry.voucher_id == copia_id, GLEntry.ledger_id == libro)
                )
                .scalars()
                .all()
            )
            asientos = {fila.account_code: (Decimal(fila.debit), Decimal(fila.credit)) for fila in filas}
            assert asientos == {
                "5201": (Decimal("100.0000"), Decimal("0.0000")),
                "2105": (Decimal("15.0000"), Decimal("0.0000")),
                "2101": (Decimal("0.0000"), Decimal("115.0000")),
            }
            total_debito = sum((debito for debito, _credito in asientos.values()), Decimal("0"))
            total_credito = sum((credito for _debito, credito in asientos.values()), Decimal("0"))
            assert total_debito == total_credito == enviada.grand_total
