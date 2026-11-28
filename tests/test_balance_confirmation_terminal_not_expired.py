# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1702: abrir el enlace vencido no borra una respuesta terminal."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    Party,
    database,
)
from cacao_accounting.internal_control_service import balance_confirmation_response_transition


@pytest.fixture
def public_confirmation_scene():
    """Confirmación enviada con token conocido y vencimiento futuro."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    sufijo = uuid4().hex[:6]
    token = f"token-1702-{sufijo}"
    codigo = "123456"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {sufijo}",
                    tax_id=f"TAX-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        party = Party(code=f"CLI-{sufijo}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company="alpha",
            document_no=f"BC-{sufijo}",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 5, 31),
            status="sent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        database.session.add(confirmation)
        database.session.flush()
        database.session.add(
            BalanceConfirmationInvitation(
                balance_confirmation_id=confirmation.id,
                email="cliente@example.test",
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                verification_code_hash=hashlib.sha256(codigo.encode("utf-8")).hexdigest(),
                status="pending",
                failed_attempts=0,
                expires_at=confirmation.expires_at,
            )
        )
        database.session.commit()
        confirmation_id = confirmation.id
    yield app, {"confirmation": confirmation_id, "token": token, "code": codigo}
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _responder(app, ids: dict[str, str], response_type: str) -> None:
    """Registra la respuesta con la transición autorizada del servicio."""
    with app.app_context():
        with balance_confirmation_response_transition(ids["confirmation"]):
            database.session.execute(
                database.update(BalanceConfirmation)
                .where(BalanceConfirmation.id == ids["confirmation"])
                .values(
                    status=response_type,
                    responded_at=datetime.now(timezone.utc),
                    response_type=response_type,
                    response_comment="Respuesta del cliente.",
                    respondent_first_name="Ana",
                    respondent_last_name="Cliente",
                    respondent_email="cliente@example.test",
                )
            )
            database.session.commit()


def _vencer(app, confirmation_id: str) -> None:
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        confirmation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        database.session.commit()


@pytest.mark.parametrize("response_type", ["confirmed", "disputed"])
def test_enlace_vencido_conserva_la_respuesta_terminal(public_confirmation_scene, response_type):
    """confirmed/disputed no se convierten en expired al abrir el enlace público."""
    app, ids = public_confirmation_scene
    _responder(app, ids, response_type)
    _vencer(app, ids["confirmation"])

    response = app.test_client().get(f"/confirm-balance/{ids['token']}")

    assert response.status_code == 200
    assert "ya fue respondida" in response.get_data(as_text=True)
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, ids["confirmation"])
        assert confirmation.status == response_type
        assert confirmation.response_type == response_type
        assert confirmation.responded_at is not None


def test_enlace_vencido_sin_respuesta_marca_expirada(public_confirmation_scene):
    """Una solicitud activa vencida sí transiciona a expired."""
    app, ids = public_confirmation_scene
    _vencer(app, ids["confirmation"])

    response = app.test_client().get(f"/confirm-balance/{ids['token']}")

    cuerpo = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "ha expirado y ya no se permiten respuestas" in cuerpo
    with app.app_context():
        assert database.session.get(BalanceConfirmation, ids["confirmation"]).status == "expired"


def test_la_vista_terminal_se_traduce_al_ingles(public_confirmation_scene):
    """QA2 H4: el cierre de una respuesta terminal usa el catálogo inglés."""
    app, ids = public_confirmation_scene
    _responder(app, ids, "confirmed")
    _vencer(app, ids["confirmation"])
    with app.app_context():
        database.session.add(CacaoConfig(key="SETUP_LANGUAGE", value="en"))
        database.session.commit()

    response = app.test_client().get(f"/confirm-balance/{ids['token']}")

    cuerpo = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "This request was already answered on" in cuerpo
    assert "and is closed." in cuerpo
