# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1749: el diario no debe anunciar una aprobación sin regla configurada."""

from __future__ import annotations

from typing import NamedTuple
from uuid import uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import create_journal_draft
from cacao_accounting.database import (
    ApprovalMatrix,
    ApprovalAction,
    ApprovalRequest,
    CacaoConfig,
    ComprobanteContable,
    ComprobanteContableDetalle,
    GLEntry,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    database,
)


class ApprovalConfigSnapshot(NamedTuple):
    """Approval settings and rules temporarily changed by this test."""

    old_mode_present: bool
    old_mode: bool
    old_config: str | None
    created_config: bool
    rule_states: list[tuple[ApprovalMatrix, bool]]
    role_id: str


def _journal_payload(reference: str) -> dict[str, object]:
    """Build a balanced journal for the accounting fixture."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "reference": reference,
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }


def _configure_missing_matrix(app, writer: User) -> ApprovalConfigSnapshot:
    """Enable cloud approvals, remove journal rules, and grant writer submit access."""
    old_mode_present = "MODO_ESCRITORIO" in app.config
    old_mode = app.config.get("MODO_ESCRITORIO", False)
    app.config["MODO_ESCRITORIO"] = False

    key = "approval_engine_enabled_cacao"
    config = database.session.execute(select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    old_config = config.value if config is not None else None
    created_config = config is None
    if config is None:
        database.session.add(CacaoConfig(key=key, value="1"))
    else:
        config.value = "1"

    rules = (
        database.session.execute(
            select(ApprovalMatrix).where(ApprovalMatrix.company_id == "cacao", ApprovalMatrix.document_type == "journal_entry")
        )
        .scalars()
        .all()
    )
    rule_states = [(rule, rule.enabled) for rule in rules]
    for rule, _enabled in rule_states:
        rule.enabled = False

    module = database.session.execute(select(Modules).filter_by(module="accounting")).scalar_one()
    role = Roles(name=f"journal submitter {uuid4().hex[:8]}", note="Journal submit test")
    database.session.add(role)
    database.session.flush()
    database.session.add(
        RolesAccess(
            rol_id=role.id,
            module_id=module.id,
            access=True,
            approve=True,
            view=True,
        )
    )
    database.session.add(RolesUser(user_id=writer.id, role_id=role.id, active=True))
    database.session.commit()
    return ApprovalConfigSnapshot(old_mode_present, bool(old_mode), old_config, created_config, rule_states, role.id)


def _remove_temporary_writer_role(role_id: str, writer_id: str) -> None:
    """Remove the temporary accounting role and its associations."""
    role_access = database.session.execute(select(RolesAccess).where(RolesAccess.rol_id == role_id)).scalars().all()
    for access in role_access:
        database.session.delete(access)
    database.session.execute(database.delete(ApprovalMatrix).where(ApprovalMatrix.role_id == role_id))
    database.session.execute(database.delete(ApprovalAction).where(ApprovalAction.role_id == role_id))
    assignment = database.session.execute(
        select(RolesUser).where(RolesUser.user_id == writer_id, RolesUser.role_id == role_id)
    ).scalar_one_or_none()
    if assignment is not None:
        database.session.delete(assignment)
    database.session.flush()
    role = database.session.get(Roles, role_id)
    if role is not None:
        database.session.delete(role)


def _restore_approval_engine_config(snapshot: ApprovalConfigSnapshot) -> None:
    """Restore the persisted approval-engine setting."""
    key = "approval_engine_enabled_cacao"
    config = database.session.execute(select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if config is None:
        return
    if snapshot.created_config:
        database.session.delete(config)
    elif snapshot.old_config is not None:
        config.value = snapshot.old_config


def _restore_missing_matrix(app, snapshot: ApprovalConfigSnapshot, writer: User) -> None:
    """Restore company approval configuration and the writer's temporary role."""
    _remove_temporary_writer_role(snapshot.role_id, writer.id)
    for rule, enabled in snapshot.rule_states:
        rule.enabled = enabled

    _restore_approval_engine_config(snapshot)
    if snapshot.old_mode_present:
        app.config["MODO_ESCRITORIO"] = snapshot.old_mode
    else:
        app.config.pop("MODO_ESCRITORIO", None)
    database.session.commit()


def _remove_test_journal(journal_id: str) -> None:
    """Remove the temporary draft after the HTTP regression has inspected it."""
    database.session.execute(
        database.delete(ComprobanteContableDetalle).where(
            ComprobanteContableDetalle.transaction == "journal_entry",
            ComprobanteContableDetalle.transaction_id == journal_id,
        )
    )
    database.session.execute(database.delete(ComprobanteContable).where(ComprobanteContable.id == journal_id))
    database.session.commit()


def _assert_submission_stays_draft(app, authenticated_client, username: str, journal_id: str) -> None:
    """Verify missing approval configuration leaves no request or GL evidence."""
    client = authenticated_client(username)
    response = client.post(f"/accounting/journal/{journal_id}/submit")

    assert response.status_code == 302
    with client.session_transaction() as session:
        messages = [message for _category, message in session.get("_flashes", [])]
    assert any("No existe una regla de aprobación" in message for message in messages)
    assert not any("aprobado" in message.lower() or "pendiente de aprobación" in message.lower() for message in messages)

    with app.app_context():
        database.session.expire_all()
        saved = database.session.get(ComprobanteContable, journal_id)
        assert saved is not None
        assert saved.status == "draft"
        assert (
            database.session.execute(select(ApprovalRequest).where(ApprovalRequest.document_id == journal_id)).scalars().all()
            == []
        )
        assert database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all() == []


@pytest.mark.parametrize("username", ["admin", "writer"])
def test_post_sin_regla_deja_diario_borrador_y_no_anuncia_aprobacion(
    app, entorno_contable, authenticated_client, reference_users, username: str
):
    """Neither a privileged nor a submitting user receives fake approval state."""
    del entorno_contable
    old_mode_present = "MODO_ESCRITORIO" in app.config
    old_mode = app.config.get("MODO_ESCRITORIO", False)
    snapshot: ApprovalConfigSnapshot | None = None
    journal_id: str | None = None
    try:
        with app.app_context():
            snapshot = _configure_missing_matrix(app, reference_users["writer"])
            with patch("cacao_accounting.contabilidad.journal_service.log_create"):
                journal = create_journal_draft(
                    _journal_payload(f"NO-MATRIX-{uuid4().hex[:8]}"),
                    user_id=str(reference_users["admin"].id),
                    assign_identifier=False,
                )
            created_journal_id = journal.id
            journal_id = created_journal_id

        _assert_submission_stays_draft(app, authenticated_client, username, created_journal_id)
    finally:
        with app.app_context():
            if journal_id is not None:
                _remove_test_journal(journal_id)
            if snapshot is None:
                database.session.rollback()
                if old_mode_present:
                    app.config["MODO_ESCRITORIO"] = old_mode
                else:
                    app.config.pop("MODO_ESCRITORIO", None)
            else:
                writer = database.session.get(User, str(reference_users["writer"].id))
                assert writer is not None
                _restore_missing_matrix(app, snapshot, writer)
