# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Etiquetas de acción de los formularios de usuario (#2022).

Escenario de negocio: ``crear_usuario`` y ``editar_usuario`` pasan a la
plantilla la acción traducida (``_("Nuevo Usuario")`` / ``_("Actualizar
Usuario")``), de modo que el botón de envío muestra un texto localizado en
lugar de un literal crudo con variables. El catálogo en inglés traduce las
etiquetas como ``New User`` y ``Update User``.
"""

from __future__ import annotations

import os

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Roles, User, database

BOTON_ENVIO = '<button type="submit" class="btn btn-primary">{texto}</button>'


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


def _crear_usuario_interno(app, *, language: str | None = None, classification: str = "system") -> str:
    """Crea un usuario único y devuelve su identificador."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        usuario = User(
            id=f"usr-{uuid4().hex[:21]}",
            user=f"forma{sufijo}",
            name="Usuario Formulario",
            password=b"x",
            active=True,
            classification=classification,
            language=language,
        )
        database.session.add(usuario)
        database.session.commit()
        return usuario.id


def test_formulario_de_alta_muestra_la_etiqueta_nuevo_usuario(app, authenticated_client, modulo_admin_activo):
    """El botón del formulario de alta presenta la acción traducida, no un literal crudo."""
    if os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}:
        pytest.skip("El módulo admin de usuarios no aplica en modo escritorio.")
    respuesta = authenticated_client().get("/settings/users/new")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert BOTON_ENVIO.format(texto="Nuevo Usuario") in html
    assert "Actualizar Usuario" not in html


def test_formulario_de_edicion_muestra_la_etiqueta_actualizar_usuario(app, authenticated_client, modulo_admin_activo):
    """El botón del formulario de edición presenta la acción de actualización traducida."""
    if os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}:
        pytest.skip("El módulo admin de usuarios no aplica en modo escritorio.")
    usuario_id = _crear_usuario_interno(app)

    respuesta = authenticated_client().get(f"/settings/users/{usuario_id}/edit")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert BOTON_ENVIO.format(texto="Actualizar Usuario") in html
    assert "Nuevo Usuario" not in html


def test_alta_en_ingles_traduce_la_accion_del_boton(app, authenticated_client, modulo_admin_activo):
    """#2022: con locale en el botón no queda en español."""
    from flask_babel import force_locale

    with force_locale("en"):
        respuesta = authenticated_client().get("/settings/users/new")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert BOTON_ENVIO.format(texto="New User") in html
    assert BOTON_ENVIO.format(texto="Nuevo Usuario") not in html


def test_edicion_en_ingles_traduce_la_accion_del_boton(app, authenticated_client, modulo_admin_activo):
    """#2022: la edición de usuario también sigue el locale inglés."""
    from flask_babel import force_locale

    usuario_id = _crear_usuario_interno(app)
    with force_locale("en"):
        respuesta = authenticated_client().get(f"/settings/users/{usuario_id}/edit")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert BOTON_ENVIO.format(texto="Update User") in html
    assert BOTON_ENVIO.format(texto="Actualizar Usuario") not in html


def test_acciones_de_roles_tambien_se_traducen_al_ingles(app, authenticated_client, modulo_admin_activo):
    """Las etiquetas adicionales de crear y editar rol mantienen el idioma activo."""
    from flask_babel import force_locale

    client = authenticated_client()
    with app.app_context():
        role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
        role_id = role.id

    with force_locale("en"):
        create_response = client.get("/settings/roles/new")
        edit_response = client.get(f"/settings/roles/{role_id}/edit")

    assert create_response.status_code == 200
    assert edit_response.status_code == 200
    assert "Save role" in create_response.get_data(as_text=True)
    assert "Update role" in edit_response.get_data(as_text=True)
    assert "Guardar rol" not in create_response.get_data(as_text=True)
    assert "Actualizar rol" not in edit_response.get_data(as_text=True)
