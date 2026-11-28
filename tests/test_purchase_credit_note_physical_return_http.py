# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2355: creación y aprobación HTTP de la nota por devolución física."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from test_purchase_receipt_return_posting import (
    ITEM_CODE,
    SUPPLIER_CODE,
    UOM_CODE,
    WAREHOUSE_CODE,
    _post,
    _receipt,
    _seed_bridge_and_warehouse_account,
)

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting import cancel_document, submit_document
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    DocumentRelation,
    GLEntry,
    Item,
    Party,
    PurchaseCreditNoteAllocation,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database


def _client(app, user_id: str):
    """Autentica un cliente HTTP real contra la app aislada del escenario."""
    client = app.test_client()
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def _seed_posted_return(app) -> dict[str, str]:
    """Publica factura origen y devolución física con sus asignaciones activas."""
    with app.app_context():
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        if (
            database.session.execute(
                database.select(UserCompanyAccess).filter_by(user_id=actor.id, company_code="cacao")
            ).scalar_one_or_none()
            is None
        ):
            database.session.add(UserCompanyAccess(user_id=actor.id, company_code="cacao"))
        matching = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching is None:
            database.session.add(PurchaseMatchingConfig(company="cacao", require_purchase_order=False))
        else:
            matching.require_purchase_order = False
        database.session.commit()
        supplier = database.session.execute(database.select(Party).filter_by(code=SUPPLIER_CODE)).scalar_one()
        settings = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=supplier.id, company="cacao")
        ).scalar_one_or_none()
        if settings is None:
            settings = CompanyParty(company="cacao", party_id=supplier.id)
            database.session.add(settings)
        settings.allow_purchase_invoice_without_order = True
        settings.allow_purchase_invoice_without_receipt = True
        item = database.session.execute(database.select(Item).filter_by(code=ITEM_CODE)).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code=UOM_CODE)).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()

        original_receipt = _receipt(is_return=False, reversal_of=None, qty="10", amount="100")
        _post(original_receipt, actor)
        source_invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            document_no=f"PI-HTTP-{uuid4().hex[:8]}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_receipt_id=original_receipt.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(source_invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=source_invoice.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom=uom.code,
                rate=Decimal("10"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
                expense_account_id=expense.id,
                warehouse=WAREHOUSE_CODE,
            )
        )
        database.session.commit()
        with audit_actor(actor.id, actor.name), approved_execution(source_invoice, actor.id):
            submit_document(source_invoice)
        database.session.commit()

        returned = _receipt(is_return=True, reversal_of=original_receipt.id, qty="4", amount="40")
        _post(returned, actor)
        return_item = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=returned.id)
        ).scalar_one()
        result = {
            "actor_id": str(actor.id),
            "supplier_id": str(supplier.id),
            "source_invoice_id": str(source_invoice.id),
            "return_id": str(returned.id),
            "return_item_id": str(return_item.id),
        }
        database.session.remove()
        return result


def _create_note(client, ids: dict[str, str]) -> str | None:
    """Crea la nota física por el POST real y devuelve su identificador."""
    response = client.post(
        "/buying/purchase-invoice/new",
        data={
            "company": "cacao",
            "supplier_id": ids["supplier_id"],
            "posting_date": "2026-05-20",
            "transaction_currency": "NIO",
            "document_type": "purchase_credit_note",
            "credit_note_type": "physical_return",
            "from_invoice": ids["source_invoice_id"],
            "from_receipt": ids["return_id"],
            "item_code_0": ITEM_CODE,
            "item_name_0": "Artículo devuelto",
            "qty_0": "4",
            "uom_0": UOM_CODE,
            "rate_0": "10",
            "source_type_0": "purchase_receipt",
            "source_id_0": ids["return_id"],
            "source_item_id_0": ids["return_item_id"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, response.get_data(as_text=True)
    location = response.headers["Location"].rstrip("/")
    return location.rsplit("/", 1)[-1] if location else None


def _note_evidence(note_id: str) -> tuple[PurchaseInvoice, list, list]:
    """Devuelve el estado de la nota y sus evidencias de asignación y GL."""
    note = database.session.get(PurchaseInvoice, note_id)
    item_ids = [
        item.id
        for item in database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=note_id)
        ).scalars()
    ]
    allocations = (
        database.session.execute(
            database.select(PurchaseCreditNoteAllocation).where(PurchaseCreditNoteAllocation.credit_note_item_id.in_(item_ids))
        )
        .scalars()
        .all()
    )
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=note_id)).scalars().all()
    return note, allocations, gl_entries


def test_nota_fisica_aprobada_por_post_contabiliza_una_asignacion(entorno_contable_aislado):
    """Crear y aprobar por HTTP deja una asignación y GL sin duplicar líneas."""
    app = entorno_contable_aislado.app
    _seed_bridge_and_warehouse_account(entorno_contable_aislado)
    ids = _seed_posted_return(app)
    client = _client(app, ids["actor_id"])

    note_id = _create_note(client, ids)
    assert note_id
    submitted = client.post(f"/buying/purchase-invoice/{note_id}/submit")

    assert submitted.status_code == 302
    with app.app_context():
        note, allocations, gl_entries = _note_evidence(note_id)
        assert note.docstatus == 1
        assert len(allocations) == 1
        assert allocations[0].allocation_type == "physical_return"
        assert gl_entries
        relations = (
            database.session.execute(
                database.select(DocumentRelation).filter_by(
                    target_type="purchase_invoice", target_id=note_id, source_type="purchase_receipt"
                )
            )
            .scalars()
            .all()
        )
        assert len(relations) == 1
        database.session.remove()


def test_nota_fisica_con_devolucion_cancelada_no_contabiliza(entorno_contable_aislado):
    """El POST de aprobación rechaza la nota y no deja evidencias parciales."""
    app = entorno_contable_aislado.app
    _seed_bridge_and_warehouse_account(entorno_contable_aislado)
    ids = _seed_posted_return(app)
    client = _client(app, ids["actor_id"])
    note_id = _create_note(client, ids)
    assert note_id

    with app.app_context():
        actor = database.session.get(User, ids["actor_id"])
        returned = database.session.get(PurchaseReceipt, ids["return_id"])
        with audit_actor(actor.id, actor.name), approved_execution(returned, actor.id):
            cancel_document(
                returned,
                reason="Cancelación previa a la nota",
                actor_user_id=actor.id,
                cancellation_date=returned.posting_date,
            )
        database.session.commit()

    response = client.post(f"/buying/purchase-invoice/{note_id}/submit", follow_redirects=True)

    assert response.status_code == 200
    assert "aprobad" in response.get_data(as_text=True)
    with app.app_context():
        note, allocations, gl_entries = _note_evidence(note_id)
        assert note.docstatus == 0
        assert allocations == []
        assert gl_entries == []
        database.session.remove()
