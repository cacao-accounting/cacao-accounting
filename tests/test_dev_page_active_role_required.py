# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""La página de información para desarrolladores falla cerrado (#2075).

Escenario de negocio: ``/info`` (y sus alias ``/dev`` y ``/development``)
revelan detalles internos del sistema, por lo que exigen una asignación
vigente al rol ``admin`` (``RolesUser.active=True``). Una asignación revocada
no habilita la página y responde 403; una asignación activa sí concede acceso.
"""

from __future__ import annotations

from uuid import uuid4


from cacao_accounting.database import Roles, RolesUser, User, database

RUTAS_DESARROLLO = ("/info", "/dev", "/development")


def _cliente_como(app, user_id: str):
    """Devuelve un cliente HTTP autenticado con el usuario indicado."""
    cliente = app.test_client()
    with cliente.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return cliente


def _crear_usuario_con_rol_admin(app, *, activo: bool) -> str:
    """Crea un usuario interno nuevo con una asignación al rol admin en el estado dado."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        rol = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one_or_none()
        if rol is None:
            rol = Roles(name="admin", note="Administrador")
            database.session.add(rol)
            database.session.flush()
        usuario = User(
            id=f"usr-{uuid4().hex[:21]}",
            user=f"dev{sufijo}",
            name="Desarrollo",
            password=b"x",
            active=True,
            classification="user",
        )
        database.session.add(usuario)
        database.session.flush()
        database.session.add(RolesUser(user_id=usuario.id, role_id=rol.id, active=activo))
        database.session.commit()
        return usuario.id


def test_asignacion_admin_activa_permite_pagina_de_desarrollo(app):
    """El mismo acceso con la asignación vigente responde 200."""
    usuario_id = _crear_usuario_con_rol_admin(app, activo=True)

    respuesta = _cliente_como(app, usuario_id).get("/info")

    assert respuesta.status_code == 200


def test_admin_por_clasificacion_conserva_acceso_a_desarrollo(app, authenticated_client):
    """Control: el administrador del sistema sigue viendo la página de desarrollo."""
    respuesta = authenticated_client().get("/info")

    assert respuesta.status_code == 200


def test_asignacion_admin_revocada_no_permite_pagina_de_desarrollo(app):
    """Una asignación `active=False` no habilita `/info`, `/dev` ni `/development`."""
    usuario_id = _crear_usuario_con_rol_admin(app, activo=False)
    cliente = _cliente_como(app, usuario_id)

    for ruta in RUTAS_DESARROLLO:
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 403, ruta
