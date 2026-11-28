# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1913: los formularios respetan los límites varchar del modelo User.

Perfil, alta y edición comparten los mismos topes (80 para nombres, 150 para
correo y 50 para teléfono) y deben rechazar el exceso antes de llegar a
PostgreSQL, no después con un error de base de datos.
"""

from __future__ import annotations

import pytest
from werkzeug.datastructures import MultiDict

from cacao_accounting.auth.forms import ProfileForm, UserCreateForm, UserEditForm
from cacao_accounting.database import User, database

LÍMITES = (("name", 80), ("name2", 80), ("last_name", 80), ("last_name2", 80), ("e_mail", 150), ("phone", 50))


def _base_profile() -> dict[str, str]:
    return {"name": "", "name2": "", "last_name": "", "last_name2": "", "e_mail": "", "phone": ""}


def _base_create() -> dict[str, str]:
    return {
        **_base_profile(),
        "usuario": "nuevo-usuario",
        "classification": "system",
        "password": "ClaveSegura-2026!",
        "confirm_password": "ClaveSegura-2026!",
    }


def _base_edit() -> dict[str, str]:
    return {**_base_profile(), "usuario": "usuario-editado", "classification": "system"}


@pytest.mark.parametrize(
    ("form_class", "base"),
    [(ProfileForm, _base_profile), (UserCreateForm, _base_create), (UserEditForm, _base_edit)],
    ids=["perfil", "alta", "edicion"],
)
@pytest.mark.parametrize(("field", "limite"), LÍMITES)
def test_los_formularios_rechazan_el_exceso_de_longitud(app, form_class, base, field, limite):
    """Cada campo sobrepasa el varchar del modelo y produce error de formulario."""
    datos = base()
    datos[field] = "x" * (limite + 1)

    with app.test_request_context("/"):
        form = form_class(formdata=MultiDict(datos))
        assert form.validate() is False
        assert field in form.errors


def test_los_limites_exactos_del_perfil_siguen_siendo_validos(app):
    """Los valores en el límite exacto no se rechazan."""
    datos = _base_profile()
    datos["name"] = "n" * 80
    datos["phone"] = "9" * 50

    with app.test_request_context("/"):
        form = ProfileForm(formdata=MultiDict(datos))
        assert form.validate() is True


def test_el_perfil_http_no_persiste_un_nombre_demasiado_largo(app, authenticated_client, reference_users):
    """El POST del perfil devuelve formulario con error y conserva al usuario."""
    user_id = str(reference_users["admin"].id)
    with app.app_context():
        anterior = database.session.get(User, user_id).name

    response = authenticated_client("admin").post(
        "/auth/profile",
        data={"name": "x" * 81, "guardar_perfil": "1"},
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "El nombre o apellido no puede superar los 80 caracteres." in cuerpo
    assert "Field must be at most 80 characters long." not in cuerpo
    with app.app_context():
        assert database.session.get(User, user_id).name == anterior
