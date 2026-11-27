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
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation_bp import _claim_verification_attempt
from cacao_accounting.contabilidad.balance_confirmation import compute_snapshot_hash
from cacao_accounting.contabilidad import balance_confirmation_bp
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
            "SQLALCHEMY_DATABASE_URI": _database_uri_for_1839(tmp_path),
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 12, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    token = f"token-{suffix}"
    code = "123456"

    currency_code = f"C{suffix}"
    company_code = f"a{suffix}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code=currency_code)).scalar_one_or_none() is None:
            database.session.add(Currency(code=currency_code, name="Córdoba", decimals=2, active=True, default=False))
        module = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="accounting", default=True, enabled=True))
        else:
            module.enabled = True
        database.session.add(
            Entity(
                code=company_code,
                name="Alfa",
                company_name=f"Compañía Alfa {suffix}",
                tax_id=f"TAX-{suffix}",
                currency=currency_code,
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        party = Party(code=f"CLI-{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company=company_code,
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
        ids = {"invitation": invitation.id, "confirmation": confirmation.id, "token": token}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _post_verification(app, token: str, code: str, *, client=None, email: str = "cliente@example.test"):
    """Submit the public verification form."""
    client = client or app.test_client()
    return client.post(
        f"/confirm-balance/{token}/verify",
        data={
            "first_name": "Cliente",
            "last_name": "Prueba",
            "email": email,
            "code": code,
            "authorized": "on",
        },
    )


def test_expired_invitation_blocks_public_access_and_verification(confirmation_attempt_scenario):
    """Una invitación vencida no expone formularios ni permite verificar credenciales."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        database.session.commit()

    client = app.test_client()
    page = client.get(f"/confirm-balance/{ids['token']}")
    assert page.status_code == 200
    assert b'name="code"' not in page.data
    _post_verification(app, ids["token"], "123456", client=client)

    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.status == "pending"
        assert invitation.verified_at is None
        assert invitation.failed_attempts == 0
        assert not _claim_verification_attempt(invitation, invitation.token_hash)


def test_unexpired_invitation_can_be_verified(confirmation_attempt_scenario):
    """Una invitación con plazo propio futuro conserva el flujo de verificación."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        database.session.commit()
    _post_verification(app, ids["token"], "123456")
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.status == "viewed"
        assert invitation.verified_at is not None


def test_expired_invitation_cannot_submit_even_with_verified_session(confirmation_attempt_scenario):
    """La sesión verificada no permite responder tras el vencimiento de la invitación."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        snapshot = {"items": [], "totals": {}}
        confirmation.snapshot_json = json.dumps(snapshot)
        confirmation.snapshot_hash = compute_snapshot_hash(snapshot)
        confirmation_id = confirmation.id
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        database.session.commit()

    client = app.test_client()
    with client.session_transaction() as session:
        session[f"verified_confirmation_{confirmation_id}"] = ids["invitation"]
    page = client.get(f"/confirm-balance/{ids['token']}")
    response = client.post(f"/confirm-balance/{ids['token']}/respond", data={"response_type": "confirmed"})
    assert b'name="response_type"' not in page.data
    assert response.status_code == 302
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        assert confirmation.status == "sent"
        assert confirmation.responded_at is None


def test_response_transition_rechecks_deadline_atomically(confirmation_attempt_scenario, monkeypatch):
    """El UPDATE de respuesta rechaza una invitación que vence después de la lectura inicial."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        snapshot = {"items": [], "totals": {}}
        confirmation.snapshot_json = json.dumps(snapshot)
        confirmation.snapshot_hash = compute_snapshot_hash(snapshot)
        confirmation_id = confirmation.id
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        database.session.commit()

    monkeypatch.setattr(balance_confirmation_bp, "_invitation_unexpired", lambda _invitation: True)
    client = app.test_client()
    with client.session_transaction() as session:
        session[f"verified_confirmation_{confirmation_id}"] = ids["invitation"]
    response = client.post(f"/confirm-balance/{ids['token']}/respond", data={"response_type": "confirmed"})
    assert response.status_code == 302
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        assert confirmation.status == "sent"
        assert confirmation.responded_at is None


@pytest.mark.parametrize("expire_before_transition", [False, True])
def test_response_checks_confirmation_deadline_at_transition(
    confirmation_attempt_scenario, monkeypatch, expire_before_transition
):
    """La respuesta no se registra si el plazo vence después de validar el formulario."""
    app, ids = confirmation_attempt_scenario
    start = datetime.now(timezone.utc)
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        snapshot = {"items": [], "totals": {}}
        confirmation.snapshot_json = json.dumps(snapshot)
        confirmation.snapshot_hash = compute_snapshot_hash(snapshot)
        confirmation.expires_at = start + timedelta(seconds=5)
        invitation.expires_at = start + timedelta(minutes=5)
        confirmation_id = confirmation.id
        database.session.commit()

    monkeypatch.setattr(balance_confirmation_bp, "_utcnow", lambda: start)
    original_validate = balance_confirmation_bp._validated_public_response

    def validate_then_advance_clock():
        result = original_validate()
        if expire_before_transition:
            monkeypatch.setattr(balance_confirmation_bp, "_utcnow", lambda: start + timedelta(seconds=6))
        return result

    monkeypatch.setattr(balance_confirmation_bp, "_validated_public_response", validate_then_advance_clock)
    client = app.test_client()
    with client.session_transaction() as session:
        session[f"verified_confirmation_{confirmation_id}"] = ids["invitation"]
    user_agent = "Reviewer/" + "x" * 600
    response = client.post(
        f"/confirm-balance/{ids['token']}/respond",
        data={"response_type": "confirmed"},
        headers={"User-Agent": user_agent},
    )
    assert response.status_code == (302 if expire_before_transition else 200)
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        database.session.refresh(confirmation)
        assert confirmation.status == ("sent" if expire_before_transition else "confirmed")
        assert (confirmation.responded_at is None) == expire_before_transition
        assert invitation.status == ("pending" if expire_before_transition else "responded")
        if not expire_before_transition:
            assert confirmation.respondent_user_agent == user_agent[:512]


def test_verification_transition_rechecks_deadline(confirmation_attempt_scenario, monkeypatch):
    """Un vencimiento tras reclamar el intento impide crear una sesión verificada."""
    app, ids = confirmation_attempt_scenario
    original_claim = balance_confirmation_bp._claim_verification_attempt

    def expire_after_claim(invitation, token_hash):
        claimed = original_claim(invitation, token_hash)
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        database.session.commit()
        return claimed

    monkeypatch.setattr(balance_confirmation_bp, "_claim_verification_attempt", expire_after_claim)
    client = app.test_client()
    response = _post_verification(app, ids["token"], "123456", client=client)
    assert response.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation_id = invitation.balance_confirmation_id
        assert invitation.status == "pending"
        assert invitation.verified_at is None
    with client.session_transaction() as session:
        assert f"verified_confirmation_{confirmation_id}" not in session


def test_rotated_token_cannot_consume_new_invitation_attempts(confirmation_attempt_scenario, monkeypatch):
    """Un enlace antiguo no consume intentos del token emitido por un reenvío concurrente."""
    app, ids = confirmation_attempt_scenario
    original_claim = balance_confirmation_bp._claim_verification_attempt
    new_token_hash = hashlib.sha256(b"rotated-token").hexdigest()

    def rotate_before_claim(invitation, token_hash):
        invitation.token_hash = new_token_hash
        invitation.failed_attempts = 0
        database.session.commit()
        return original_claim(invitation, token_hash)

    monkeypatch.setattr(balance_confirmation_bp, "_claim_verification_attempt", rotate_before_claim)
    client = app.test_client()
    response = _post_verification(app, ids["token"], "000000", client=client)
    assert response.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.token_hash == new_token_hash
        assert invitation.failed_attempts == 0
        assert invitation.verified_at is None


@pytest.mark.parametrize("transition", ["cancelled", "expired", "confirmed"])
def test_verification_cannot_reopen_confirmation_changed_after_attempt_claim(
    confirmation_attempt_scenario, monkeypatch, transition
):
    """Una confirmación cerrada tras reclamar el intento no vuelve a viewed."""
    app, ids = confirmation_attempt_scenario
    original_claim = balance_confirmation_bp._claim_verification_attempt

    def change_confirmation_after_claim(invitation, token_hash):
        claimed = original_claim(invitation, token_hash)
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        if transition == "expired":
            confirmation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        elif transition == "confirmed":
            from cacao_accounting.internal_control_service import balance_confirmation_response_transition

            with balance_confirmation_response_transition(confirmation.id):
                database.session.execute(
                    database.update(BalanceConfirmation)
                    .where(BalanceConfirmation.id == confirmation.id)
                    .values(status="confirmed", response_type="confirmed", responded_at=datetime.now(timezone.utc))
                )
        else:
            confirmation.status = "cancelled"
        database.session.commit()
        return claimed

    monkeypatch.setattr(balance_confirmation_bp, "_claim_verification_attempt", change_confirmation_after_claim)
    client = app.test_client()
    response = _post_verification(app, ids["token"], "123456", client=client)
    assert response.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        assert confirmation.status == ("sent" if transition == "expired" else transition)
        assert confirmation.viewed_at is None
        assert invitation.status == "pending"
        assert invitation.verified_at is None
        confirmation_id = confirmation.id
    with client.session_transaction() as session:
        assert f"verified_confirmation_{confirmation_id}" not in session


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


@pytest.mark.database
def test_concurrent_attempts_claim_at_most_five_slots(confirmation_attempt_scenario):
    """Diez reclamos paralelos solo obtienen cinco incrementos tras leer el mismo estado."""
    app, ids = confirmation_attempt_scenario
    barrier = Barrier(10, timeout=30)

    def claim() -> bool:
        with app.app_context():
            try:
                invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
                # Fuerza una lectura obsoleta antes de competir: un contador
                # read-modify-write vulnerable no puede usar el valor actual.
                invitation.failed_attempts
                barrier.wait()
                return _claim_verification_attempt(invitation, invitation.token_hash)
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


def test_correo_unicode_no_rompe_la_comparacion(confirmation_attempt_scenario):
    """La comparación en tiempo constante admite direcciones no ASCII."""
    app, ids = confirmation_attempt_scenario
    email = "cliente@exämple.test"
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        invitation.email = email
        database.session.commit()

    respuesta = _post_verification(app, ids["token"], "123456", email=email)

    assert respuesta.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitation.status == "viewed"


def test_nombres_largos_se_acotan_al_verificar(confirmation_attempt_scenario):
    """Nombre y apellido se recortan al límite de sus columnas."""
    app, ids = confirmation_attempt_scenario
    client = app.test_client()
    respuesta = client.post(
        f"/confirm-balance/{ids['token']}/verify",
        data={
            "first_name": "N" * 200,
            "last_name": "A" * 200,
            "email": "cliente@example.test",
            "code": "123456",
            "authorized": "on",
        },
    )

    assert respuesta.status_code == 302
    with client.session_transaction() as sesion:
        nombres = next(valor for clave, valor in sesion.items() if clave.startswith("verified_confirmation_name_"))
    assert len(nombres[0]) <= 100
    assert len(nombres[1]) <= 100


def test_pagina_publica_no_se_cachea(confirmation_attempt_scenario):
    """La página con token financiero responde `Cache-Control: no-store`."""
    app, ids = confirmation_attempt_scenario
    respuesta = app.test_client().get(f"/confirm-balance/{ids['token']}")

    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_confirmacion_sin_responded_at_no_rompe_la_vista(confirmation_attempt_scenario):
    """Un estado terminal sin fecha de respuesta se muestra sin 500."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, ids["confirmation"])
        confirmation.status = "confirmed"
        confirmation.responded_at = None
        confirmation.respondent_first_name = "Cliente"
        confirmation.respondent_last_name = "Prueba"
        confirmation.respondent_email = "cliente@example.test"
        database.session.commit()

    respuesta = app.test_client().get(f"/confirm-balance/{ids['token']}")

    assert respuesta.status_code == 200
    assert "fecha no registrada" in respuesta.get_data(as_text=True)


def test_no_se_responde_un_borrador(confirmation_attempt_scenario):
    """Una confirmación nunca enviada no acepta respuestas públicas."""
    app, ids = confirmation_attempt_scenario
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, ids["confirmation"])
        confirmation.status = "draft"
        database.session.commit()

    respuesta = app.test_client().post(
        f"/confirm-balance/{ids['token']}/respond",
        data={"response_type": "confirmed", "response_comment": ""},
    )

    assert respuesta.status_code == 302
    with app.app_context():
        confirmation = database.session.get(BalanceConfirmation, ids["confirmation"])
        assert confirmation.status == "draft"


@pytest.mark.parametrize("status", ["cancelled", "responded", "expired"])
def test_invitacion_terminal_no_muta_al_verificar(confirmation_attempt_scenario, status):
    """#1839: una invitación terminal se rechaza sin cambiar su estado."""
    from cacao_accounting.database import BalanceConfirmationInvitation, database

    app, ids = confirmation_attempt_scenario
    with app.app_context():
        invitacion = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        invitacion.status = status
        before = (invitacion.verified_at, invitacion.last_access_at, invitacion.failed_attempts)
        database.session.commit()

    respuesta = _post_verification(app, ids["token"], "123456")

    assert respuesta.status_code in {302, 400, 404, 410}
    with app.app_context():
        invitacion = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        assert invitacion.status == status
        assert (invitacion.verified_at, invitacion.last_access_at, invitacion.failed_attempts) == before


def _database_uri_for_1839(tmp_path) -> str:
    """Usa el motor real en CI (-m database) y SQLite local como respaldo."""
    if os.environ.get("CHECK_DATABASE", "").strip().lower() in {"1", "true", "yes"}:
        return str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    return f"sqlite:///{tmp_path / 'confirmation-1839.sqlite'}"


@pytest.fixture
def confirmation_1839_scenario(tmp_path):
    """Escenario aislado para carreras de #1839 sobre SQLite local o motor real CI."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": _database_uri_for_1839(tmp_path),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    token = f"token-1839-{suffix}"
    code = "123456"

    with app.app_context():
        database.create_all()
        currency = database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none()
        if currency is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        module = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="accounting", default=True, enabled=True))
        company_code = f"a1839{suffix[:4]}"
        database.session.add(
            Entity(
                code=company_code,
                name=f"Alfa {suffix}",
                company_name=f"Compañía Alfa {suffix}",
                tax_id=f"TAX-1839-{suffix}",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        party = Party(code=f"CLI-1839-{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company=company_code,
            document_no=f"BC-1839-{suffix}",
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
        ids = {
            "invitation": invitation.id,
            "confirmation": confirmation.id,
            "party": party.id,
            "entity": company_code,
            "token": token,
        }

    try:
        yield app, ids
    finally:
        with app.app_context():
            uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
            is_memory = uri == "sqlite://" or ":memory:" in uri
            try:
                if not is_memory:
                    database.session.execute(
                        database.delete(BalanceConfirmationInvitation).where(
                            BalanceConfirmationInvitation.id == ids["invitation"]
                        )
                    )
                    database.session.execute(
                        database.delete(BalanceConfirmation).where(BalanceConfirmation.id == ids["confirmation"])
                    )
                    database.session.commit()
                    database.session.execute(database.delete(Party).where(Party.id == ids["party"]))
                    database.session.commit()

                    # La compañía se conserva: AuditTrail la referencia con
                    # FK RESTRICT y la evidencia de auditoría es append-only.
                    # El código es único por prueba, así que no colisiona.
                    remaining = {
                        "invitation": database.session.get(BalanceConfirmationInvitation, ids["invitation"]),
                        "confirmation": database.session.get(BalanceConfirmation, ids["confirmation"]),
                        "party": database.session.get(Party, ids["party"]),
                    }
                    leftovers = [name for name, row in remaining.items() if row is not None]
                    if leftovers:
                        raise AssertionError(f"Limpieza incompleta de fixture 1839: {', '.join(leftovers)}")
            except Exception:
                database.session.rollback()
                raise
            finally:
                database.session.remove()
                database.engine.dispose()


def _aplicar_estado_terminal(app, invitation_id: str, terminal_status: str) -> None:
    """Aplica cancelación o respuesta terminal desde otra transacción."""
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, invitation_id)
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        if terminal_status == "cancelled":
            confirmation.status = "cancelled"
            invitation.status = "cancelled"
        elif terminal_status == "responded":
            confirmation.status = "confirmed"
            confirmation.response_type = "confirmed"
            confirmation.responded_at = datetime.now(timezone.utc)
            invitation.status = "responded"
        else:
            raise AssertionError(f"Estado terminal no soportado: {terminal_status}")
        database.session.commit()


@pytest.mark.database
@pytest.mark.parametrize("terminal_status", ["cancelled", "responded"])
@pytest.mark.parametrize("order", ["terminal_first", "terminal_after_claim"])
def test_verificacion_concurrente_con_estado_terminal_no_otorga_acceso(
    confirmation_1839_scenario, monkeypatch, terminal_status, order
):
    """#1839: verificación pública no reabre invitación terminal en ambos órdenes."""
    app, ids = confirmation_1839_scenario
    client = app.test_client()
    if order == "terminal_first":
        _aplicar_estado_terminal(app, ids["invitation"], terminal_status)
        response = _post_verification(app, ids["token"], "123456", client=client)
    else:
        original_claim = balance_confirmation_bp._claim_verification_attempt
        barrier = Barrier(2, timeout=30)
        errors: list[BaseException] = []

        def claim_then_race(invitation, token_hash):
            claimed = original_claim(invitation, token_hash)
            if claimed:
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:

                        def apply_and_sync():
                            barrier.wait()
                            _aplicar_estado_terminal(app, ids["invitation"], terminal_status)

                        future = executor.submit(apply_and_sync)
                        barrier.wait()
                        future.result(timeout=30)
                except BaseException as exc:  # pragma: no cover - diagnóstico de carrera
                    errors.append(exc)
                    raise
            return claimed

        monkeypatch.setattr(balance_confirmation_bp, "_claim_verification_attempt", claim_then_race)
        response = _post_verification(app, ids["token"], "123456", client=client)
        assert not errors

    assert response.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        assert invitation.status == terminal_status
        assert invitation.verified_at is None
        if terminal_status == "cancelled":
            assert confirmation.status == "cancelled"
        else:
            assert confirmation.status == "confirmed"
            assert confirmation.response_type == "confirmed"
        confirmation_id = confirmation.id

    with client.session_transaction() as session:
        assert f"verified_confirmation_{confirmation_id}" not in session


@pytest.mark.database
def test_verificacion_exitosa_marca_sesion_del_mismo_cliente(confirmation_1839_scenario):
    """Control: el mismo cliente que verifica conserva la marca de sesi?n."""
    app, ids = confirmation_1839_scenario
    client = app.test_client()
    response = _post_verification(app, ids["token"], "123456", client=client)

    assert response.status_code == 302
    with app.app_context():
        invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
        confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
        assert invitation.status == "viewed"
        confirmation_id = confirmation.id

    with client.session_transaction() as session:
        assert session.get(f"verified_confirmation_{confirmation_id}") == ids["invitation"]
