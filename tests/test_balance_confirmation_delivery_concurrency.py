# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1702: expiración y respuesta compiten sin sobrescribir el estado terminal."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, or_, text, update

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation_bp import _mark_expired
from cacao_accounting.database import (
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Currency,
    Entity,
    Party,
    database,
)

pytestmark = pytest.mark.database


def _app(tmp_path):
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'balance-race.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 30}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
    return application


def _confirmacion(application, *, expira_en: timedelta) -> str:
    sufijo = uuid4().hex[:6]
    token = f"race-{sufijo}"
    with application.app_context():
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Alfa {sufijo}",
                    tax_id=f"T-{sufijo}",
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
            expires_at=datetime.now(timezone.utc) + expira_en,
        )
        database.session.add(confirmation)
        database.session.flush()
        database.session.add(
            BalanceConfirmationInvitation(
                balance_confirmation_id=confirmation.id,
                email="cliente@example.test",
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                verification_code_hash=hashlib.sha256(b"123456").hexdigest(),
                status="pending",
                failed_attempts=0,
                expires_at=confirmation.expires_at,
            )
        )
        database.session.commit()
        return confirmation.id


def _responder(application, confirmation_id: str) -> int:
    with application.app_context():
        now = datetime.now(timezone.utc)
        result = database.session.execute(
            update(BalanceConfirmation)
            .where(
                BalanceConfirmation.id == confirmation_id,
                BalanceConfirmation.status.in_(("sent", "viewed")),
                BalanceConfirmation.response_type.is_(None),
                BalanceConfirmation.responded_at.is_(None),
                or_(BalanceConfirmation.expires_at.is_(None), BalanceConfirmation.expires_at >= now),
            )
            .values(status="confirmed", response_type="confirmed", responded_at=now)
            .execution_options(synchronize_session=False)
        )
        database.session.commit()
        return int(getattr(result, "rowcount", 0))


def _expirar(application, confirmation_id: str) -> bool:
    with application.app_context():
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        resultado = _mark_expired(confirmation)
        database.session.commit()
        return resultado


def _carrera(application, confirmation_id: str) -> tuple[int, bool]:
    barrier = Barrier(2, timeout=30)
    with ThreadPoolExecutor(max_workers=2) as workers:

        def responder():
            barrier.wait()
            return _responder(application, confirmation_id)

        def expirar():
            barrier.wait()
            return _expirar(application, confirmation_id)

        respuesta = workers.submit(responder)
        expiracion = workers.submit(expirar)
        return respuesta.result(timeout=30), expiracion.result(timeout=30)


def test_respuesta_gana_y_expiracion_no_sobrescribe_estado_terminal(tmp_path):
    application = _app(tmp_path)
    confirmation_id = _confirmacion(application, expira_en=timedelta(hours=1))
    try:
        filas, _ = _carrera(application, confirmation_id)
        with application.app_context():
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            assert filas == 1
            assert confirmation.status == "confirmed"
            assert confirmation.response_type == "confirmed"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_expiracion_gana_y_respuesta_no_sobrescribe(tmp_path):
    application = _app(tmp_path)
    confirmation_id = _confirmacion(application, expira_en=timedelta(seconds=-1))
    try:
        filas, _ = _carrera(application, confirmation_id)
        with application.app_context():
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            assert confirmation.status == "expired"
            assert filas == 0
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _postgresql_uri() -> str:
    """Devuelve la URI Tier 1 configurada o salta el caso fuera de CI."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("postgresql"):
        pytest.skip("La carrera expiración/respuesta se valida en PostgreSQL Tier 1.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return uri


def _postgresql_app(uri: str):
    """Crea la app en un esquema PostgreSQL aislado por ejecución."""
    schema_name = f"bc_race_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri)
    with bootstrap_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    bootstrap_engine.dispose()
    engine_options: Any = {
        "pool_size": 4,
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
            "SECRET_KEY": "isolated-balance-race-test",
        }
    )
    with application.app_context():
        database.create_all()
    return application


def test_carrera_expiracion_y_respuesta_en_postgresql():
    """QA2 H1: la respuesta gana y el UPDATE condicional no la degrada en Tier 1."""
    application = _postgresql_app(_postgresql_uri())
    confirmation_id = _confirmacion(application, expira_en=timedelta(hours=1))
    try:
        filas, _ = _carrera(application, confirmation_id)
        with application.app_context():
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            assert filas == 1
            assert confirmation.status == "confirmed"
            assert confirmation.response_type == "confirmed"
            assert confirmation.responded_at is not None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_carrera_expiracion_gana_en_postgresql():
    """QA2 H1: con la solicitud vencida la respuesta CAS no la reabre."""
    application = _postgresql_app(_postgresql_uri())
    confirmation_id = _confirmacion(application, expira_en=timedelta(seconds=-1))
    try:
        filas, _ = _carrera(application, confirmation_id)
        with application.app_context():
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            assert filas == 0
            assert confirmation.status == "expired"
            assert confirmation.response_type is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
