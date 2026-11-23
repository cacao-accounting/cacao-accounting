# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1738: el bloqueo compara valores con zona horaria sin TypeError."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


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
