# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1740: los errores de administración de usuarios se traducen al inglés."""

from __future__ import annotations

import pytest
from flask_babel import force_locale, gettext

from cacao_accounting.database import Modules, User, database

MENSAJES = {
    "Los usuarios de portal requieren un tercero asociado.": "Portal users require an associated party.",
    "Los usuarios de portal requieren una compañía asociada.": "Portal users require an associated company.",
    "El tercero no corresponde a la clasificación del portal.": "The party does not match the portal classification.",
    "El nombre de usuario ya está en uso.": "The username is already in use.",
    "El correo electrónico ya está en uso.": "The email address is already in use.",
    "Retire los roles antes de convertir el usuario en portal.": (
        "Remove the roles before converting the user to a portal user."
    ),
    "Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos.": (
        "Password too weak. Use at least 8 characters, upper and lower case letters, numbers and symbols."
    ),
}


@pytest.mark.parametrize(("espanol", "ingles"), MENSAJES.items())
def test_el_catalogo_traduce_los_errores_de_usuario(app, espanol, ingles):
    """Cada mensaje visible tiene su msgstr inglés."""
    with app.app_context(), force_locale("en"):
        assert gettext(espanol) == ingles


def test_password_debil_http_muestra_error_en_ingles(app, authenticated_client, reference_users):
    """La ruta de cambio de contraseña usa el catálogo con locale EN."""
    user_id = str(reference_users["admin"].id)
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
        usuario = database.session.get(User, user_id)
        idioma = usuario.language
        usuario.language = "en"
        database.session.commit()
    try:
        response = authenticated_client("admin").post(
            f"/settings/users/{user_id}/password",
            data={"password": "aaaaaaaa", "confirm_password": "aaaaaaaa"},
        )
    finally:
        with app.app_context():
            usuario = database.session.get(User, user_id)
            usuario.language = idioma
            modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if modulo is not None:
                if creado:
                    database.session.delete(modulo)
                else:
                    modulo.enabled = anterior
            database.session.commit()

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Password too weak." in cuerpo
    assert "Contraseña muy débil" not in cuerpo
