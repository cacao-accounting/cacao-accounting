# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El diagnóstico de versión de base de datos no registra credenciales."""

from __future__ import annotations

from io import StringIO

from cacao_accounting.datos.base import _log_database_version
from cacao_accounting.database import database
from cacao_accounting.logs import log


def test_diagnostico_no_escribe_uri_ni_parametros_sensibles(app, monkeypatch):
    """Conserva la versión del motor sin emitir usuario, contraseña o token."""
    uri = "postgresql+psycopg2://ci-user:ci-password@db.internal/cacao?sslpassword=ssl-secret&token=token-secret"
    salida = StringIO()
    sink_id = log.add(salida, format="{message}")
    try:
        with app.app_context():
            app.config["SQLALCHEMY_DATABASE_URI"] = uri
            monkeypatch.setattr(database.session, "execute", lambda _query: [("PostgreSQL 16",)])

            _log_database_version()
    finally:
        log.remove(sink_id)

    resultado = salida.getvalue()
    assert "Running on Postgresql." in resultado
    assert "PostgreSQL 16" in resultado
    assert "ci-user" not in resultado
    assert "ci-password" not in resultado
    assert "ssl-secret" not in resultado
    assert "token-secret" not in resultado
