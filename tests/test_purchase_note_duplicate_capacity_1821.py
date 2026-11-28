# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1821: un borrador duplicado no consume capacidad de la factura origen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect

from cacao_accounting.compras.services import (
    _compute_credit_capacity,
    _has_active_purchase_reversal_notes,
    _persist_purchase_reversal_relation,
    _validate_purchase_reversal_of,
)
from cacao_accounting.database import (
    Accounts,
    DocumentRelation,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    User,
    database,
)

FECHA = date(2026, 5, 15)


def _document(
    supplier: Party,
    expense_account: Accounts,
    *,
    amount: Decimal,
    document_no: str,
    docstatus: int,
    credit_note: bool,
    reversal_of: str | None = None,
) -> PurchaseInvoice:
    """Crea una factura o nota con línea real y totales coherentes."""
    document = PurchaseInvoice(
        company="cacao",
        posting_date=FECHA,
        document_no=document_no,
        document_type="purchase_credit_note" if credit_note else "purchase_invoice",
        credit_note_type="commercial_adjustment" if credit_note else None,
        is_return=credit_note,
        reversal_of=reversal_of,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        total=amount,
        grand_total=amount,
        base_grand_total=amount,
        outstanding_amount=amount,
        docstatus=docstatus,
    )
    database.session.add(document)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=document.id,
            item_code="ART01",
            item_name="Artículo comercial",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=amount,
            amount=amount,
            base_amount=amount,
            expense_account_id=expense_account.id,
        )
    )
    database.session.flush()
    return document


def _relacion(source: PurchaseInvoice, note: PurchaseInvoice) -> DocumentRelation:
    """Crea la relación canónica de reversión usada por capacidad y AP."""
    _persist_purchase_reversal_relation(note)
    return database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="purchase_invoice",
            source_id=source.id,
            target_type="purchase_credit_note",
            target_id=note.id,
            relation_type="invoice_reversal",
            status="active",
        )
    ).scalar_one()


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(inspect(admin).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def test_nota_borrador_no_consume_capacidad_ni_bloquea_factura(entorno_contable_aislado):
    """Solo la nota aprobada afecta capacidad y dependencias de anulación."""
    app = entorno_contable_aislado.app
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        source = _document(
            supplier,
            expense,
            amount=Decimal("100"),
            document_no=f"PI-1821-{uuid4().hex[:8]}",
            docstatus=1,
            credit_note=False,
        )
        note = _document(
            supplier,
            expense,
            amount=Decimal("40"),
            document_no=f"NC-1821-{uuid4().hex[:8]}",
            docstatus=0,
            credit_note=True,
            reversal_of=source.id,
        )
        _relacion(source, note)
        database.session.commit()

        assert _compute_credit_capacity(source) == Decimal("100")
        assert _has_active_purchase_reversal_notes(source.id) is False

        note.docstatus = 1
        database.session.commit()

        assert _compute_credit_capacity(source) == Decimal("60")
        assert _has_active_purchase_reversal_notes(source.id) is True


def test_duplicado_de_nota_no_se_auto_descuenta_al_validar(entorno_contable_aislado):
    """El borrador copiado no reduce la capacidad disponible para aprobarlo."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        source = _document(
            supplier,
            expense,
            amount=Decimal("100"),
            document_no=f"PI-DUP-1821-{suffix}",
            docstatus=1,
            credit_note=False,
        )
        original = _document(
            supplier,
            expense,
            amount=Decimal("40"),
            document_no=f"NC-DUP-1821-{suffix}",
            docstatus=1,
            credit_note=True,
            reversal_of=source.id,
        )
        _relacion(source, original)
        database.session.commit()
        source_id, original_id = source.id, original.id

    response = _cliente(app).post(f"/buying/purchase-invoice/{original_id}/duplicate")
    assert response.status_code == 302

    with app.app_context():
        source = database.session.get(PurchaseInvoice, source_id)
        duplicate = database.session.execute(
            database.select(PurchaseInvoice).filter_by(
                reversal_of=source_id,
                document_type="purchase_credit_note",
                docstatus=0,
            )
        ).scalar_one()
        assert duplicate.grand_total == Decimal("40")
        copied_relation = database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="purchase_invoice",
                source_id=source_id,
                target_type="purchase_credit_note",
                target_id=duplicate.id,
                status="active",
            )
        ).scalar_one()
        assert copied_relation.amount == Decimal("40")
        assert _compute_credit_capacity(source) == Decimal("60")

        _validate_purchase_reversal_of(
            source_id,
            supplier_id=source.supplier_id,
            company=source.company,
            note_amount=duplicate.grand_total,
            document_type="purchase_credit_note",
            transaction_currency=duplicate.transaction_currency,
        )
