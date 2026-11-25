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
    GLEntry,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesMatchingConfig,
    SalesOrder,
    SalesOrderItem,
    StockBin,
    StockLedgerEntry,
    StockValuationLayer,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.document_flow.repository import consumed_qty_for_source
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


def test_duplicado_no_infla_disponibilidad_ni_hereda_entrega(entorno_contable_aislado):
    """El duplicado no consume stock ni reutiliza la relación de entrega del origen."""
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
        assert copia.delivery_note_id is None
        assert (
            database.session.execute(
                database.select(DocumentRelation.id).filter_by(
                    target_type="sales_invoice", target_id=copia.id, source_type="delivery_note", status="active"
                )
            ).scalar_one_or_none()
            is None
        )
        consumido = consumed_qty_for_source(
            "delivery_note", entrega_id, entrega_linea_id, "sales_invoice", exclude_draft_targets=True
        )
        assert consumido == Decimal("1")


def test_duplicado_de_orden_agotada_no_contabiliza_ni_mueve_inventario(entorno_contable_aislado):
    """La copia de una factura que agotó su orden conserva el snapshot pero no puede contabilizarse."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        cuenta_iva = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
        orden = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"OV-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(orden)
        database.session.flush()
        orden_linea = SalesOrderItem(
            sales_order_id=orden.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(orden_linea)
        database.session.flush()
        origen = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"FV-{sufijo}",
            sales_order_id=orden.id,
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
        origen_linea = SalesInvoiceItem(
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
        database.session.add(origen_linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="sales_order",
                source_id=orden.id,
                source_item_id=orden_linea.id,
                target_type="sales_invoice",
                target_id=origen.id,
                target_item_id=origen_linea.id,
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
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=origen.id,
            currency="NIO",
            tax_lines=[{**_linea_fiscal(sufijo), "account_id": cuenta_iva.id}],
            tax_summary={"subtotal": "100", "grand_total": "115"},
            server_subtotal=Decimal("100"),
            server_total=Decimal("115"),
        )
        database.session.commit()
        origen_id = origen.id

    cliente_http = _cliente(entorno_contable_aislado)
    assert cliente_http.post(f"/sales/sales-invoice/{origen_id}/duplicate").status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != origen_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        copia_id = copia.id
        assert copia.update_inventory is True
        assert load_document_fiscal_lines("sales_invoice", copia_id)

    respuesta = cliente_http.post(f"/sales/sales-invoice/{copia_id}/submit", follow_redirects=True)
    assert respuesta.status_code == 200
    assert b"Sobre-facturaci" in respuesta.data

    with app.app_context():
        database.session.expire_all()
        assert database.session.get(SalesInvoice, copia_id).docstatus == 0
        assert (
            database.session.execute(database.select(GLEntry.id).filter_by(voucher_type="sales_invoice", voucher_id=copia_id))
            .scalars()
            .all()
            == []
        )
        copia = database.session.get(SalesInvoice, copia_id)
        assert copia is not None and copia.delivery_note_id is None
        assert database.session.execute(database.select(DeliveryNote.id)).scalars().all() == []


def test_duplicado_de_factura_con_entrega_no_comparte_nota(entorno_contable_aislado):
    """La copia independiente no reutiliza la nota de entrega del original."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        entrega = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"NE-DUP-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(entrega)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"FV-DUP-{sufijo}",
            delivery_note_id=entrega.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.flush()
        linea = SalesInvoiceItem(
            sales_invoice_id=factura.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="delivery_note",
                source_id=entrega.id,
                target_type="sales_invoice",
                target_id=factura.id,
                target_item_id=linea.id,
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
        factura_id = factura.id

    respuesta = _cliente(entorno_contable_aislado).post(f"/sales/sales-invoice/{factura_id}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != factura_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        assert copia.delivery_note_id is None
        assert (
            database.session.execute(
                database.select(DocumentRelation.id).filter_by(
                    target_type="sales_invoice", target_id=copia.id, source_type="delivery_note", status="active"
                )
            ).scalar_one_or_none()
            is None
        )


@pytest.mark.parametrize("document_type", ["sales_credit_note", "sales_debit_note", "sales_return"])
def test_duplicado_documento_no_positivo_3way_no_se_bloquea(entorno_contable_aislado, document_type):
    """Las notas y devoluciones conservan la duplicación aunque la compañía sea 3-way."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        database.session.add(SalesMatchingConfig(company="cacao", matching_type="3-way", require_sales_order=True))
        nota = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type=document_type,
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"NC-3W-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add(nota)
        database.session.commit()
        nota_id = nota.id

    respuesta = _cliente(entorno_contable_aislado).post(f"/sales/sales-invoice/{nota_id}/duplicate")
    assert respuesta.status_code == 302
    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != nota_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        assert copia.document_type == document_type


@pytest.mark.parametrize(
    ("matching_type", "require_order"),
    [("3-way", True), ("3-way", False), ("2-way", True)],
)
def test_duplicado_con_entrega_sin_orden_se_rechaza(entorno_contable_aislado, matching_type, require_order):
    """Una copia que perdería su origen no se crea en modalidades que lo exigen."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        database.session.add(
            SalesMatchingConfig(
                company="cacao",
                matching_type=matching_type,
                require_sales_order=require_order,
            )
        )
        entrega = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"NE-3W-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(entrega)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            document_no=f"FV-3W-{sufijo}",
            delivery_note_id=entrega.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            grand_total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id

    respuesta = _cliente(entorno_contable_aislado).post(f"/sales/sales-invoice/{factura_id}/duplicate")

    assert respuesta.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(SalesInvoice).where(SalesInvoice.id != factura_id)).scalars().all() == []
        )


