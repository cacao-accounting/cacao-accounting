# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""A failed recipient keeps the last invitation credentials they received."""

from __future__ import annotations

import hashlib
from importlib import import_module
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Currency,
    Entity,
    Modules,
    Party,
    User,
    database,
)
from cacao_accounting.messaging.email import EmailError

CONTRASENA = "Confirmacion-Admin-2026!"
CODIGO_PREVIO = "123456"


def _crear_app(confirmation_status: str, resend: bool):
    """Build a cloud confirmation with a viable previous credential per invite."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    previous_sent_at = datetime(2026, 11, 1, tzinfo=timezone.utc) if resend else None
    previous_status = "viewed" if resend else "pending"
    with application.app_context():
        database.create_all()
        party = Party(code="CLI-1", name="Cliente", is_customer=True)
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                party,
            ]
        )
        database.session.flush()
        confirmation = BalanceConfirmation(
            company="cacao",
            document_no="CONF-1",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 10, 31),
            status=confirmation_status,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            snapshot_json='{"company_name":"Cacao SA","party_name":"Cliente","items":[],"totals":{}}',
        )
        database.session.add(confirmation)
        database.session.flush()

        old_tokens = {}
        invitation_ids = {}
        for recipient in ("ok@example.test", "failed@example.test"):
            old_token = f"previous-token-{recipient.split('@')[0]}"
            old_tokens[recipient] = old_token
            invitation = BalanceConfirmationInvitation(
                balance_confirmation_id=confirmation.id,
                email=recipient,
                token_hash=hashlib.sha256(old_token.encode("utf-8")).hexdigest(),
                verification_code_hash=hashlib.sha256(CODIGO_PREVIO.encode("ascii")).hexdigest(),
                status=previous_status,
                sent_at=previous_sent_at,
                failed_attempts=3 if resend else 0,
                expires_at=confirmation.expires_at,
            )
            database.session.add(invitation)
            database.session.flush()
            invitation_ids[recipient] = invitation.id
        database.session.commit()
        confirmation_id = confirmation.id

    return application, confirmation_id, invitation_ids, old_tokens, previous_status, previous_sent_at


@pytest.mark.parametrize(
    ("confirmation_status", "resend"),
    [("draft", False), ("sent", True)],
)
def test_falla_individual_conserva_credenciales_previas(confirmation_status, resend, monkeypatch):
    """Mixed delivery rotates credentials only for recipients whose mail was accepted."""
    application, confirmation_id, invitation_ids, old_tokens, previous_status, previous_sent_at = _crear_app(
        confirmation_status, resend
    )
    sent_bodies = {}
    try:

        def deliver(*, to_email, **kwargs):
            if to_email == "failed@example.test":
                raise EmailError("SMTP unavailable")
            sent_bodies[to_email] = kwargs["body"]

        route_module = import_module("cacao_accounting.contabilidad.balance_confirmation_bp")
        monkeypatch.setattr(route_module, "send_email", deliver)
        client = application.test_client()
        login = client.post(
            "/login",
            data={"usuario": "admin", "acceso": CONTRASENA},
            follow_redirects=True,
        )
        assert login.status_code == 200

        action = "resend" if resend else "send"
        response = client.post(f"/accounting/balance-confirmations/{confirmation_id}/{action}")
        assert response.status_code == 302
        assert set(sent_bodies) == {"ok@example.test"}

        with application.app_context():
            invitations = {
                item.email: item
                for item in database.session.execute(
                    database.select(BalanceConfirmationInvitation).where(
                        BalanceConfirmationInvitation.id.in_(list(invitation_ids.values()))
                    )
                ).scalars()
            }
            successful = invitations["ok@example.test"]
            failed = invitations["failed@example.test"]
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)

            assert confirmation is not None and confirmation.status == "sent"
            assert successful.token_hash != hashlib.sha256(old_tokens["ok@example.test"].encode()).hexdigest()
            assert successful.verification_code_hash != hashlib.sha256(CODIGO_PREVIO.encode("ascii")).hexdigest()
            assert successful.status == "pending"
            assert successful.sent_at is not None
            assert successful.failed_attempts == 0

            assert failed.token_hash == hashlib.sha256(old_tokens["failed@example.test"].encode()).hexdigest()
            assert failed.verification_code_hash == hashlib.sha256(CODIGO_PREVIO.encode("ascii")).hexdigest()
            assert failed.status == previous_status
            expected_sent_at = previous_sent_at.replace(tzinfo=None) if previous_sent_at else None
            assert failed.sent_at == expected_sent_at
            assert failed.failed_attempts == (3 if resend else 0)

        body = sent_bodies["ok@example.test"]
        link_match = re.search(r"https?://\S+/confirm-balance/([^\s]+)", body)
        code_match = re.search(r"(?:Nuevo )?código de verificación:\s*(\d{6})", body, re.IGNORECASE)
        assert link_match is not None and code_match is not None
        new_token = urlparse(link_match.group(0)).path.rsplit("/", maxsplit=1)[-1]
        with application.app_context():
            successful = database.session.get(BalanceConfirmationInvitation, invitation_ids["ok@example.test"])
            assert successful is not None
            assert hashlib.sha256(new_token.encode("utf-8")).hexdigest() == successful.token_hash
            assert hashlib.sha256(code_match.group(1).encode("ascii")).hexdigest() == successful.verification_code_hash

        assert client.get(f"/confirm-balance/{old_tokens['failed@example.test']}").status_code == 200
        assert client.get(f"/confirm-balance/{new_token}").status_code == 200
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
