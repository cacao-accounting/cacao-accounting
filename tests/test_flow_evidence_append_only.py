# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#923: la evidencia del flujo documental y de conciliación es inmutable.

`DocumentRelation`, `PurchaseReconciliation` y `PurchaseReconciliationItem`
son la fuente de verdad de cantidades consumidas y resultados de matching.
Reescribir sus cifras o borrarlas rompe la trazabilidad frente al ledger, así
que el guard estructural debe rechazar UPDATE/DELETE por ORM, Core y SQL
textual en Desktop y Cloud, dejando la fila y sus importes intactos.

Las transiciones legítimas de `status` se ejecutan por los servicios
autorizados y no forman parte de este contrato de inmutabilidad.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReconciliation,
    PurchaseReconciliationItem,
    UOM,
    database,
)


def _build_app(desktop: bool):
    """Crea una app con el guard estructural de evidencia habilitado."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": desktop,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _seed_flow_evidence(app) -> dict[str, tuple[type, str, str, object, object]]:
    """Siembra una recepción/factura conciliada real y su relación documental.

    Devuelve por tabla el modelo, el id, el campo de evidencia que no debe
    mutarse y los valores usados por ORM/Core y por SQL textual.
    """
    suffix = uuid4().hex[:6].upper()
    item_code = f"ITEM-{suffix}"
    supplier_code = f"SUP-{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(Item(code=item_code, name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA"))
        database.session.flush()
        supplier = Party(code=supplier_code, name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        order = PurchaseOrder(
            company="alpha",
            document_no=f"PO-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(order)
        database.session.flush()
        order_item = PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code=item_code,
            item_name="Artículo",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
        invoice = PurchaseInvoice(
            company="alpha",
            document_type="purchase_invoice",
            document_no=f"PI-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            supplier_invoice_no=f"FAC-{suffix}",
            posting_date=date(2026, 5, 12),
            docstatus=1,
            purchase_order_id=order.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([order_item, invoice])
        database.session.flush()
        invoice_item = PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code=item_code,
            item_name="Artículo",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
        database.session.add(invoice_item)
        database.session.flush()
        reconciliation = PurchaseReconciliation(
            company="alpha",
            purchase_order_id=order.id,
            purchase_invoice_id=invoice.id,
            idempotency_key=f"recon-{suffix}",
            matching_type="2-way",
            matched_amount=Decimal("50"),
            matched_date=date(2026, 5, 12),
            status="reconciled",
        )
        database.session.add(reconciliation)
        database.session.flush()
        reconciliation_item = PurchaseReconciliationItem(
            purchase_reconciliation_id=reconciliation.id,
            purchase_order_item_id=order_item.id,
            purchase_invoice_item_id=invoice_item.id,
            item_code=item_code,
            uom="EA",
            received_qty=Decimal("5"),
            invoiced_qty=Decimal("5"),
            matched_qty=Decimal("5"),
            received_amount=Decimal("50"),
            invoiced_amount=Decimal("50"),
            matched_amount=Decimal("50"),
            status="reconciled",
        )
        relation = DocumentRelation(
            company="alpha",
            source_type="purchase_order",
            source_id=order.id,
            source_item_id=order_item.id,
            target_type="purchase_invoice",
            target_id=invoice.id,
            target_item_id=invoice_item.id,
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
            relation_type="invoice_from_order",
            revision=1,
            status="active",
        )
        database.session.add_all([reconciliation_item, relation])
        database.session.commit()
        return {
            "document_relation": (DocumentRelation, relation.id, "qty", Decimal("9"), 9),
            "purchase_reconciliation": (
                PurchaseReconciliation,
                reconciliation.id,
                "matched_amount",
                Decimal("9"),
                9,
            ),
            "purchase_reconciliation_item": (
                PurchaseReconciliationItem,
                reconciliation_item.id,
                "matched_qty",
                Decimal("9"),
                9,
            ),
        }


@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize(
    "table_name",
    ["document_relation", "purchase_reconciliation", "purchase_reconciliation_item"],
)
@pytest.mark.parametrize("desktop", [True, False], ids=["desktop", "cloud"])
def test_flow_evidence_rejects_mutation(channel, operation, table_name, desktop):
    """Ni ORM, ni Core, ni SQL textual pueden reescribir o borrar la evidencia."""
    app = _build_app(desktop=desktop)
    evidence = _seed_flow_evidence(app)
    model, row_id, field_name, orm_value, sql_value = evidence[table_name]

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(model, row_id)
                assert row is not None
                if operation == "delete":
                    database.session.delete(row)
                else:
                    setattr(row, field_name, orm_value)
                database.session.commit()
            elif channel == "core":
                statement = (
                    database.delete(model) if operation == "delete" else database.update(model).values({field_name: orm_value})
                )
                database.session.execute(statement.where(model.id == row_id))
                database.session.commit()
            else:
                if operation == "delete":
                    statement = text(f"DELETE FROM {table_name} WHERE id = :row_id")
                    parameters = {"row_id": row_id}
                else:
                    statement = text(f"UPDATE {table_name} SET {field_name} = :value WHERE id = :row_id")
                    parameters = {"row_id": row_id, "value": sql_value}
                database.session.execute(statement, parameters)
                database.session.commit()
        database.session.rollback()

    with app.app_context():
        row = database.session.get(model, row_id)
        assert row is not None
        expected = {"document_relation": "5", "purchase_reconciliation": "50", "purchase_reconciliation_item": "5"}
        assert Decimal(str(getattr(row, field_name))) == Decimal(expected[table_name])
