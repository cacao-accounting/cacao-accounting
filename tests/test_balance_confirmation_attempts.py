# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2186: los intentos de verificación externa se reclaman de forma atómica.

La lectura y el incremento en memoria de `failed_attempts` permitían que
solicitudes concurrentes observaran el mismo valor y probaran más de cinco
códigos. El reclamo condicional incrementa solo mientras no se alcanza el
límite y decide el turno en una sola operación.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation_bp import _claim_verification_attempt
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Currency,
    Entity,
    Modules,
    Party,
    database,
)


@pytest.fixture
def confirmation_attempt_scenario(tmp_path):
    """Create a sent confirmation with a known invitation token."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'confirmation-attempts.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 8, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    token = f"token-{suffix}"
    code = "123456"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        party = Party(code=f"CLI-{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company="alpha",
            document_no=f"BC-{suffix}",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 5, 31),
            status="sent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        database.session.add(confirmation)
        database.session.flush()
        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email="cliente@example.test",
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            verification_code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            status="pending",
            failed_attempts=0,
        )
        database.session.add(invitation)
        database.session.commit()
        ids = {"invitation": invitation.id, "token": token}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _post_verification(app, token: str, code: str):
    """Submit the public verification form."""
    client = app.test_client()
    return client.post(
        f"/confirm-balance/{token}/verify",
        data={
            "first_name": "Cliente",
            "last_name": "Prueba",
            "email": "cliente@example.test",
            "code": code,
            "authorized": "on",
        },
    )


def test_sixth_wrong_verification_is_rejected_after_five_attempts(confirmation_attempt_scenario):
    """El contador se detiene en cinco y el siguiente intento no compara el código."""
    app, ids = confirmation_attempt_scenario

    for _ in range(5):
        _post_verification(app, ids["token"], "000000")

    sixth = _post_verification(app, ids["token"], "000000")

    assert sixth.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.failed_attempts == 5


def test_concurrent_attempts_claim_at_most_five_slots(confirmation_attempt_scenario):
    """Diez reclamos paralelos solo obtienen cinco incrementos."""
    app, ids = confirmation_attempt_scenario

    def claim() -> bool:
        with app.app_context():
            try:
                invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
                return _claim_verification_attempt(invitation)
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: claim(), range(10)))

    assert sum(results) == 5
    with app.app_context():
        counter = database.session.execute(
            database.select(func.max(BalanceConfirmationInvitation.failed_attempts)).where(
                BalanceConfirmationInvitation.id == ids["invitation"]
            )
        ).scalar_one()
        assert counter == 5


def test_successful_verification_resets_the_claim_counter(confirmation_attempt_scenario):
    """Un código correcto sigue verificando la invitación y limpia el contador."""
    app, ids = confirmation_attempt_scenario

    _post_verification(app, ids["token"], "000000")
    _post_verification(app, ids["token"], "123456")

    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.status == "viewed"
        assert invitation.failed_attempts == 0
