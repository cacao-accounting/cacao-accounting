# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La verificación pública respeta el estado de la invitación.

Escenario de negocio (issue #1839): el POST de verificación solo controlaba
la expiración de la confirmación; una invitación cancelada, respondida o
expirada podía pasar a ``viewed`` y quedar como leída ante el administrador.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Entity,
    Party,
    database,
)

CODIGO = "123456"


def _crear_app(invitation_status: str):
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
    token = f"token-{invitation_status}"
    with application.app_context():
        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        party = Party(code="CLI-1", name="Cliente", is_customer=True, is_supplier=False)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company="cacao",
            document_no="BC-1",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 10, 31),
            status="sent",
        )
        database.session.add(confirmation)
        database.session.flush()
        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email="cliente@example.com",
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            verification_code_hash=hashlib.sha256(CODIGO.encode("utf-8")).hexdigest(),
            status=invitation_status,
        )
        database.session.add(invitation)
        database.session.commit()
        confirmation_id = confirmation.id
        invitation_id = invitation.id
    return application, token, confirmation_id, invitation_id


def _formulario() -> dict[str, str]:
    return {
        "first_name": "Ana",
        "last_name": "Pérez",
        "email": "cliente@example.com",
        "code": CODIGO,
        "authorized": "on",
    }


@pytest.mark.parametrize("estado", ["cancelled", "responded", "expired"])
def test_no_muta_invitaciones_cerradas(estado):
    """La invitación cerrada conserva su estado y no queda como verificada."""
    application, token, _confirmation_id, invitation_id = _crear_app(estado)
    try:
        client = application.test_client()
        respuesta = client.post(f"/confirm-balance/{token}/verify", data=_formulario())

        assert respuesta.status_code == 302
        with application.app_context():
            invitacion = database.session.get(BalanceConfirmationInvitation, invitation_id)
            assert invitacion is not None
            assert invitacion.status == estado
            assert invitacion.verified_at is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_verifica_una_invitacion_pendiente():
    """El camino válido sigue marcando la invitación como vista."""
    application, token, confirmation_id, invitation_id = _crear_app("pending")
    try:
        client = application.test_client()
        respuesta = client.post(f"/confirm-balance/{token}/verify", data=_formulario())

        assert respuesta.status_code == 302
        with application.app_context():
            invitacion = database.session.get(BalanceConfirmationInvitation, invitation_id)
            confirmacion = database.session.get(BalanceConfirmation, confirmation_id)
            assert invitacion is not None and invitacion.status == "viewed"
            assert invitacion.verified_at is not None
            assert confirmacion is not None and confirmacion.status == "viewed"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
