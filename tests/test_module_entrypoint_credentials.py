# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1602: el entrypoint del módulo exige credenciales iniciales seguras.

`python -m cacao_accounting` debe usar `resolver_credenciales_iniciales` y
detenerse en producción cuando faltan `CACAO_USER`/`CACAO_PSWD`, sin crear el
administrador predeterminado.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.__main__ import inicializar_si_hace_falta
from cacao_accounting.config import configuracion
from cacao_accounting.database import User, database
from cacao_accounting.database.helpers import usuarios_creados


@pytest.fixture
def entrypoint_scenario():
    """Create an app with an empty database for the entrypoint."""
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
    with app.app_context():
        database.create_all()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_entrypoint_stops_without_credentials_in_production(entrypoint_scenario, monkeypatch):
    """Production without initial credentials exits before creating an admin."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("CACAO_TEST", raising=False)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with entrypoint_scenario.app_context():
        with pytest.raises(SystemExit) as error:
            inicializar_si_hace_falta(entrypoint_scenario, esperar_segundos=0)

        assert error.value.code == 1
        assert usuarios_creados() is False
        assert database.session.execute(database.select(User)).scalars().all() == []


def test_entrypoint_uses_explicit_credentials(entrypoint_scenario, monkeypatch):
    """Explicit credentials initialize the administrator without defaults."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("CACAO_USER", "secure-admin")
    monkeypatch.setenv("CACAO_PSWD", "clave-segura-2026")
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("CACAO_TEST", raising=False)

    with entrypoint_scenario.app_context():
        inicializar_si_hace_falta(entrypoint_scenario, esperar_segundos=0)

        admin = database.session.execute(database.select(User).filter_by(user="secure-admin")).scalar_one_or_none()
        assert admin is not None
        assert usuarios_creados() is True
