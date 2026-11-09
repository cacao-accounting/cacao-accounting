# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El desbloqueo se redondea al minuto, sin sumar uno de más.

Escenario de negocio (issue #2013): la plantilla hacía ``(segundos // 60) + 1``;
con 60, 120 o 180 segundos exactos mostraba un minuto adicional.
"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.admin.session_security_service import lockout_minutes_remaining
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Modules, User, database


@pytest.mark.parametrize(
    ("segundos", "minutos"),
    [(0, 0), (1, 1), (59, 1), (60, 1), (61, 2), (120, 2), (121, 3), (180, 3)],
)
def test_redondeo_hacia_arriba_con_minimo_uno(segundos, minutos):
    """El cociente se redondea hacia arriba, sin sobrecontar múltiplos."""
    assert lockout_minutes_remaining(segundos) == minutos


def test_la_pantalla_muestra_un_minuto_para_sesenta_segundos(monkeypatch):
    """El HTML usa el valor calculado y no la fórmula anterior."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                User(
                    id="bloqueado",
                    user="bloqueado",
                    name="Bloqueado",
                    password=b"x",
                    active=True,
                    classification="system",
                    failed_login_count=5,
                ),
            ]
        )
        database.session.commit()
        bloqueado = database.session.get(User, "bloqueado")

    admin_routes = importlib.import_module("cacao_accounting.admin.routes")
    monkeypatch.setattr(admin_routes, "listar_cuentas_bloqueadas", lambda: [(bloqueado, 60)])
    monkeypatch.setattr(admin_routes, "listar_todos_dispositivos", lambda: [])

    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/settings/session-security")

        assert respuesta.status_code == 200
        assert "1 min(s)" in respuesta.get_data(as_text=True)
        assert "2 min(s)" not in respuesta.get_data(as_text=True)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
