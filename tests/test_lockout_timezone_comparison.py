# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1738: el bloqueo compara valores con zona horaria sin TypeError."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest


def test_lockout_aware_futuro_bloquea(app):
    """Un lockout aware futuro se interpreta como bloqueado."""
    from cacao_accounting.auth.account_throttling import esta_bloqueada

    usuario = SimpleNamespace(lockout_until=datetime.now(timezone.utc) + timedelta(minutes=5), failed_login_attempts=3)
    with app.app_context():
        assert esta_bloqueada(usuario) is True


def test_lockout_aware_pasado_desbloquea(app, monkeypatch):
    """Un lockout aware vencido se trata como no bloqueado."""
    from cacao_accounting.auth import account_throttling

    usuario = SimpleNamespace(lockout_until=datetime.now(timezone.utc) - timedelta(minutes=5), failed_login_attempts=3)
    monkeypatch.setattr(account_throttling, "_desbloquear_cuenta", lambda u: None)
    with app.app_context():
        assert account_throttling.esta_bloqueada(usuario) is False


def test_tiempo_restante_acepta_lockout_aware(app, monkeypatch):
    """El tiempo restante calcula lockouts PostgreSQL aware en UTC."""
    from cacao_accounting.auth import account_throttling

    ahora = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    usuario = SimpleNamespace(lockout_until=ahora + timedelta(minutes=5))
    monkeypatch.setattr(account_throttling, "_now_utc", lambda: ahora.replace(tzinfo=None))

    with app.app_context():
        assert account_throttling.tiempo_restante_bloqueo(usuario) == 300


def test_listar_cuentas_bloqueadas_acepta_lockout_aware(app, monkeypatch):
    """El listado calcula el tiempo de filas aware sin comparar zonas mixtas."""
    from cacao_accounting.auth import account_throttling

    ahora = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    usuario = SimpleNamespace(lockout_until=ahora + timedelta(minutes=5))
    monkeypatch.setattr(account_throttling, "_now_utc", lambda: ahora.replace(tzinfo=None))
    monkeypatch.setattr(
        account_throttling.database.session,
        "scalars",
        lambda _query: SimpleNamespace(all=lambda: [usuario]),
    )

    with app.app_context():
        assert account_throttling.listar_cuentas_bloqueadas() == [(usuario, 300)]


@pytest.mark.database
def test_lockout_persistido_en_postgresql():
    """Un lockout real con zona se lee por las tres rutas de throttling."""
    from cacao_accounting import create_app
    from cacao_accounting.auth import account_throttling
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import User, database

    application = create_app({**configuracion, "TESTING": True, "WTF_CSRF_ENABLED": False})
    with application.app_context():
        if database.engine.dialect.name != "postgresql":
            pytest.skip("La persistencia de lockout con zona requiere PostgreSQL.")
        user_id = f"lockout-{uuid4().hex[:8]}"
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Lockout",
                password=b"x",
                active=True,
                lockout_until=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        database.session.commit()
        database.session.expire_all()
        usuario = database.session.get(User, user_id)

        assert account_throttling.esta_bloqueada(usuario) is True
        restante = account_throttling.tiempo_restante_bloqueo(usuario)
        assert restante is not None and 0 < restante <= 300
        bloqueadas = account_throttling.listar_cuentas_bloqueadas()
        assert any(str(bloqueado.id) == user_id for bloqueado, _ in bloqueadas)
