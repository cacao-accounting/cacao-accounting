# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2187: la emisión concurrente deja un único token de recuperación vigente."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, current_thread
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from cacao_accounting import create_app
from cacao_accounting.auth import device_verification
from cacao_accounting.auth.device_verification import generar_token_recuperacion, validar_token_recuperacion
from cacao_accounting.config import configuracion
from cacao_accounting.database import PasswordResetToken, User, database


def test_emisiones_concurrentes_conservan_un_solo_token(tmp_path, monkeypatch):
    """Dos solicitudes simultáneas se serializan y solo el último enlace sirve."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'reset-token.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0, "connect_args": {"timeout": 30}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    user_id = f"reset-{uuid4().hex[:8]}"
    with app.app_context():
        database.create_all()
        database.session.add(User(id=user_id, user=user_id, name="Usuario", password=b"x", active=True))
        database.session.commit()

    locks: list[str] = []
    original_lock = device_verification._lock_secret_issuance

    def tracking_lock(target_user_id: str) -> None:
        locks.append(target_user_id)
        original_lock(target_user_id)

    monkeypatch.setattr(device_verification, "_lock_secret_issuance", tracking_lock)
    barrier = Barrier(2, timeout=30)

    def issue_token() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                token = generar_token_recuperacion(user_id)
                database.session.commit()
                return token
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        tokens = list(workers.map(lambda _: issue_token(), range(2)))

    with app.app_context():
        active = database.session.scalars(database.select(PasswordResetToken).filter_by(user_id=user_id, consumed=False)).all()
        assert len(active) == 1
        assert sum(validar_token_recuperacion(token) is not None for token in tokens) == 1
        database.session.commit()

    assert locks.count(user_id) == 2


@pytest.mark.database
def test_emisiones_concurrentes_en_postgresql_bloquean_al_segundo(monkeypatch):
    """El segundo emisor no avanza hasta que el primero confirma su token."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("postgresql"):
        pytest.skip("La carrera de emisión requiere PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    schema_name = f"reset_race_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri)
    with bootstrap_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    engine_options: Any = {
        "pool_size": 2,
        "max_overflow": 0,
        "connect_args": {"options": f"-csearch_path={schema_name}"},
    }
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": cast(Any, engine_options),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    user_id = f"reset-{uuid4().hex[:8]}"
    primero_en_lock = Event()
    liberar_primero = Event()
    segundo_intenta = Event()
    segundo_salio = Event()
    segundo_termino = Event()
    hilo_primero: list[Any] = []
    locks: list[str] = []
    original_lock = device_verification._lock_secret_issuance

    def observing_lock(target_user_id: str) -> None:
        if not hilo_primero:
            hilo_primero.append(current_thread())
            locks.append(target_user_id)
            original_lock(target_user_id)
            primero_en_lock.set()
            if not liberar_primero.wait(timeout=30):
                raise RuntimeError("El primer emisor no fue liberado a tiempo.")
            return
        if current_thread() is hilo_primero[0]:
            original_lock(target_user_id)
            return
        locks.append(target_user_id)
        segundo_intenta.set()
        original_lock(target_user_id)
        segundo_salio.set()

    def issue_token(orden: int) -> str:
        with app.app_context():
            try:
                token = generar_token_recuperacion(user_id)
                database.session.commit()
                if orden == 1:
                    segundo_termino.set()
                return token
            finally:
                database.session.remove()

    monkeypatch.setattr(device_verification, "_lock_secret_issuance", observing_lock)
    try:
        with app.app_context():
            database.create_all()
            database.session.add(User(id=user_id, user=user_id, name="Usuario", password=b"x", active=True))
            database.session.commit()
            database.session.remove()

        with ThreadPoolExecutor(max_workers=2) as workers:
            primero = workers.submit(issue_token, 0)
            assert primero_en_lock.wait(timeout=15)
            segundo = workers.submit(issue_token, 1)
            assert segundo_intenta.wait(timeout=15)
            assert not segundo_salio.wait(timeout=0.5)
            assert not segundo_termino.wait(timeout=0.5)
            liberar_primero.set()
            tokens = [primero.result(timeout=30), segundo.result(timeout=30)]

        with app.app_context():
            active = database.session.scalars(
                database.select(PasswordResetToken).filter_by(user_id=user_id, consumed=False)
            ).all()
            assert len(active) == 1
            assert sum(validar_token_recuperacion(token) is not None for token in tokens) == 1
            database.session.commit()
    finally:
        liberar_primero.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        bootstrap_engine.dispose()

    assert locks.count(user_id) == 2
