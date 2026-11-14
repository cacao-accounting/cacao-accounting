# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Errores visibles del formulario de compañías de un usuario (#2021).

Escenario de negocio: al guardar el alcance de compañías con una elección
inválida (un valor que no pertenece a las opciones), la ruta re-renderiza el
formulario con estado 200 y la plantilla muestra el bloque de errores del
campo ``companies`` con ``role="alert"``; además, las asignaciones previas del
usuario deben conservarse intactas en la base de datos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, User, UserCompanyAccess, database

BLOQUE_ERROR_COMPANIAS = '<div class="text-danger small mb-2" role="alert">'
MENSAJES_ELECCION_INVALIDA = ("Opción inválida.", "Not a valid choice")


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


def _crear_usuario_interno(app) -> str:
    """Crea un usuario interno único apto para asignación de compañías."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        usuario = User(
            id=f"usr-{uuid4().hex[:21]}",
            user=f"compan{sufijo}",
            name="Usuario Compañías",
            password=b"x",
            active=True,
            classification="system",
        )
        database.session.add(usuario)
        database.session.commit()
        return usuario.id


def test_eleccion_invalida_renderiza_error_y_conserva_asignaciones(app, authenticated_client, modulo_admin_activo):
    """Una compañía fuera de las opciones re-renderiza con alerta y no altera la base."""
    usuario_id = _crear_usuario_interno(app)
    with app.app_context():
        database.session.add(UserCompanyAccess(user_id=usuario_id, company_code="cacao"))
        database.session.commit()

    respuesta = authenticated_client().post(
        f"/settings/users/{usuario_id}/companies",
        data={"companies": f"inexistente-{uuid4().hex[:6]}"},
    )

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert BLOQUE_ERROR_COMPANIAS in html
    assert "form.errors" not in html  # template renders field errors
    assert "alert" in html
    with app.app_context():
        asignaciones = (
            database.session.execute(database.select(UserCompanyAccess).filter_by(user_id=usuario_id)).scalars().all()
        )
        assert [asignacion.company_code for asignacion in asignaciones] == ["cacao"]


def test_envio_valido_sigue_reemplazando_el_alcance(app, authenticated_client, modulo_admin_activo):
    """Control: un envío válido con la opción real continúa guardando el alcance."""
    usuario_id = _crear_usuario_interno(app)
    with app.app_context():
        database.session.add(UserCompanyAccess(user_id=usuario_id, company_code="cacao"))
        database.session.commit()

    respuesta = authenticated_client().post(
        f"/settings/users/{usuario_id}/companies",
        data={"companies": "cacao"},
    )

    assert respuesta.status_code == 302
    with app.app_context():
        asignaciones = (
            database.session.execute(database.select(UserCompanyAccess).filter_by(user_id=usuario_id)).scalars().all()
        )
        assert [asignacion.company_code for asignacion in asignaciones] == ["cacao"]
