# SPDX-License-Identifier: Apache-2.0
"""Verify transactional Cloud evidence and financial mutation boundaries."""

from datetime import date
import json

import pytest
from sqlalchemy import delete, text, update

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalAction,
    ApprovalRequest,
    AuditTrail,
    CacaoConfig,
    ComprobanteContable,
    DocumentRelation,
    Entity,
    GLEntry,
    PurchaseReconciliation,
    PurchaseMatchingConfig,
    Roles,
    SalesInvoice,
    SalesInvoiceItem,
    User,
    database,
)
from cacao_accounting.internal_control_service import audit_actor, current_audit_actor, register_internal_controls


@pytest.fixture()
def app():
    """Create isolated Cloud data with the real flush and SQL listeners."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Entity(code="co", company_name="Company", tax_id="tax", name="Company"))
        database.session.add(User(id="actor", user="actor", password=b"x", active=True))
        database.session.commit()
        yield application
        database.session.rollback()
        database.session.remove()
        database.engine.dispose()


def _event(document_id):
    """Return the last automatic event for a document."""
    return (
        database.session.execute(
            database.select(AuditTrail)
            .where(AuditTrail.document_id == document_id)
            .order_by(AuditTrail.timestamp.desc(), AuditTrail.id.desc())
        )
        .scalars()
        .first()
    )


def test_sensitive_changes_share_commit_and_actor(app):
    """Sensitive snapshots preserve old/new values and explicit job attribution."""
    role = Roles(name="custom", note="Original")
    with audit_actor("actor", "job:role-maintenance"):
        database.session.add(role)
        database.session.flush()
        original = _event(role.id)
        assert original.actor_user_id == "actor"
        assert original.actor_name == "job:role-maintenance"
        role.note = "Updated"
        database.session.flush()
        event = _event(role.id)
        assert json.loads(event.changes_json)["note"] == {"before": "Original", "after": "Updated"}
        role_id = role.id
        database.session.rollback()
    assert database.session.get(Roles, role_id) is None
    assert _event(role_id) is None
    assert current_audit_actor() == (None, "system")


def test_sensitive_delete_and_secret_configuration_exclusion(app):
    """Sensitive assignments cannot be deleted and secret settings stay private."""
    role = Roles(name="custom", note="Custom")
    database.session.add(role)
    database.session.commit()
    role_id = role.id
    database.session.delete(role)
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.flush()
    database.session.rollback()
    assert database.session.get(Roles, role_id) is not None
    secret = CacaoConfig(key="smtp_password", value="secret")
    option = CacaoConfig(key="approval_engine_enabled_co", value="1")
    database.session.add_all([secret, option])
    database.session.flush()
    assert _event(secret.id) is None
    assert _event(option.id).action == "created"
    register_internal_controls()
    with pytest.raises(ValueError):
        with audit_actor(None, " "):
            pass


@pytest.mark.parametrize("mode", ["orm_update", "orm_delete", "core_update", "core_delete"])
def test_evidence_is_append_only(app, mode):
    """Reject each normal SQLAlchemy mutation path for audit evidence."""
    entry = AuditTrail(document_type="test", document_id="doc", action="created")
    database.session.add(entry)
    database.session.commit()
    with pytest.raises(ValueError, match="inmutable"):
        if mode == "orm_update":
            entry.comment = "tampered"
            database.session.flush()
        elif mode == "orm_delete":
            database.session.delete(entry)
            database.session.flush()
        elif mode == "core_update":
            database.session.execute(update(AuditTrail).values(comment="tampered"))
        else:
            database.session.execute(delete(AuditTrail))


def test_approval_action_and_policy_cannot_be_rewritten(app):
    """Approval provenance is fixed but its processing status can advance."""
    request = ApprovalRequest(
        document_type="test",
        document_id="doc",
        company_id="co",
        requested_by="actor",
        policy_snapshot={"requires_independent": True},
        review_payload={"reason": "review"},
    )
    database.session.add(request)
    database.session.flush()
    action = ApprovalAction(approval_request_id=request.id, approved_by="actor", action="approve")
    database.session.add(action)
    database.session.commit()
    from cacao_accounting.internal_control_service import approval_request_transition

    with approval_request_transition(request):
        request.status = "Approved"
        database.session.flush()
    request.policy_snapshot = {"requires_independent": False}
    with pytest.raises(ValueError, match="inmutable"):
        database.session.flush()
    database.session.rollback()
    request.cancellation_reason = "forged"
    with pytest.raises(ValueError, match="inmutable"):
        database.session.flush()
    database.session.rollback()
    database.session.delete(action)
    with pytest.raises(ValueError, match="inmutable"):
        database.session.flush()


def test_approval_transition_scope_is_limited_to_target_request(app):
    """One authorized request cannot piggyback another dirty request in the flush."""
    requests = [
        ApprovalRequest(document_type="test", document_id=f"doc-{index}", company_id="co", requested_by="actor")
        for index in range(2)
    ]
    database.session.add_all(requests)
    database.session.commit()
    from cacao_accounting.internal_control_service import approval_request_transition

    requests[0].status = "Approved"
    requests[1].status = "Approved"
    with approval_request_transition(requests[0]):
        with pytest.raises(ValueError, match="servicio autorizado"):
            database.session.flush()
    database.session.rollback()


def test_request_required_level_cannot_be_weakened(app):
    """El nivel de four-eyes congelado no puede revaluarse a la baja."""
    request = ApprovalRequest(
        document_type="test",
        document_id="doc-922",
        company_id="co",
        requested_by="actor",
        required_level=3,
        policy_snapshot={"requires_independent": True},
    )
    database.session.add(request)
    database.session.commit()
    request.required_level = 1
    with pytest.raises(ValueError, match="inmutable"):
        database.session.flush()
    database.session.rollback()
    with pytest.raises(ValueError, match="servicio autorizado"):
        database.session.connection().execute(
            update(ApprovalRequest).where(ApprovalRequest.id == request.id).values(status="Approved")
        )
    database.session.rollback()
    request.policy_snapshot = {"requires_independent": False}
    with pytest.raises(ValueError, match="inmutable"):
        database.session.flush()
    database.session.rollback()
    with pytest.raises(ValueError, match="inmutable"):
        database.session.connection().execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == request.id)
            .values(required_level=1, policy_snapshot={"requires_independent": False})
        )
    database.session.rollback()
    with pytest.raises(ValueError, match="servicio autorizado"):
        request.status = "Approved"
        database.session.flush()
    database.session.rollback()
    with pytest.raises(ValueError, match="servicio autorizado"):
        request.current_level = 3
        database.session.flush()
    database.session.rollback()
    from cacao_accounting.internal_control_service import approval_request_transition

    with approval_request_transition(request):
        request.current_level = 3
        database.session.flush()


def test_posted_header_and_line_protected_but_balances_and_cancellation_mutable(app):
    """Financial evidence stays fixed; derived balances and lifecycle may change."""
    invoice = SalesInvoice(company="co", docstatus=1, total=100, posting_date=date.today())
    database.session.add(invoice)
    database.session.flush()
    line = SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="item", qty=1, rate=100, amount=100)
    database.session.add(line)
    database.session.commit()
    invoice.outstanding_amount = 50
    invoice.docstatus = 2
    database.session.flush()
    invoice.total = 200
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()
    database.session.rollback()
    line.amount = 200
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()
    database.session.rollback()
    database.session.delete(invoice)
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()


def test_draft_and_desktop_compatibility(app):
    """Draft edits work and Desktop incurs no extra control requirement."""
    invoice = SalesInvoice(company="co", docstatus=0, total=100)
    database.session.add(invoice)
    database.session.commit()
    invoice.total = 200
    database.session.flush()
    app.config["MODO_ESCRITORIO"] = True
    role = Roles(name="desktop", note="Desktop")
    database.session.add(role)
    database.session.flush()
    assert _event(role.id) is None
    event = _event(invoice.id)
    event.comment = "Desktop legacy behavior"
    database.session.flush()


def test_sensitive_bulk_mutation_is_rejected(app):
    """Bulk SQL cannot bypass per-row configuration evidence."""
    database.session.add(Roles(name="custom", note="Custom"))
    database.session.commit()
    with pytest.raises(ValueError, match="auditado"):
        database.session.execute(update(Roles).values(note="No actor"))


def test_journal_posted_fields_and_line_guard(app):
    """Legacy journals use their applied timestamp instead of DocBase flags."""
    from datetime import datetime, timezone

    journal = ComprobanteContable(entity="co", applied=datetime.now(timezone.utc), memo="Posted")
    database.session.add(journal)
    database.session.commit()
    journal.memo = "Changed"
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()


def test_internal_control_schema_columns_exist(app):
    """Las columnas de control se crean con create_all; no se aplican migraciones incrementales."""
    from sqlalchemy import inspect

    inspector = inspect(database.engine)
    roles_access = {column["name"] for column in inspector.get_columns("roles_access")}
    approval_request = {column["name"] for column in inspector.get_columns("approval_request")}
    assert "approval_rank" in roles_access
    assert {"policy_snapshot", "review_payload"}.issubset(approval_request)


def test_bulk_and_text_cannot_rewrite_financial_evidence(app):
    """Core, raw SQL and legacy detail writes obey the same financial boundary."""
    from sqlalchemy import text
    from cacao_accounting.database import ComprobanteContableDetalle
    from datetime import datetime, timezone

    draft = SalesInvoice(company="co", docstatus=0, total=10)
    posted = SalesInvoice(company="co", docstatus=1, total=20)
    journal = ComprobanteContable(entity="co", applied=datetime.now(timezone.utc), memo="Posted")
    database.session.add_all([draft, posted, journal])
    database.session.flush()
    line = SalesInvoiceItem(sales_invoice_id=posted.id, item_code="item", qty=1, rate=20, amount=20)
    detail = ComprobanteContableDetalle(transaction_id=journal.id, value=10)
    database.session.add_all([line, detail])
    database.session.commit()
    database.session.execute(update(SalesInvoice).where(SalesInvoice.id == draft.id).values(total=30))
    database.session.execute(update(SalesInvoice).where(SalesInvoice.id == posted.id).values(outstanding_amount=5))
    database.session.flush()
    for statement in (
        update(SalesInvoice).where(SalesInvoice.id == posted.id).values(total=50),
        delete(SalesInvoice).where(SalesInvoice.id == posted.id),
        update(SalesInvoiceItem).where(SalesInvoiceItem.id == line.id).values(amount=50),
        update(ComprobanteContableDetalle).where(ComprobanteContableDetalle.id == detail.id).values(value=50),
        text("UPDATE audit_trail SET comment = 'tampered'"),
    ):
        with pytest.raises(ValueError):
            database.session.execute(statement)
    with pytest.raises(ValueError):
        database.session.connection().exec_driver_sql("DELETE FROM audit_trail")
    detail.value = 50
    with pytest.raises(ValueError):
        database.session.flush()


def test_request_bulk_and_delete_guards(app):
    """A request cannot be removed or have its policy replaced using bulk SQL."""
    request = ApprovalRequest(document_type="test", document_id="doc", company_id="co", requested_by="actor")
    database.session.add(request)
    database.session.commit()
    with pytest.raises(ValueError):
        database.session.execute(update(ApprovalRequest).values(policy_snapshot={"requires_independent": False}))
    with pytest.raises(ValueError):
        database.session.connection().execute(delete(ApprovalRequest))
    database.session.delete(request)
    with pytest.raises(ValueError):
        database.session.flush()


def test_request_parameterized_connection_update_is_blocked(app):
    """Connection parameters cannot bypass approval transition guards."""
    request = ApprovalRequest(document_type="test", document_id="doc", company_id="co", requested_by="actor")
    database.session.add(request)
    database.session.commit()
    statement = update(ApprovalRequest).where(ApprovalRequest.id == request.id)
    with pytest.raises(ValueError, match="servicio autorizado"):
        database.session.connection().execute(statement, {"status": "Approved"})
    database.session.rollback()


def test_request_textual_sql_update_is_blocked(app):
    """Text SQL cannot bypass immutable ApprovalRequest evidence guards."""
    request = ApprovalRequest(
        document_type="test",
        document_id="doc-922-text",
        company_id="co",
        requested_by="actor",
        required_level=3,
        policy_snapshot={"requires_independent": True},
    )
    database.session.add(request)
    database.session.commit()

    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(
            text("UPDATE approval_request SET required_level = :required_level WHERE id = :request_id"),
            {"required_level": 1, "request_id": request.id},
        )

    database.session.rollback()
    database.session.refresh(request)
    assert request.required_level == 3
    assert request.policy_snapshot == {"requires_independent": True}


def test_explicit_actor_reaches_manual_audit_service_and_user_snapshot_is_safe(app):
    """Explicit automation attribution also applies to existing audit APIs."""
    from cacao_accounting.audit_trail_service import log_create

    actor = database.session.get(User, "actor")
    event = _event(actor.id)
    assert "password" not in json.loads(event.after_json)
    with audit_actor("actor", "job:testing"):
        entry = log_create({"id": "document", "document_type": "test", "company_id": "co"})
        database.session.flush()
        assert entry.actor_user_id == "actor"
        assert entry.actor_name == "job:testing"
        assert entry.company == "co"


def test_maker_stamps_follow_financial_edits_only(app):
    """Persist original maker and most recent financial editor from explicit actors."""
    other = User(id="other", user="other", password=b"x", active=True)
    database.session.add(other)
    database.session.flush()
    with audit_actor("actor", "Maker"):
        invoice = SalesInvoice(company="co", docstatus=0, total=10)
        journal = ComprobanteContable(entity="co", memo="Draft")
        database.session.add_all([invoice, journal])
        database.session.commit()
    assert invoice.created_by == "actor"
    assert journal.created_by == "actor"
    assert _event(journal.id).source_module == "internal_control"
    with audit_actor("other", "Editor"):
        invoice.total = 20
        database.session.flush()
    assert invoice.modified_by == "other"
    with audit_actor("actor", "Reviewer"):
        invoice.status = "Pending Approval"
        database.session.flush()
    assert invoice.modified_by == "other"


def test_posted_document_cannot_be_reset_or_receive_new_lines(app):
    """Lifecycle flags cannot reopen financial values or append documentary lines."""
    from cacao_accounting.database import GLEntry

    invoice = SalesInvoice(company="co", docstatus=1, total=10)
    database.session.add(invoice)
    database.session.flush()
    entry = GLEntry(
        company="co",
        voucher_type="sales_invoice",
        voucher_id=invoice.id,
        posting_date=date.today(),
        account_id="account",
        debit=10,
        credit=0,
    )
    database.session.add(entry)
    database.session.commit()
    invoice.docstatus = 0
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()
    database.session.rollback()
    with pytest.raises(ValueError, match="financieros"):
        database.session.execute(update(SalesInvoice).where(SalesInvoice.id == invoice.id).values(docstatus=0))
    database.session.add(SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="item", qty=1, rate=5, amount=5))
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()


def test_draft_line_edits_stamp_parent_editor_and_legacy_draft_reset_is_blocked(app):
    """A line editor cannot conceal their maker role by leaving header totals unchanged."""
    invoice = SalesInvoice(company="co", docstatus=0, total=10)
    database.session.add(invoice)
    database.session.flush()
    line = SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="item", qty=1, rate=10, amount=10)
    with audit_actor("actor", "Maker"):
        database.session.add(line)
        database.session.flush()
    assert invoice.modified_by == "actor"
    invoice.modified_by = None
    with audit_actor("actor", "Editor"):
        line.qty = 2
        database.session.flush()
    assert invoice.modified_by == "actor"
    journal = ComprobanteContable(entity="co", status="submitted", memo="Posted")
    database.session.add(journal)
    database.session.commit()
    journal.status = "draft"
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()


def test_posted_advance_can_append_allocation_reference(app):
    """A later advance allocation adds evidence without rewriting the posted payment."""
    from cacao_accounting.database import GLEntry, PaymentEntry, PaymentReference

    payment = PaymentEntry(company="co", docstatus=1, payment_type="receive", received_amount=100, is_advance=True)
    database.session.add(payment)
    database.session.flush()
    database.session.add(
        GLEntry(
            company="co", posting_date=date.today(), voucher_type="payment_entry", voucher_id=payment.id, debit=100, credit=0
        )
    )
    database.session.commit()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id="invoice",
        allocated_amount=50,
        allocation_date=date.today(),
    )
    database.session.add(reference)
    payment.unallocated_amount = 50
    database.session.flush()
    assert reference.id
    assert payment.unallocated_amount == 50
    reference.allocated_amount = 100
    with pytest.raises(ValueError, match="financieros"):
        database.session.flush()


def test_matching_config_changes_are_audited(app):
    """Los cambios al motor de matching dejan evidencia con valores previos."""
    from cacao_accounting.database import PurchaseMatchingConfig

    config = PurchaseMatchingConfig(
        company="co",
        matching_type="3-way",
        price_tolerance_value=0,
        auto_reconcile=True,
        allow_price_difference=False,
    )
    database.session.add(config)
    database.session.commit()
    created = _event(config.id)
    assert created is not None
    assert created.action == "created"
    config.matching_type = "2-way"
    config.allow_price_difference = True
    database.session.flush()
    event = _event(config.id)
    assert event.action == "updated"
    changes = json.loads(event.changes_json)
    assert changes["matching_type"]["before"] == "3-way"
    assert changes["matching_type"]["after"] == "2-way"
    assert changes["allow_price_difference"]["after"] is True


def test_matching_config_bulk_mutation_is_rejected(app):
    """La configuración de matching solo se modifica por la vía auditada."""
    from sqlalchemy import text

    from cacao_accounting.database import PurchaseMatchingConfig, SalesMatchingConfig

    database.session.add(PurchaseMatchingConfig(company="co"))
    database.session.add(SalesMatchingConfig(company="co"))
    database.session.commit()
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.execute(update(PurchaseMatchingConfig).values(auto_reconcile=False))
    database.session.rollback()
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(text("DELETE FROM sales_matching_config"))
    database.session.rollback()


def _ledger_row():
    """Create an isolated GL ledger line for cancellation-boundary tests."""
    entry = GLEntry(
        company="co",
        posting_date=date.today(),
        debit=100,
        credit=0,
        voucher_type="test_document",
        voucher_id="v-925",
    )
    database.session.add(entry)
    database.session.commit()
    return entry


def test_ledger_cancellation_is_monotonic(app):
    """La cancelación del ledger va en una sola dirección False -> True."""
    entry = _ledger_row()
    entry.is_cancelled = True
    database.session.flush()
    database.session.commit()
    assert database.session.get(GLEntry, entry.id).is_cancelled is True
    # La reactivación directa queda bloqueada a nivel de ORM.
    entry.is_cancelled = False
    with pytest.raises(ValueError, match="no se reactiva"):
        database.session.flush()
    database.session.rollback()
    assert database.session.get(GLEntry, entry.id).is_cancelled is True


def test_ledger_reactivation_via_sql_core_is_blocked(app):
    """La vía Core no puede reactivar una línea del ledger cancelada."""
    entry = _ledger_row()
    entry.is_cancelled = True
    database.session.flush()
    database.session.commit()
    with pytest.raises(ValueError, match="no se reactiva"):
        database.session.connection().execute(update(GLEntry).where(GLEntry.id == entry.id).values(is_cancelled=False))
    database.session.rollback()
    assert database.session.get(GLEntry, entry.id).is_cancelled is True


def test_ledger_reactivation_via_orm_bulk_is_blocked(app):
    """Los UPDATE bulk del ORM tampoco pueden reactivar la evidencia."""
    entry = _ledger_row()
    entry.is_cancelled = True
    database.session.flush()
    database.session.commit()
    with pytest.raises(ValueError, match="no se reactiva"):
        database.session.execute(update(GLEntry).values(is_cancelled=False))
    database.session.rollback()
    assert database.session.get(GLEntry, entry.id).is_cancelled is True


def test_ledger_bulk_cancellation_remains_allowed(app):
    """Cancelar por Core sigue permitido (dirección monotónica)."""
    entry = _ledger_row()
    database.session.connection().execute(update(GLEntry).where(GLEntry.id == entry.id).values(is_cancelled=True))
    database.session.commit()
    database.session.expire_all()
    assert database.session.get(GLEntry, entry.id).is_cancelled is True


def _document_relation(suffix: str = "923"):
    relation = DocumentRelation(
        company="co",
        source_type="sales_order",
        source_id=f"so-{suffix}",
        target_type="sales_invoice",
        target_id=f"inv-{suffix}",
        relation_type="derived_from",
        qty=2,
    )
    database.session.add(relation)
    database.session.commit()
    return relation


def test_document_relation_core_rewrite_is_blocked(app):
    """Un UPDATE Core no reescribe la cantidad consumida de una relación."""
    relation = _document_relation()
    with pytest.raises(ValueError, match="transiciones documentales"):
        database.session.connection().execute(
            update(DocumentRelation).where(DocumentRelation.id == relation.id).values(qty=200)
        )
    database.session.rollback()
    assert database.session.get(DocumentRelation, relation.id).qty == 2


def test_document_relation_delete_via_core_is_blocked(app):
    """La relación documental no admite borrado por SQL Core."""
    relation = _document_relation()
    with pytest.raises(ValueError, match="no se elimina"):
        database.session.connection().execute(delete(DocumentRelation).where(DocumentRelation.id == relation.id))
    database.session.rollback()


def test_document_relation_parameterized_transition_is_blocked(app):
    """Parameterized Connection updates cannot bypass document-flow services."""
    relation = _document_relation()
    statement = update(DocumentRelation).where(DocumentRelation.id == relation.id)
    with pytest.raises(ValueError, match="transiciones documentales"):
        database.session.connection().execute(statement, {"status": "reverted"})
    database.session.rollback()


def test_document_relation_transition_is_audited_and_not_reactivated(app):
    """Reversión queda auditada y una relación revertida no se reactiva."""
    relation = _document_relation()
    from cacao_accounting.document_flow.service import revert_relations_for_target

    revert_relations_for_target(relation.target_type, relation.target_id, reason="test_reversal")
    event = _event(relation.id)
    assert event.action == "updated"
    assert json.loads(event.changes_json)["status"]["after"] == "reverted"
    database.session.commit()
    # La reversión es monotónica: se agrega una relación nueva si se corrige.
    relation.status = "active"
    with pytest.raises(ValueError, match="no se reactiva"):
        database.session.flush()
    database.session.rollback()


def test_document_relation_qty_via_orm_is_blocked(app):
    """La mutación ORM de evidencia del flujo también queda bloqueada."""
    relation = _document_relation()
    relation.qty = 999
    with pytest.raises(ValueError, match="vínculos documentales"):
        database.session.flush()
    database.session.rollback()


def test_flow_transition_scope_is_limited_to_target_relation(app):
    """One authorized flow relation cannot piggyback another dirty relation."""
    relations = [_document_relation("one"), _document_relation("two")]
    from cacao_accounting.internal_control_service import flow_evidence_transition

    relations[0].status = "reverted"
    relations[1].status = "reverted"
    with flow_evidence_transition(relations[0]):
        with pytest.raises(ValueError, match="servicio autorizado"):
            database.session.flush()
    database.session.rollback()


def test_purchase_reconciliation_evidence_is_guarded(app):
    """Conciliaciones: sin borrado y con transiciones únicamente por estado."""
    reconciliation = PurchaseReconciliation(
        company="co",
        matching_type="3-way",
        purchase_invoice_id="pinv-1",
        matched_amount=10,
        matched_date=date.today(),
        status="reconciled",
    )
    database.session.add(reconciliation)
    database.session.commit()
    with pytest.raises(ValueError, match="no se elimina"):
        database.session.connection().execute(
            delete(PurchaseReconciliation).where(PurchaseReconciliation.id == reconciliation.id)
        )
    database.session.rollback()
    # Una asignación ORM directa no emite el evento económico de cancelación.
    reconciliation.status = "cancelled"
    with pytest.raises(ValueError, match="servicio autorizado"):
        database.session.flush()
    database.session.rollback()
    from cacao_accounting.compras.purchase_reconciliation_service import cancel_purchase_reconciliation

    cancel_purchase_reconciliation(reconciliation.purchase_invoice_id)
    event = _event(reconciliation.id)
    assert event.action == "updated"
    assert json.loads(event.changes_json)["status"]["after"] == "cancelled"
    database.session.rollback()


def test_purchase_reconciliation_match_result_is_immutable(app):
    """Matching figures are evidence and cannot be rewritten after creation."""
    reconciliation = PurchaseReconciliation(
        company="co",
        matching_type="3-way",
        purchase_invoice_id="pinv-immutable",
        matched_amount=10,
        matched_date=date.today(),
        status="reconciled",
    )
    database.session.add(reconciliation)
    database.session.commit()
    reconciliation.matched_amount = 20
    with pytest.raises(ValueError, match="vínculos documentales"):
        database.session.flush()
    database.session.rollback()
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(
            update(PurchaseReconciliation).where(PurchaseReconciliation.id == reconciliation.id).values(status="cancelled")
        )
    database.session.rollback()


def test_matching_config_connection_update_is_rejected(app):
    """Compiled Connection updates cannot bypass matching-config auditing."""
    config = PurchaseMatchingConfig(company="co", matching_type="3-way")
    database.session.add(config)
    database.session.commit()
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(
            update(PurchaseMatchingConfig).where(PurchaseMatchingConfig.id == config.id).values(matching_type="2-way")
        )
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(
            update(PurchaseMatchingConfig).where(PurchaseMatchingConfig.id == config.id), {"matching_type": "2-way"}
        )
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(delete(PurchaseMatchingConfig).where(PurchaseMatchingConfig.id == config.id))


def test_sensitive_config_keys_via_core_are_blocked(app):
    """Connection updates can never rewrite application configuration."""
    config = CacaoConfig(key="approval_engine_enabled_co", value="1")
    database.session.add(config)
    database.session.commit()
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(update(CacaoConfig).where(CacaoConfig.key == config.key).values(value="0"))
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(update(CacaoConfig).where(CacaoConfig.key == config.key), {"value": "0"})
    with pytest.raises(ValueError, match="servicio auditado"):
        database.session.connection().execute(delete(CacaoConfig).where(CacaoConfig.key == config.key))
    database.session.rollback()
    plain = CacaoConfig(key="ui_locale", value="es")
    database.session.add(plain)
    database.session.commit()
    plain.value = "en"
    database.session.commit()
    refreshed = database.session.execute(database.select(CacaoConfig).filter_by(key="ui_locale")).scalar_one()
    assert refreshed.value == "en"
