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

from cacao_accounting.database import Modules, User, database

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
