# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2300: exposición O2C a partir de líneas reales y flujo de aprobación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import submit_document
from cacao_accounting.database import (
    CompanyParty,
    DocumentRelation,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    User,
    database,
)
from cacao_accounting.document_flow import create_document_relation
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.ventas.services import _approved_customer_order_exposure

FECHA = date(2026, 5, 15)


@pytest.fixture
def flujo_exposicion_real(app, entorno_contable):
    """Crea y aprueba orden y factura con líneas reales; limpia todo al final."""
    sufijo = uuid4().hex[:8]
    item_code = f"EXP-REAL-{sufijo}"
    with app.app_context():
        cliente = Party(code=f"EXP-CLI-{sufijo}", name="Cliente flujo real", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=cliente.id, is_active=True))
        item = Item(
            code=item_code,
            name="Servicio exposición",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            default_uom="UND",
        )
        database.session.add(item)
        database.session.flush()
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        orden = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"SO-EXP-REAL-{sufijo}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("300"),
            grand_total=Decimal("300"),
            base_total=Decimal("300"),
            status="open",
        )
        database.session.add(orden)
        database.session.flush()
        orden_linea = SalesOrderItem(
            sales_order_id=orden.id,
            item_code=item_code,
            item_name=item.name,
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("300"),
            base_amount=Decimal("300"),
        )
        database.session.add(orden_linea)
        database.session.flush()
        orden.docstatus = 1
        database.session.commit()

        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"SI-EXP-REAL-{sufijo}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            document_type="sales_invoice",
            is_return=False,
            total=Decimal("100"),
            grand_total=Decimal("100"),
            base_total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.flush()
        from cacao_accounting.database import Accounts

        income_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="4101")
        ).scalar_one()
        factura_linea = SalesInvoiceItem(
            sales_invoice_id=factura.id,
            item_code=item_code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            income_account_id=income_account_id,
        )
        database.session.add(factura_linea)
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(factura, actor.id):
            submit_document(factura)
        database.session.commit()

        exposicion_antes = _approved_customer_order_exposure("cacao", cliente.id)
        create_document_relation(
            source_type="sales_order",
            source_id=orden.id,
            source_item_id=orden_linea.id,
            target_type="sales_invoice",
            target_id=factura.id,
            target_item_id=factura_linea.id,
            qty=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.commit()
        ids = {
            "cliente": cliente.id,
            "orden": orden.id,
            "factura": factura.id,
            "orden_linea": orden_linea.id,
            "factura_linea": factura_linea.id,
            "item": item_code,
            "exposicion_antes": exposicion_antes,
            "exposicion_despues": _approved_customer_order_exposure("cacao", cliente.id),
        }

    yield ids

    with app.app_context():
        from cacao_accounting.database import (
            ARAPLedgerBookEntry,
            ARAPLedgerEntry,
            ARAPOpenItem,
            AuditTrail,
            GLEntry,
        )

        database.session.execute(
            database.delete(DocumentRelation).where(
                DocumentRelation.target_type == "sales_invoice", DocumentRelation.target_id == ids["factura"]
            )
        )
        database.session.execute(database.delete(ARAPOpenItem).where(ARAPOpenItem.document_id == ids["factura"]))
        ledger_ids = database.session.execute(
            database.select(ARAPLedgerEntry.id).where(ARAPLedgerEntry.document_id == ids["factura"])
        ).scalars()
        database.session.execute(
            database.delete(ARAPLedgerBookEntry).where(ARAPLedgerBookEntry.ledger_entry_id.in_(list(ledger_ids)))
        )
        database.session.execute(database.delete(ARAPLedgerEntry).where(ARAPLedgerEntry.document_id == ids["factura"]))
        database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id == ids["factura"]))
        database.session.execute(database.delete(AuditTrail).where(AuditTrail.document_id == ids["factura"]))
        database.session.execute(database.delete(SalesInvoiceItem).where(SalesInvoiceItem.sales_invoice_id == ids["factura"]))
        database.session.execute(database.delete(SalesInvoice).where(SalesInvoice.id == ids["factura"]))
        database.session.execute(database.delete(SalesOrderItem).where(SalesOrderItem.sales_order_id == ids["orden"]))
        database.session.execute(database.delete(SalesOrder).where(SalesOrder.id == ids["orden"]))
        database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == ids["cliente"]))
        database.session.execute(database.delete(Party).where(Party.id == ids["cliente"]))
        database.session.execute(database.delete(Item).where(Item.code == ids["item"]))
        database.session.commit()


def test_exposicion_usa_lineas_reales_aprobadas(app, flujo_exposicion_real):
    """La relación real descuenta la exposición después del posting."""
    ids = flujo_exposicion_real
    with app.app_context():
        assert ids["exposicion_antes"] == Decimal("300")
        assert ids["exposicion_despues"] == Decimal("200")
        assert _approved_customer_order_exposure("cacao", ids["cliente"]) == Decimal("200")
        relacion = database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type="sales_invoice",
                target_id=ids["factura"],
                source_item_id=ids["orden_linea"],
                target_item_id=ids["factura_linea"],
                status="active",
            )
        ).scalar_one()
        assert relacion.source_type == "sales_order"
        assert relacion.source_id == ids["orden"]
