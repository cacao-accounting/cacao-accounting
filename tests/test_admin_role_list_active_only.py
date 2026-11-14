# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Los roles revocados no se presentan como asignaciones vigentes (#2064).

Escenario de negocio: una asignación con ``RolesUser.active=False`` está
revocada y no concede acceso; por coherencia la lista de usuarios tampoco debe
mostrarla como rol del usuario y el formulario de asignación de roles no debe
preseleccionarla. Las asignaciones activas se siguen mostrando y
preseleccionando.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Roles, RolesUser, User, database


@pytest.fixture
def modulo_admin_activo(app):
    """Habilita el módulo admin para las rutas de configuración y restaura su estado al salir."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            fue_creado = True
            estado_previo = True
        else:
            fue_creado = False
            estado_previo = modulo.enabled
            modulo.enabled = True
        database.session.commit()

    yield

    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if fue_creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = estado_previo
            database.session.commit()


def _crear_usuario_con_roles(app) -> tuple[str, str, str, str]:
    """Crea un usuario interno con un rol activo y otro revocado.

    Devuelve ``(user_id, rol_activo_id, rol_activo_nombre, rol_revocado_nombre)``.
    """
    sufijo = uuid4().hex[:8]
    with app.app_context():
        usuario = User(
            id=f"usr-{uuid4().hex[:21]}",
            user=f"roles{sufijo}",
            name="Usuario con Roles",
            password=b"x",
            active=True,
            classification="system",
        )
        rol_activo = Roles(name=f"rol vigente {sufijo}", note="rol asignado y activo")
        rol_revocado = Roles(name=f"rol retirado {sufijo}", note="rol revocado para la prueba")
        database.session.add_all([usuario, rol_activo, rol_revocado])
        database.session.flush()
        database.session.add_all(
            [
                RolesUser(user_id=usuario.id, role_id=rol_activo.id, active=True),
                RolesUser(user_id=usuario.id, role_id=rol_revocado.id, active=False),
            ]
        )
        database.session.commit()
        return usuario.id, rol_activo.id, rol_activo.name, rol_revocado.name


def _casilla_de(html: str, valor: str) -> str | None:
    """Devuelve la etiqueta ``<input>`` cuya casilla tenga el valor indicado."""
    coincidencia = re.search(rf'<input[^>]*value="{re.escape(valor)}"[^>]*>', html)
    return coincidencia.group(0) if coincidencia else None


def test_lista_usuarios_omite_roles_revocados(app, authenticated_client, modulo_admin_activo):
    """La columna de roles de la lista de usuarios solo presenta asignaciones vigentes."""
    _user_id, _rol_activo_id, rol_activo, rol_revocado = _crear_usuario_con_roles(app)

    respuesta = authenticated_client().get("/settings/users")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert rol_activo in html
    assert rol_revocado not in html


def test_formulario_roles_no_preselecciona_roles_revocados(app, authenticated_client, modulo_admin_activo):
    """El formulario de roles solo marca como seleccionadas las asignaciones activas."""
    user_id, rol_activo_id, _rol_activo, _rol_revocado = _crear_usuario_con_roles(app)

    respuesta = authenticated_client().get(f"/settings/users/{user_id}/roles")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    casilla_activa = _casilla_de(html, rol_activo_id)
    assert casilla_activa is not None
    assert "checked" in casilla_activa
    opciones = re.findall(r'<input[^>]*name="roles"[^>]*type="checkbox"[^>]*>', html)
    assert any("checked" in casilla for casilla in opciones)
    assert any("checked" not in casilla for casilla in opciones)


def test_formulario_roles_sigue_listando_el_rol_revocado_como_opcion(app, authenticated_client, modulo_admin_activo):
    """El rol revocado permanece disponible para reasignarse, sin marcarse como vigente."""
    user_id, _rol_activo_id, _rol_activo, rol_revocado = _crear_usuario_con_roles(app)

    respuesta = authenticated_client().get(f"/settings/users/{user_id}/roles")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert rol_revocado in html