def test_duplicado_aprobado_genera_evidencia_fiscal_gl_e_inventario_propia(entorno_contable_aislado):
    """La copia aprobada calcula sus impuestos y genera asiento y stock propios."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        cuenta_iva = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
        cuenta_iva_id = cuenta_iva.id
        cuenta_inventario = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code="1109")
        ).scalar_one()
        database.session.add(
            WarehouseCompanyAccount(warehouse_code="BOD01", company="cacao", inventory_account_id=cuenta_inventario.id)
        )
        origen = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=0,
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
        database.session.add(
            StockLedgerEntry(
                posting_date=date(2026, 5, 1),
                item_code="ART01",
                warehouse="BOD01",
                company="cacao",
                qty_change=Decimal("5"),
                qty_after_transaction=Decimal("5"),
                valuation_rate=Decimal("10"),
                stock_value=Decimal("50"),
                voucher_type="stock_entry",
                voucher_id=f"SE-{sufijo}",
            )
        )
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ART01",
                warehouse="BOD01",
                actual_qty=Decimal("5"),
                stock_value=Decimal("50"),
                valuation_rate=Decimal("10"),
            )
        )
        database.session.add(
            StockValuationLayer(
                posting_date=date(2026, 5, 1),
                item_code="ART01",
                warehouse="BOD01",
                company="cacao",
                qty=Decimal("5"),
                rate=Decimal("10"),
                stock_value_difference=Decimal("50"),
                remaining_qty=Decimal("5"),
                remaining_stock_value=Decimal("50"),
                voucher_type="stock_entry",
                voucher_id=f"SE-{sufijo}",
            )
        )
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=origen.id,
            currency="NIO",
            tax_lines=[{**_linea_fiscal(sufijo), "account_id": cuenta_iva_id}],
            tax_summary={"subtotal": "100", "grand_total": "115"},
            server_subtotal=Decimal("100"),
            server_total=Decimal("115"),
        )
        database.session.commit()
        origen_id = origen.id

    cliente_http = _cliente(entorno_contable_aislado)
    assert cliente_http.post(f"/sales/sales-invoice/{origen_id}/duplicate").status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != origen_id, SalesInvoice.docstatus == 0)
        ).scalar_one()
        copia_id = copia.id
        assert copia.delivery_note_id is None
        assert [linea.amount for linea in load_document_fiscal_lines("sales_invoice", copia_id)] == [Decimal("15.0000")]

    respuesta_origen = cliente_http.post(f"/sales/sales-invoice/{origen_id}/submit", follow_redirects=True)
    assert respuesta_origen.status_code == 200
    assert b"Factura de venta aprobada y contabilizada" in respuesta_origen.data

    with app.app_context():
        assert database.session.get(SalesInvoice, origen_id).docstatus == 1

    with app.app_context():
        copia = database.session.get(SalesInvoice, copia_id)
        linea_copia = database.session.execute(
            database.select(SalesInvoiceItem).filter_by(sales_invoice_id=copia_id)
        ).scalar_one()
        linea_copia.rate = Decimal("200")
        linea_copia.amount = Decimal("200")
        copia.total = copia.base_total = Decimal("200")
        copia.grand_total = copia.base_grand_total = Decimal("230")
        copia.outstanding_amount = copia.base_outstanding_amount = Decimal("230")
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id=copia_id,
            currency="NIO",
            tax_lines=[
                {
                    **_linea_fiscal(sufijo),
                    "base_amount": "200",
                    "rate": "15",
                    "amount": "30",
                    "account_id": cuenta_iva_id,
                }
            ],
            tax_summary={"subtotal": "200", "grand_total": "230"},
            server_subtotal=Decimal("200"),
            server_total=Decimal("230"),
        )
        database.session.commit()

    assert cliente_http.post(f"/sales/sales-invoice/{copia_id}/submit", follow_redirects=True).status_code == 200

    with app.app_context():
        database.session.expire_all()
        origen = database.session.get(SalesInvoice, origen_id)
        copia = database.session.get(SalesInvoice, copia_id)
        assert copia.docstatus == 1
        assert copia.delivery_note_id != origen.delivery_note_id

        def creditos_impuesto(invoice_id: str) -> set[Decimal]:
            return {
                Decimal(entry.credit or "0")
                for entry in database.session.execute(
                    database.select(GLEntry).filter_by(
                        voucher_type="sales_invoice", voucher_id=invoice_id, account_code="2105"
                    )
                )
                .scalars()
                .all()
            }

        assert creditos_impuesto(origen_id) == {Decimal("15")}
        assert creditos_impuesto(copia_id) == {Decimal("30")}

        def movimientos(delivery_note_id: str) -> list[Decimal]:
            return [
                Decimal(entry.qty_change)
                for entry in database.session.execute(
                    database.select(StockLedgerEntry).filter_by(voucher_type="delivery_note", voucher_id=delivery_note_id)
                )
                .scalars()
                .all()
            ]

        assert movimientos(origen.delivery_note_id) == [Decimal("-1.000000000")]
        assert movimientos(copia.delivery_note_id) == [Decimal("-1.000000000")]

        lineas_copia = load_document_fiscal_lines("sales_invoice", copia_id)
        assert [linea.amount for linea in lineas_copia] == [Decimal("30.0000")]
        assert [linea.id for linea in lineas_copia] != [
            linea.id for linea in load_document_fiscal_lines("sales_invoice", origen_id)
        ]
        assert [
            regla.amount
            for regla in build_tax_rule_contexts_from_snapshot(
                document_type="sales_invoice", document_id=copia_id, recognition_event="sales_invoice_confirmed"
            )
        ] == [Decimal("30.0000")]
