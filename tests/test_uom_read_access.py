# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Permiso de lectura del catálogo global de UOM.

Escenario de negocio: UOM es global y no requiere compañía, pero no debe
exponerse a un usuario autenticado sin permiso de consulta del módulo
Inventario. Listado y detalle exigen la misma lectura que las rutas de escritura.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import Modules, UOM, User, database

CONTRASENA = "uom-lectura-2026"


@pytest.fixture
def uom_cloud():
    """Cloud con una UOM y usuarios con/sin permiso de Inventario."""
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
                Modules(module="inventory", default=False, enabled=True),
                UOM(code="UND", name="Unidad"),
                User(
                    id="lector",
                    user="lector",
                    name="Lector Inventario",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="sinacceso",
                    user="sinacceso",
                    name="Sin Acceso",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("lector", "inventory_user")
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_usuario_sin_permiso_no_lee_el_catalogo(uom_cloud):
    """Sin consulta de Inventario, listado y detalle responden 403."""
    client = uom_cloud.test_client()
    _iniciar(client, "sinacceso")

    assert client.get("/inventory/uom/list").status_code == 403
    assert client.get("/inventory/uom/UND").status_code == 403


def test_usuario_con_permiso_lee_el_catalogo(uom_cloud):
    """Control positivo: inventory_user accede al catálogo global."""
    client = uom_cloud.test_client()
    _iniciar(client, "lector")

    response = client.get("/inventory/uom/list")

    assert response.status_code == 200
    assert "UND" in response.get_data(as_text=True)
    detalle = client.get("/inventory/uom/UND")
    assert detalle.status_code == 200
    assert "Unidad" in detalle.get_data(as_text=True)
