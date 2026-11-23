# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2061: los entry points aplican credenciales iniciales seguras.

Cubre dos defectos: `verifica_coneccion_db()` trataba un `Result` vacío como
verdadero (una base conectada sin filas no se detectaba) y `server()` solo
validaba credenciales cuando la conexión fallaba, permitiendo arrancar Waitress
con una base conectada pero sin administrador y credenciales por defecto.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import User, database
from cacao_accounting.database import helpers as db_helpers
from cacao_accounting.database.helpers import verifica_coneccion_db


@pytest.fixture
def empty_db_app():
    """App con esquema creado pero sin usuarios."""
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


def test_verifica_conexion_detecta_base_vacia(empty_db_app, monkeypatch):
    """Una conexión válida sin filas se reporta como conectada."""
    monkeypatch.setenv("CACAO_TEST", "True")
    with empty_db_app.app_context():
        assert database.session.execute(database.select(User)).scalars().all() == []
        assert verifica_coneccion_db(empty_db_app) is True


def test_verifica_conexion_detecta_con_filas(empty_db_app, monkeypatch):
    """Control positivo: con filas presentes también reporta conectado."""
    monkeypatch.setenv("CACAO_TEST", "True")
    with empty_db_app.app_context():
        database.session.add(User(user="probe", name="Probe", password=b"x", active=True))
        database.session.commit()
        assert verifica_coneccion_db(empty_db_app) is True


def test_verifica_conexion_agota_reintentos_y_revierte_errores_sql(empty_db_app, monkeypatch):
    """Los fallos de conexión se revierten y todos los reintentos terminan en False."""
    import time

    monkeypatch.setenv("CACAO_TEST", "True")
    monkeypatch.setattr(db_helpers, "TIEMPO_ESPERA", 5)
    monkeypatch.setattr(time, "time", Mock(side_effect=[0, 0, 1, 2, 3, 5]))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    failures = [
        error_type("SELECT user", {}, RuntimeError("connection unavailable"))
        for error_type in (OperationalError, InterfaceError, ProgrammingError, OperationalError)
    ]
    execute = Mock(side_effect=failures)
    rollback = Mock()
    monkeypatch.setattr(database.session, "execute", execute)
    monkeypatch.setattr(database.session, "rollback", rollback)

    assert verifica_coneccion_db(empty_db_app) is False
    assert execute.call_count == 4
    assert rollback.call_count == 4


def test_server_detiene_arranque_sin_admin_ni_credenciales(empty_db_app, monkeypatch):
    """Waitress no expone una base vacía sin credenciales seguras."""
    import cacao_accounting.server as server_module

    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("CACAO_TEST", raising=False)

    import importlib

    db_helpers = importlib.import_module("cacao_accounting.database.helpers")

    served: list[bool] = []
    monkeypatch.setattr(server_module, "app", empty_db_app)
    monkeypatch.setattr(server_module, "serve", lambda *_a, **_k: served.append(True))
    monkeypatch.setattr(db_helpers, "verifica_coneccion_db", lambda _app: True)
    monkeypatch.setattr(db_helpers, "usuarios_creados", lambda: False)
    monkeypatch.setattr(
        db_helpers,
        "resolver_credenciales_iniciales",
        lambda: (_ for _ in ()).throw(ValueError("CACAO_USER and CACAO_PSWD must be set in environment")),
    )

    with pytest.raises(SystemExit) as error:
        server_module.server()

    assert error.value.code == 1
    assert served == []
