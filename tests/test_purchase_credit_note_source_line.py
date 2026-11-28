# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1424: la nota de crédito respeta la línea origen de la relación documental.

Una factura puede repetir el mismo artículo en varias líneas; la relación
guardada al capturar la nota identifica la línea exacta y debe tener prioridad
sobre la búsqueda por código de artículo.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.compras.purchase_reconciliation_service import (
    PurchaseReconciliationError,
    create_purchase_credit_note_allocations,
)
from cacao_accounting.database import (
    DocumentRelation,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    UOM,
    database,
)

FECHA = date(2026, 5, 15)


def _context() -> tuple[str, str, str]:
    """Devuelve proveedor, artículo y unidad de medida del escenario."""
    supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
    item_code = str(database.session.execute(select(Item.code).filter_by(code="ART01")).scalar_one())
    uom_code = str(database.session.execute(select(UOM.code).filter_by(code="UND")).scalar_one())
    return supplier_id, item_code, uom_code


def _invoice(supplier_id: str) -> PurchaseInvoice:
    """Crea una factura de compra aprobada."""
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=FECHA,
        document_no="PI-1424",
        document_type="purchase_invoice",
        supplier_id=supplier_id,
        supplier_name="Proveedor de prueba",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _line(invoice_id: str, item_code: str, uom_code: str, amount: str) -> PurchaseInvoiceItem:
    """Crea una línea de factura con el importe indicado."""
    line = PurchaseInvoiceItem(
        purchase_invoice_id=invoice_id,
        item_code=item_code,
        item_name="Artículo repetido",
        qty=Decimal("1"),
        qty_in_base_uom=Decimal("1"),
        uom=uom_code,
        rate=Decimal(amount),
        amount=Decimal(amount),
        base_amount=Decimal(amount),
    )
    database.session.add(line)
    database.session.flush()
    return line


def _credit_note(supplier_id: str, source_id: str, item_code: str, uom_code: str, amount: str) -> PurchaseInvoice:
    """Crea una nota de crédito comercial aprobada contra la factura origen."""
    note = PurchaseInvoice(
        company="cacao",
        posting_date=FECHA,
        document_no="CN-1424",
        document_type="purchase_credit_note",
        credit_note_type="commercial_adjustment",
        is_return=True,
        reversal_of=source_id,
        supplier_id=supplier_id,
        supplier_name="Proveedor de prueba",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
    )
    database.session.add(note)
    database.session.flush()
    _line(note.id, item_code, uom_code, amount)
    database.session.commit()
    return note


def _link(source_id: str, source_item_id: str, note: PurchaseInvoice, amount: str, status: str) -> None:
    """Persiste la relación de línea que guarda la captura de la nota."""
    note_item = database.session.execute(select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=note.id)).scalar_one()
    database.session.add(
        DocumentRelation(
            source_type="purchase_invoice",
            source_id=source_id,
            source_item_id=source_item_id,
            target_type="purchase_credit_note",
            target_id=note.id,
            target_item_id=note_item.id,
            company="cacao",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            amount=Decimal(amount),
            relation_type="credit_note",
            status=status,
        )
    )
    database.session.commit()


def _two_line_scenario(status: str) -> tuple[PurchaseInvoice, PurchaseInvoiceItem, PurchaseInvoiceItem]:
    """Factura con dos líneas del mismo artículo y nota enlazada a la segunda."""
    supplier_id, item_code, uom_code = _context()
    invoice = _invoice(supplier_id)
    first = _line(invoice.id, item_code, uom_code, "40")
    second = _line(invoice.id, item_code, uom_code, "60")
    database.session.commit()
    note = _credit_note(supplier_id, invoice.id, item_code, uom_code, "25")
    _link(invoice.id, second.id, note, "25", status)
    return note, first, second


def test_nota_usa_la_linea_de_la_relacion_con_codigo_repetido(entorno_contable_aislado):
    """La relación documental desambigua la línea origen exacta."""
    app = entorno_contable_aislado.app
    with app.app_context():
        note, first, second = _two_line_scenario("active")

        allocations = create_purchase_credit_note_allocations(note.id)

        assert len(allocations) == 1
        assert allocations[0].invoice_item_id == second.id
        assert allocations[0].invoice_item_id != first.id
        assert allocations[0].amount == Decimal("25")
        assert allocations[0].status == "active"


def test_nota_sin_relacion_rechaza_codigo_repetido(entorno_contable_aislado):
    """Sin relación, dos líneas con el mismo código siguen siendo ambiguas."""
    app = entorno_contable_aislado.app
    with app.app_context():
        note, _first, _second = _two_line_scenario("reverted")

        with pytest.raises(PurchaseReconciliationError, match="única línea"):
            create_purchase_credit_note_allocations(note.id)


def test_nota_con_una_sola_linea_conserva_el_flujo_previo(entorno_contable_aislado):
    """Una factura con una única línea no necesita relación documental."""
    app = entorno_contable_aislado.app
    with app.app_context():
        supplier_id, item_code, uom_code = _context()
        invoice = _invoice(supplier_id)
        only_line = _line(invoice.id, item_code, uom_code, "100")
        database.session.commit()
        note = _credit_note(supplier_id, invoice.id, item_code, uom_code, "30")

        allocations = create_purchase_credit_note_allocations(note.id)

        assert len(allocations) == 1
        assert allocations[0].invoice_item_id == only_line.id
        assert allocations[0].amount == Decimal("30")
