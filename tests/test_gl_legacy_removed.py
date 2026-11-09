# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Superficie GL legacy retirada en favor del flujo de comprobantes.

Escenario de negocio: las pantallas ``/accounting/gl/list`` y
``/accounting/gl/new`` no tenían POST, contexto ni persistencia. El flujo
operativo es el módulo de comprobantes (``/accounting/journal/...``); las rutas
legacy no deben seguir simulando una pantalla funcional.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Modules, User, database

CONTRASENA = "gl-legacy-2026"


@pytest.fixture
def contabilidad_admin():
    """Cloud contable con administrador."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
                Modules(module="accounting", default=False, enabled=True),
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
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.parametrize("ruta", ["/accounting/gl/list", "/accounting/gl/new"])
def test_rutas_gl_legacy_estan_retiradas(contabilidad_admin, ruta):
    """Las pantallas legacy ya no responden."""
    client = contabilidad_admin.test_client()
    _iniciar(client)

    assert client.get(ruta).status_code == 404


@pytest.mark.parametrize("ruta", ["/accounting/journal/list", "/accounting/journal/new"])
def test_flujo_canonico_de_comprobantes_sigue_disponible(contabilidad_admin, ruta):
    """El flujo operativo de comprobantes conserva sus pantallas."""
    client = contabilidad_admin.test_client()
    _iniciar(client)

    response = client.get(ruta)

    assert response.status_code == 200
