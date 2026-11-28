# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2186: evidencia en PostgreSQL de que los cupos OTP se reclaman sin carrera."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

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

pytestmark = pytest.mark.database

INTENTOS = 10
LIMITE = 5


def _sembrar_confirmacion(sufijo: str, token: str, code: str) -> dict[str, str]:
    """Siembra la confirmación y la invitación que compiten por los cupos."""
    database.create_all()
    company_code = f"a{sufijo}"
    if database.session.execute(database.select(Currency.id).filter_by(code="NIO")).scalar_one_or_none() is None:
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    if database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one_or_none() is None:
        database.session.add(Modules(module="accounting", default=True, enabled=True))
    database.session.add(
        Entity(
            code=company_code,
            name="Alfa",
            company_name=f"Compañía Alfa {sufijo}",
            tax_id=f"TAX-{sufijo}",
            currency="NIO",
            enabled=True,
            status="default",
        )
    )
    database.session.flush()
    party = Party(code=f"CLI-{sufijo}", name="Cliente", is_customer=True, is_active=True)
    database.session.add(party)
    database.session.flush()
    confirmation = BalanceConfirmation(
        company=company_code,
        document_no=f"BC-{sufijo}",
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
    return {"invitation": str(invitation.id), "token": token}


def test_reclamo_otp_postgresql_con_intercalado_determinista() -> None:
    """En PostgreSQL solo cinco de diez reclamos simultáneos obtienen un cupo."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("postgresql"):
        pytest.skip("Este caso valida el bloqueo transaccional de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    schema_name = f"otp_attempts_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri)
    with bootstrap_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    engine_options: Any = {
        "pool_size": INTENTOS + 2,
        "max_overflow": 0,
        "connect_args": {"options": f"-csearch_path={schema_name}"},
    }
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": cast(Any, engine_options),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "isolated-otp-attempts-test",
        }
    )
    sufijo = uuid4().hex[:6]
    token = f"token-{sufijo}"
    try:
        with application.app_context():
            ids = _sembrar_confirmacion(sufijo, token, "123456")

        barrera = Barrier(INTENTOS, timeout=30)

        def claim() -> bool:
            with application.app_context():
                try:
                    invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
                    invitation.failed_attempts
                    barrera.wait()
                    return _claim_verification_attempt(invitation, invitation.token_hash)
                finally:
                    database.session.remove()

        with ThreadPoolExecutor(max_workers=INTENTOS) as executor:
            resultados = list(executor.map(lambda _: claim(), range(INTENTOS)))

        assert sum(resultados) == LIMITE
        with application.app_context():
            contador = database.session.execute(
                database.select(BalanceConfirmationInvitation.failed_attempts).where(
                    BalanceConfirmationInvitation.id == ids["invitation"]
                )
            ).scalar_one()
            assert contador == LIMITE

        # Agotados los cupos, ni siquiera el código correcto puede verificar.
        respuesta = application.test_client().post(
            f"/confirm-balance/{token}/verify",
            data={
                "first_name": "Cliente",
                "last_name": "Prueba",
                "email": "cliente@example.test",
                "code": "123456",
                "authorized": "on",
            },
            follow_redirects=True,
        )
        assert respuesta.status_code == 200
        assert "Se ha excedido el número de intentos permitidos" in respuesta.get_data(as_text=True)
        with application.app_context():
            invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
            assert invitation.status == "pending"
            assert invitation.failed_attempts == LIMITE
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        bootstrap_engine.dispose()


def test_reclamo_otp_mysql_con_intercalado_determinista() -> None:
    """En MySQL solo cinco de diez lecturas obsoletas obtienen un cupo."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith(("mysql", "mariadb")):
        pytest.skip("Este caso valida el bloqueo transaccional de MySQL/MariaDB.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "isolated-otp-attempts-mysql-test",
        }
    )
    sufijo = uuid4().hex[:6]
    token = f"token-mysql-{sufijo}"
    barrera = Barrier(INTENTOS, timeout=30)
    try:
        with application.app_context():
            ids = _sembrar_confirmacion(sufijo, token, "123456")

        def claim() -> bool:
            with application.app_context():
                try:
                    invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
                    invitation.failed_attempts
                    barrera.wait()
                    return _claim_verification_attempt(invitation, invitation.token_hash)
                finally:
                    database.session.remove()

        with ThreadPoolExecutor(max_workers=INTENTOS) as executor:
            resultados = list(executor.map(lambda _: claim(), range(INTENTOS)))

        assert sum(resultados) == LIMITE
        with application.app_context():
            contador = database.session.execute(
                database.select(BalanceConfirmationInvitation.failed_attempts).where(
                    BalanceConfirmationInvitation.id == ids["invitation"]
                )
            ).scalar_one()
            assert contador == LIMITE

        respuesta = application.test_client().post(
            f"/confirm-balance/{token}/verify",
            data={
                "first_name": "Cliente",
                "last_name": "Prueba",
                "email": "cliente@example.test",
                "code": "123456",
                "authorized": "on",
            },
            follow_redirects=True,
        )
        assert respuesta.status_code == 200
        assert "Se ha excedido el número de intentos permitidos" in respuesta.get_data(as_text=True)
        with application.app_context():
            invitation = database.session.get(BalanceConfirmationInvitation, ids["invitation"])
            assert invitation.status == "pending"
            assert invitation.failed_attempts == LIMITE
    finally:
        if "ids" in locals():
            with application.app_context():
                database.session.execute(
                    database.delete(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.id == ids["invitation"])
                )
                database.session.execute(
                    database.delete(BalanceConfirmation).where(BalanceConfirmation.document_no == f"BC-{sufijo}")
                )
                database.session.execute(database.delete(Party).where(Party.code == f"CLI-{sufijo}"))
                database.session.execute(database.delete(Entity).where(Entity.code == f"a{sufijo}"))
                database.session.commit()
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
