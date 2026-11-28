# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regression coverage for writes against a broken audit-chain topology."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.audit_chain import stamp_audit_values
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditChainState, AuditTrail, database


def _build_app():
    """Create an isolated application database for audit-chain writes."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def _seed_cycle(app, *, clear_head: bool) -> tuple[str, str]:
    """Create valid evidence, then corrupt only its links into a two-row cycle."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        first = AuditTrail(document_type="invoice", document_id=f"INV-{suffix}-1", action="created")
        second = AuditTrail(document_type="invoice", document_id=f"INV-{suffix}-2", action="created")
        database.session.add_all([first, second])
        database.session.commit()
        first_id, second_id = first.id, second.id
        first_hash, second_hash = first.payload_hash, second.payload_hash

        raw_connection = database.engine.raw_connection()
        try:
            raw_dbapi = raw_connection.driver_connection
            raw_dbapi.execute("UPDATE audit_trail SET prev_hash = ? WHERE id = ?", (second_hash, first_id))
            raw_dbapi.execute("UPDATE audit_trail SET prev_hash = ? WHERE id = ?", (first_hash, second_id))
            if clear_head:
                raw_dbapi.execute("UPDATE audit_chain_state SET head_hash = NULL WHERE id = 'main'")
            raw_dbapi.commit()
        finally:
            raw_connection.close()
    return first_id, second_id


@pytest.mark.parametrize("write_path", ["orm", "core"])
@pytest.mark.parametrize("clear_head", [False, True])
def test_audit_chain_cycle_blocks_orm_and_core_writes(write_path, clear_head):
    """Neither a stale pointer nor a missing pointer can start a second root."""
    app = _build_app()
    first_id, second_id = _seed_cycle(app, clear_head=clear_head)

    with app.app_context():
        original_head = database.session.get(AuditChainState, "main").head_hash
        with pytest.raises(RuntimeError, match="cadena de auditoría|cabeza de la cadena"):
            if write_path == "orm":
                database.session.add(AuditTrail(document_type="invoice", document_id="INV-NUEVA", action="created"))
                database.session.commit()
            else:
                with database.engine.begin() as connection:
                    stamp_audit_values(
                        connection,
                        {"id": "AUDIT-NUEVA", "action": "created", "document_type": "invoice"},
                    )

        database.session.rollback()
        database.session.expire_all()
        assert database.session.get(AuditTrail, first_id) is not None
        assert database.session.get(AuditTrail, second_id) is not None
        assert database.session.scalar(database.select(database.func.count()).select_from(AuditTrail)) == 2
        assert database.session.get(AuditChainState, "main").head_hash == original_head
