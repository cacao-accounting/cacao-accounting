# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Posted external balance confirmation evidence cannot be rewritten."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation import compute_snapshot_hash
from cacao_accounting.internal_control_service import balance_confirmation_response_transition
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Currency,
    Entity,
    Modules,
    Party,
    database,
)


@pytest.fixture(params=[True, False], ids=["desktop", "cloud"])
def sent_confirmation(request):
    """Create a sent confirmation with a valid snapshot and active invitation."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": request.param,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    suffix = uuid4().hex[:8]
    raw_token = f"balance-token-{suffix}"
    verification_code = f"{uuid4().int % 1_000_000:06d}"
    snapshot = {
        "company_id": "alpha",
        "company_name": "Compañía Alfa",
        "party_id": f"PARTY-{suffix}",
        "party_name": "Cliente Alfa",
        "party_type": "customer",
        "cutoff_date": "2026-11-20",
        "items": [],
        "totals": {"NIO": "0"},
        "emails": ["client@example.test"],
    }
    snapshot_json = json.dumps(snapshot, ensure_ascii=False)

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name="Compañía Alfa",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        party = Party(code=f"C-{suffix}", name="Cliente Alfa", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        snapshot["party_id"] = party.id
        snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        confirmation = BalanceConfirmation(
            company="alpha",
            document_no=f"CONF-{suffix}",
            document_type="balance_confirmation",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 11, 20),
            status="sent",
            sent_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            snapshot_json=snapshot_json,
            snapshot_hash=compute_snapshot_hash(snapshot),
        )
        database.session.add(confirmation)
        database.session.flush()
        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email="client@example.test",
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            verification_code_hash=hashlib.sha256(verification_code.encode("utf-8")).hexdigest(),
            status="pending",
            sent_at=datetime.now(timezone.utc),
            expires_at=confirmation.expires_at,
        )
        database.session.add(invitation)
        database.session.commit()
        ids = {"confirmation": confirmation.id, "snapshot": snapshot_json}

    yield app, ids, raw_token, verification_code

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _record_valid_external_response(app, confirmation_id: str, token: str, code: str) -> None:
    """Complete identity verification and the first valid customer response."""
    if app.config["MODO_ESCRITORIO"]:
        with app.app_context():
            with balance_confirmation_response_transition(confirmation_id):
                database.session.execute(
                    database.update(BalanceConfirmation)
                    .where(BalanceConfirmation.id == confirmation_id)
                    .values(
                        status="confirmed",
                        responded_at=datetime.now(timezone.utc),
                        response_type="confirmed",
                        response_comment="Saldo confirmado.",
                        respondent_first_name="Ana",
                        respondent_last_name="Cliente",
                        respondent_email="client@example.test",
                    )
                )
                database.session.commit()
        return

    client = app.test_client()
    assert client.get(f"/confirm-balance/{token}").status_code == 200
    assert (
        client.post(
            f"/confirm-balance/{token}/verify",
            data={
                "first_name": "Ana",
                "last_name": "Cliente",
                "email": "client@example.test",
                "code": code,
                "authorized": "on",
            },
        ).status_code
        == 302
    )
    assert (
        client.post(
            f"/confirm-balance/{token}/respond",
            data={"response_type": "confirmed", "response_comment": "Saldo confirmado."},
        ).status_code
        == 200
    )


@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_responded_confirmation_rejects_snapshot_rewrite_and_delete(sent_confirmation, channel):
    """The immutable snapshot and first external response survive every write path."""
    app, ids, token, code = sent_confirmation
    _record_valid_external_response(app, ids["confirmation"], token, code)

    with app.app_context():
        confirmation_id = ids["confirmation"]
        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(BalanceConfirmation, confirmation_id)
                assert row is not None
                row.snapshot_json = "{}"
                database.session.commit()
            elif channel == "core":
                database.session.execute(
                    database.update(BalanceConfirmation)
                    .where(BalanceConfirmation.id == confirmation_id)
                    .values(snapshot_json="{}")
                )
                database.session.commit()
            else:
                database.session.execute(
                    text("UPDATE balance_confirmation SET snapshot_json = '{}' WHERE id = :id"), {"id": confirmation_id}
                )
                database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(BalanceConfirmation, confirmation_id)
                assert row is not None
                database.session.delete(row)
                database.session.commit()
            elif channel == "core":
                database.session.execute(database.delete(BalanceConfirmation).where(BalanceConfirmation.id == confirmation_id))
                database.session.commit()
            else:
                database.session.execute(text("DELETE FROM balance_confirmation WHERE id = :id"), {"id": confirmation_id})
                database.session.commit()
        database.session.rollback()

        row = database.session.get(BalanceConfirmation, confirmation_id)
        assert row is not None
        assert row.snapshot_json == ids["snapshot"]
        assert row.status == "confirmed"
        assert row.response_type == "confirmed"
        assert row.response_comment == "Saldo confirmado."


@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_responded_confirmation_rejects_response_rewrite(sent_confirmation, channel):
    """A recorded third-party response cannot be edited through another path."""
    app, ids, token, code = sent_confirmation
    _record_valid_external_response(app, ids["confirmation"], token, code)

    with app.app_context():
        confirmation_id = ids["confirmation"]
        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(BalanceConfirmation, confirmation_id)
                assert row is not None
                row.response_comment = "Cambiada tras responder."
                database.session.commit()
            elif channel == "core":
                database.session.execute(
                    database.update(BalanceConfirmation)
                    .where(BalanceConfirmation.id == confirmation_id)
                    .values(response_comment="Cambiada tras responder.")
                )
                database.session.commit()
            else:
                database.session.execute(
                    text("UPDATE balance_confirmation SET response_comment = :comment WHERE id = :id"),
                    {"id": confirmation_id, "comment": "Cambiada tras responder."},
                )
                database.session.commit()
        database.session.rollback()

        row = database.session.get(BalanceConfirmation, confirmation_id)
        assert row is not None
        assert row.response_comment == "Saldo confirmado."


def test_terminal_status_requires_the_atomic_external_response(sent_confirmation):
    """A status cannot claim a response without appending its response evidence."""
    app, ids, _token, _code = sent_confirmation

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.execute(
                database.update(BalanceConfirmation)
                .where(BalanceConfirmation.id == ids["confirmation"])
                .values(status="confirmed")
            )
            database.session.commit()
        database.session.rollback()

        row = database.session.get(BalanceConfirmation, ids["confirmation"])
        assert row is not None
        assert row.status == "sent"
        assert row.response_type is None
        assert row.responded_at is None


def test_first_response_requires_the_authorized_transition_scope(sent_confirmation):
    """A caller cannot forge even the first response with an unscoped Core update."""
    app, ids, _token, _code = sent_confirmation

    with app.app_context():
        with pytest.raises(ValueError):
            database.session.execute(
                database.update(BalanceConfirmation)
                .where(BalanceConfirmation.id == ids["confirmation"])
                .values(
                    status="confirmed",
                    responded_at=datetime.now(timezone.utc),
                    response_type="confirmed",
                    response_comment="Saldo confirmado.",
                )
            )
            database.session.commit()
        database.session.rollback()

        row = database.session.get(BalanceConfirmation, ids["confirmation"])
        assert row is not None
        assert row.status == "sent"
        assert row.response_type is None
        assert row.responded_at is None
