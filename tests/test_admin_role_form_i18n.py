# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1999: el formulario de roles traduce botones y errores en inglés.

Las vistas de alta/edición ya reciben los botones por argumentos; la regresión
comprueba el render real con un administrador cuyo idioma es inglés y que el
error de nombre duplicado también pasa por gettext.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import Modules, Roles, User, database


@pytest.fixture
def admin_en(app):
    """Administrador con idioma inglés y módulo administrativo activo."""
    sufijo = uuid4().hex[:6]
    user_id = f"admin-i18n-{sufijo}"
    marca = f"i18n-roles-{sufijo}"
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
        else:
            creado = False
            anterior = modulo.enabled
            modulo.enabled = True
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Administrador Inglés",
                password=proteger_passwd("AdminRole-2026!"),
                classification="admin",
                language="en",
                active=True,
            )
        )
        database.session.commit()
    yield user_id, marca
    with app.app_context():
        database.session.execute(database.delete(Roles).where(Roles.note == marca))
        database.session.execute(database.delete(User).where(User.id == user_id))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def _cliente(app, user_id: str):
    """Autentica un cliente con el administrador de idioma inglés."""
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def test_alta_de_rol_renderiza_boton_traducido(app, admin_en):
    """El botón Guardar rol se muestra en inglés."""
    user_id, _marca = admin_en
    response = _cliente(app, user_id).get("/settings/roles/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Create Role" in cuerpo
    assert "Save role" in cuerpo
    assert "Guardar rol" not in cuerpo


def test_edicion_de_rol_renderiza_boton_traducido(app, admin_en):
    """El botón Actualizar rol se muestra en inglés."""
    user_id, marca = admin_en
    client = _cliente(app, user_id)
    assert client.post("/settings/roles/new", data={"name": f"Rol {marca}", "note": marca}).status_code == 302
    with app.app_context():
        role_id = database.session.execute(database.select(Roles.id).filter_by(name=f"Rol {marca}")).scalar_one()

    response = client.get(f"/settings/roles/{role_id}/edit")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Edit Role" in cuerpo
    assert "Update role" in cuerpo
    assert "Actualizar rol" not in cuerpo


def test_nombre_duplicado_en_alta_muestra_error_traducido(app, admin_en):
    """El alta con nombre repetido muestra el error en inglés."""
    user_id, marca = admin_en
    client = _cliente(app, user_id)
    nombre = f"Rol {marca}"
    assert client.post("/settings/roles/new", data={"name": nombre, "note": marca}).status_code == 302

    response = client.post("/settings/roles/new", data={"name": nombre, "note": marca})

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "The role name is already in use." in cuerpo
    assert "El nombre del rol ya está en uso." not in cuerpo
    with app.app_context():
        assert len(database.session.execute(database.select(Roles).filter_by(name=nombre)).scalars().all()) == 1


def test_nombre_duplicado_en_edicion_muestra_error_traducido(app, admin_en):
    """La edición hacia un nombre existente muestra el error en inglés."""
    user_id, marca = admin_en
    client = _cliente(app, user_id)
    primero = f"Rol A {marca}"
    segundo = f"Rol B {marca}"
    assert client.post("/settings/roles/new", data={"name": primero, "note": marca}).status_code == 302
    assert client.post("/settings/roles/new", data={"name": segundo, "note": marca}).status_code == 302
    with app.app_context():
        role_id = database.session.execute(database.select(Roles.id).filter_by(name=primero)).scalar_one()

    response = client.post(f"/settings/roles/{role_id}/edit", data={"name": segundo, "note": marca})

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "The role name is already in use." in cuerpo
    assert "El nombre del rol ya está en uso." not in cuerpo
    with app.app_context():
        persistido = database.session.get(Roles, role_id)
        assert persistido is not None
        assert persistido.name == primero
