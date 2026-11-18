# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1002: la evidencia de auditoría es inmutable también en Desktop.

Los guardas estructurales deben permitir el INSERT auditado y rechazar
UPDATE/DELETE por ORM, Core y SQL textual, conservando la cadena íntegra.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.audit_chain import verify_audit_trail_chain
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, Currency, database


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
