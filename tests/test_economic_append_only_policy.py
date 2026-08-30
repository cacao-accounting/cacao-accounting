# SPDX-License-Identifier: Apache-2.0
"""Tests for the append-only guarantee on pure-evidence economic tables (#759)."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditLog, PurchaseEconomicEvent, database


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con base SQLite en memoria."""
    app = create_app({**configuracion, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        yield app


def test_audit_log_is_append_only(app_ctx) -> None:
    """AuditLog accepts insertion but rejects mutation and deletion."""
    row = AuditLog(entity_type="invoice", entity_id="INV-1", action="insert")
    database.session.add(row)
    database.session.flush()
    assert row.id is not None

    row.action = "update"
    with pytest.raises(ValueError):
        database.session.flush()
    database.session.rollback()

    row = AuditLog(entity_type="invoice", entity_id="INV-2", action="insert")
    database.session.add(row)
    database.session.flush()
    with pytest.raises(ValueError):
        database.session.delete(row)
        database.session.flush()
    database.session.rollback()


def test_purchase_economic_event_is_append_only(app_ctx) -> None:
    """PurchaseEconomicEvent accepts insertion but rejects mutation/deletion."""
    row = PurchaseEconomicEvent(
        event_type="purchase_invoice", document_type="purchase_invoice", document_id="DOC-1", company="r2r"
    )
    database.session.add(row)
    database.session.flush()
    assert row.id is not None

    row.event_type = "sales_invoice"
    with pytest.raises(ValueError):
        database.session.flush()
    database.session.rollback()

    row = PurchaseEconomicEvent(
        event_type="purchase_invoice", document_type="purchase_invoice", document_id="DOC-2", company="r2r"
    )
    database.session.add(row)
    database.session.flush()
    with pytest.raises(ValueError):
        database.session.delete(row)
        database.session.flush()
    database.session.rollback()
