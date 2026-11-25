# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2260: duplicar una factura conserva su configuración fiscal y de inventario."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect

import pytest

from cacao_accounting.database import (
    Accounts,
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    database,
)
from cacao_accounting.document_flow.repository import consumed_qty_for_source
from cacao_accounting.ventas.services import _validate_sales_invoice_relation
from cacao_accounting.fiscal_persistence_service import (
    build_tax_rule_contexts_from_snapshot,
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)


def _cliente(escenario):
    """Autentica al administrador del escenario aislado."""
    application = escenario.app
    user_id = str(inspect(escenario.admin_user).identity[0])
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _linea_fiscal(sufijo: str) -> dict:
    """Serializa una línea fiscal manual como la captura del formulario."""
    return {
        "manual": True,
        "source_rule_id": f"MANUAL-IVA-{sufijo}",
        "concept": "iva",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "base_amount": "100",
        "rate": "15",
        "amount": "15",
        "accounting_treatment": "separate_tax_account",
        "affects_document_total": True,
        "included_in_price": False,
    }


def test_duplicado_conserva_snapshot_fiscal_y_actualizacion_inventario(entorno_contable_aislado):
    """La copia mantiene el impuesto calculado y la decisión de inventario del original."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        cuenta_iva = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
        origen = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"FV-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            update_inventory=True,
            total=Decimal("100"),
            grand_total=Decimal("115"),
            outstanding_amount=Decimal("115"),
            base_total=Decimal("100"),
            base_grand_total=Decimal("115"),
            base_outstanding_amount=Decimal("115"),
        )
        database.session.add(origen)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=origen.id,
                item_code="ART01",
                item_name="Artículo de prueba",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("100"),
                warehouse="BOD01",
            )
        )
        database.session.flush()
        origen_id = origen.id

        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=origen_id,
            currency="NIO",
            tax_lines=[{**_linea_fiscal(sufijo), "account_id": cuenta_iva.id}],
            tax_summary={"subtotal": "100", "grand_total": "115"},
            server_subtotal=Decimal("100"),
            server_total=Decimal("115"),
        )
        database.session.commit()

    respuesta = _cliente(entorno_contable_aislado).post(f"/sales/sales-invoice/{origen_id}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != origen_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        assert copia.update_inventory is True
        assert copia.grand_total == Decimal("115")

        originales = load_document_fiscal_lines("sales_invoice", origen_id)
        duplicadas = load_document_fiscal_lines("sales_invoice", copia.id)
        assert len(originales) == len(duplicadas) == 1
        assert duplicadas[0].concept == originales[0].concept
        assert duplicadas[0].base_amount == originales[0].base_amount
        assert duplicadas[0].rate == originales[0].rate
        assert duplicadas[0].amount == originales[0].amount
        assert duplicadas[0].account_id == originales[0].account_id

        restauradas = build_tax_rule_contexts_from_snapshot(
            document_type="sales_invoice",
            document_id=copia.id,
            recognition_event="sales_invoice_confirmed",
        )
        assert [regla.amount for regla in restauradas] == [Decimal("15.0000")]


def test_duplicado_no_infla_disponibilidad_y_detecta_sobre_facturacion(entorno_contable_aislado):
    """El borrador duplicado no consume stock del origen, pero al confirmar se detecta el exceso."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        entrega = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 2260",
            document_no=f"NE-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add(entrega)
        database.session.flush()
        entrega_linea = DeliveryNoteItem(
            delivery_note_id=entrega.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(entrega_linea)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            customer_name="Cliente 2260",
            document_no=f"FV-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.flush()
        factura_linea = SalesInvoiceItem(
            sales_invoice_id=factura.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(factura_linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="delivery_note",
                source_id=entrega.id,
                source_item_id=entrega_linea.id,
                target_type="sales_invoice",
                target_id=factura.id,
                target_item_id=factura_linea.id,
                company="cacao",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("100"),
                relation_type="billing",
                status="active",
            )
        )
        database.session.commit()
        entrega_id = entrega.id
        entrega_linea_id = entrega_linea.id
        factura_id = factura.id

    respuesta = _cliente(entorno_contable_aislado).post(f"/sales/sales-invoice/{factura_id}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != factura_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        relacion = database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="sales_invoice", target_id=copia.id, status="active")
        ).scalar_one()
        consumido = consumed_qty_for_source(
            "delivery_note", entrega_id, entrega_linea_id, "sales_invoice", exclude_draft_targets=True
        )
        assert consumido == Decimal("1")

        with pytest.raises(ValueError, match="Sobre-facturación"):
            _validate_sales_invoice_relation(relacion, invoice_id=copia.id)
