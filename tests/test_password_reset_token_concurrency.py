# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2187: la emisión concurrente deja un único token de recuperación vigente."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

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
    barrier = Barrier(2)

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
def test_emisiones_concurrentes_en_postgresql_conservan_un_solo_token(monkeypatch):
    """La serialización se valida con conexiones concurrentes al motor Tier 1."""
    app = create_app({**configuracion, "TESTING": True, "WTF_CSRF_ENABLED": False})
    with app.app_context():
        if database.engine.dialect.name != "postgresql":
            pytest.skip("La carrera de emisión requiere PostgreSQL.")
        user_id = f"reset-{uuid4().hex[:8]}"
        database.session.add(User(id=user_id, user=user_id, name="Usuario", password=b"x", active=True))
        database.session.commit()

    locks: list[str] = []
    lock_rendezvous = Barrier(2)
    original_lock = device_verification._lock_secret_issuance

    def tracking_lock(target_user_id: str) -> None:
        locks.append(target_user_id)
        lock_rendezvous.wait(timeout=10)
        original_lock(target_user_id)

    monkeypatch.setattr(device_verification, "_lock_secret_issuance", tracking_lock)
    barrier = Barrier(2)

    def issue_token(_):
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                token = generar_token_recuperacion(user_id)
                database.session.commit()
                return token
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        tokens = list(workers.map(issue_token, range(2)))

    with app.app_context():
        active = database.session.scalars(database.select(PasswordResetToken).filter_by(user_id=user_id, consumed=False)).all()
        assert len(active) == 1
        assert sum(validar_token_recuperacion(token) is not None for token in tokens) == 1

    assert locks.count(user_id) == 2
