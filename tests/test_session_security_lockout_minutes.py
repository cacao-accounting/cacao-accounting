# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2013: el lockout se muestra redondeando al minuto, sin sumar uno extra.

Sesenta segundos restantes son un minuto; sesenta y uno son dos. El cálculo
anterior `(segundos // 60) + 1` mostraba dos minutos para un minuto exacto.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.admin.session_security_service import lockout_minutes_remaining
from cacao_accounting.auth import account_throttling
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Modules, User, database

FIXED_NOW = datetime(2026, 11, 6, 12, 0, 0)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, 0),
        (-5, 0),
        (0, 0),
        (1, 1),
        (59, 1),
        (60, 1),
        (61, 2),
        (119, 2),
        (120, 2),
        (121, 3),
    ],
)
def test_lockout_minutes_round_up_without_an_extra_minute(seconds, expected):
    """The admin UI reports the real remaining minutes."""
    assert lockout_minutes_remaining(seconds) == expected


@pytest.fixture
def session_security_scenario(monkeypatch):
    """Create an admin and a locked user with a controlled clock."""
    monkeypatch.setattr(account_throttling, "_now_utc", lambda: FIXED_NOW)
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
                User(
                    id=f"locked-{suffix}",
                    user=f"locked-{suffix}",
                    name="Cuenta Bloqueada",
                    password=b"unused",
                    active=True,
                    failed_login_count=5,
                    lockout_until=FIXED_NOW + timedelta(seconds=60),
                ),
            ]
        )
        database.session.commit()
        ids = {"admin": f"admin-{suffix}", "locked_username": f"locked-{suffix}"}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_session_security_page_shows_one_minute_for_an_exact_lockout(session_security_scenario):
    """A 60-second lockout renders as one minute, not two."""
    app, ids = session_security_scenario
    client = _authenticated_client(app, ids["admin"])

    response = client.get("/settings/session-security")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["locked_username"] in body
    assert "1 min(s)" in body
    assert "2 min(s)" not in body
