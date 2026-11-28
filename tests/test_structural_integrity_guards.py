# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Evidencia estructural inmutable en Desktop y Cloud.

Protege los invariantes de #1002 (bitácoras de auditoría) y #759 (eventos
económicos y transiciones documentales): el INSERT auditado está permitido y
UPDATE/DELETE se rechazan por ORM, Core y SQL textual, conservando la fila.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.audit_chain import verify_audit_trail_chain
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    ApprovalAction,
    ApprovalRequest,
    AuditLog,
    AuditTrail,
    Currency,
    DocumentTransition,
    Entity,
    ExchangeRevaluation,
    ExchangeRevaluationItem,
    ExternalCounter,
    ExternalCounterAuditLog,
    FiscalYear,
    PurchaseEconomicEvent,
    User,
    database,
)


def _build_app(desktop: bool):
    """Create an app with the structural guards explicitly enabled."""
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


def _seed_audit_rows(app) -> list[str]:
    """Insert two chained audit events and return their ids."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        first = AuditTrail(
            document_type="sales_invoice",
            document_id=f"INV-1-{suffix}",
            document_no=f"INV-1-{suffix}",
            action="created",
        )
        database.session.add(first)
        database.session.flush()
        second = AuditTrail(
            document_type="sales_invoice",
            document_id=f"INV-2-{suffix}",
            document_no=f"INV-2-{suffix}",
            action="created",
        )
        database.session.add(second)
        database.session.commit()
        ids = [first.id, second.id]
    return ids


@pytest.mark.parametrize("desktop", [True, False])
def test_audit_insert_is_allowed_and_chain_verifies(desktop):
    """The audited insertion path stays open in Desktop and Cloud."""
    app = _build_app(desktop)
    ids = _seed_audit_rows(app)

    with app.app_context():
        rows = database.session.execute(database.select(AuditTrail.id)).scalars().all()
        assert sorted(rows) == sorted(ids)
        assert verify_audit_trail_chain() == []


def test_desktop_rejects_orm_delete_of_the_last_audit_event():
    """Deleting the tail through the session cannot truncate the chain."""
    app = _build_app(desktop=True)
    ids = _seed_audit_rows(app)

    with app.app_context():
        tail = database.session.get(AuditTrail, ids[-1])
        assert tail is not None
        database.session.delete(tail)
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        assert database.session.get(AuditTrail, ids[-1]) is not None
        assert verify_audit_trail_chain() == []


def test_desktop_rejects_orm_update_of_an_audit_event():
    """Rewriting the action of an audit row is rejected."""
    app = _build_app(desktop=True)
    ids = _seed_audit_rows(app)

    with app.app_context():
        row = database.session.get(AuditTrail, ids[0])
        assert row is not None
        row.action = "deleted"
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

    with app.app_context():
        assert database.session.get(AuditTrail, ids[0]).action == "created"
        assert verify_audit_trail_chain() == []


@pytest.mark.parametrize("channel", ["core", "textual"])
def test_desktop_rejects_bulk_audit_delete(channel):
    """Core and textual DELETE cannot bypass the structural guard."""
    app = _build_app(desktop=True)
    ids = _seed_audit_rows(app)

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "core":
                database.session.execute(database.delete(AuditTrail))
                database.session.commit()
            else:
                database.session.execute(text("DELETE FROM audit_trail"))
                database.session.commit()
        database.session.rollback()

    with app.app_context():
        rows = database.session.execute(database.select(AuditTrail.id)).scalars().all()
        assert sorted(rows) == sorted(ids)
        assert verify_audit_trail_chain() == []


def _seed_all_evidence(app) -> dict[str, tuple[type, str, str]]:
    """Create realistic linked evidence rows for all protected audit tables."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        currency = Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True)
        company = Entity(
            code=f"C{suffix}",
            name="Compañía de prueba",
            company_name=f"Compañía evidencia {suffix}",
            tax_id=f"TAX-{suffix}",
            currency="NIO",
            enabled=True,
            status="default",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        user = User(user=f"user-{suffix}", password=b"test-password", active=True, company=company.code)
        database.session.add(user)
        database.session.flush()
        counter = ExternalCounter(company=company.code, name=f"Contador {suffix}", last_used=1)
        database.session.add(counter)
        database.session.flush()
        request = ApprovalRequest(
            document_type="sales_invoice",
            document_id=f"DOC-{suffix}",
            company_id=company.code,
            requested_by=user.id,
            status="Pending Approval",
        )
        database.session.add(request)
        database.session.flush()
        fiscal_year = FiscalYear(
            id=f"FY-{suffix}",
            entity=company.code,
            name=f"Ejercicio {suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fiscal_year)
        database.session.flush()
        period = AccountingPeriod(
            id=f"PER-{suffix}",
            entity=company.code,
            fiscal_year_id=fiscal_year.id,
            name=f"Periodo {suffix}",
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.flush()
        revaluation = ExchangeRevaluation(
            company=company.code,
            document_no=f"REV-{suffix}",
            posting_date=date(2026, 5, 31),
            docstatus=1,
        )
        database.session.add(revaluation)
        database.session.flush()
        revaluation_item = ExchangeRevaluationItem(
            revaluation_id=revaluation.id,
            reference_type="party",
            reference_id=user.id,
            source_document_type="sales_invoice",
            source_document_id=f"DOC-{suffix}",
            source_document_no=f"INV-ORIG-{suffix}",
        )
        economic_event = PurchaseEconomicEvent(
            event_type="GOODS_RECEIVED",
            company=company.code,
            document_type="purchase_receipt",
            document_id=f"REC-{suffix}",
            payload='{"matched_qty": "1"}',
            idempotency_key=f"event-{suffix}",
        )
        transition = DocumentTransition(
            source_type="sales_invoice",
            source_id=f"DOC-{suffix}",
            transition_type="cancel",
            company=company.code,
            posting_date=date(2026, 5, 20),
            accounting_period_id=period.id,
            actor_user_id=user.id,
            reason="Anulación documentada",
        )
        database.session.add_all([revaluation_item, economic_event, transition])
        database.session.flush()
        audit_log = AuditLog(entity_type="sales_invoice", entity_id=f"DOC-{suffix}", action="insert")
        audit_trail = AuditTrail(
            document_type="sales_invoice",
            document_id=f"DOC-{suffix}",
            document_no=f"INV-{suffix}",
            action="created",
        )
        approval_action = ApprovalAction(
            approval_request_id=request.id,
            approved_by=user.id,
            action="approve",
            comments="Aprobación registrada",
        )
        counter_audit = ExternalCounterAuditLog(
            external_counter_id=counter.id,
            previous_value=0,
            new_value=1,
            reason="Ajuste inicial",
        )
        database.session.add_all([audit_log, audit_trail, approval_action, counter_audit])
        database.session.commit()
        return {
            "audit_log": (AuditLog, audit_log.id, "action"),
            "audit_trail": (AuditTrail, audit_trail.id, "action"),
            "approval_action": (ApprovalAction, approval_action.id, "comments"),
            "external_counter_audit_log": (ExternalCounterAuditLog, counter_audit.id, "reason"),
            "exchange_revaluation_item": (ExchangeRevaluationItem, revaluation_item.id, "source_document_no"),
            "purchase_economic_event": (PurchaseEconomicEvent, economic_event.id, "payload"),
            "document_transition": (DocumentTransition, transition.id, "reason"),
        }


@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize(
    "table_name",
    [
        "audit_log",
        "audit_trail",
        "approval_action",
        "external_counter_audit_log",
        "exchange_revaluation_item",
        "purchase_economic_event",
        "document_transition",
    ],
)
@pytest.mark.parametrize("desktop", [True, False])
def test_every_audit_evidence_table_rejects_mutation(channel, operation, table_name, desktop):
    """ORM, Core, and textual SQL preserve structural evidence in Desktop and Cloud."""
    app = _build_app(desktop=desktop)
    evidence = _seed_all_evidence(app)
    model, row_id, field_name = evidence[table_name]

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(model, row_id)
                assert row is not None
                if operation == "delete":
                    database.session.delete(row)
                else:
                    setattr(row, field_name, "tampered")
                database.session.commit()
            elif channel == "core":
                statement = (
                    database.delete(model)
                    if operation == "delete"
                    else database.update(model).values({field_name: "tampered"})
                )
                database.session.execute(statement.where(model.id == row_id))
                database.session.commit()
            else:
                if operation == "delete":
                    statement = text(f"DELETE FROM {table_name} WHERE id = :row_id")
                else:
                    statement = text(f"UPDATE {table_name} SET {field_name} = :value WHERE id = :row_id")
                database.session.execute(statement, {"row_id": row_id, "value": "tampered"})
                database.session.commit()
        database.session.rollback()

    with app.app_context():
        row = database.session.get(model, row_id)
        assert row is not None
        assert getattr(row, field_name) != "tampered"
        if table_name == "audit_trail":
            assert verify_audit_trail_chain() == []
