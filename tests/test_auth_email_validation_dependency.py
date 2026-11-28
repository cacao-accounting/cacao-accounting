# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1948: la validación de correo funciona con la dependencia declarada.

Los formularios usan ``wtforms.validators.Email`` y el manifiesto declara
``email-validator``. La regresión recupera la validación de correo inválido y
vacío sin excepción, incluida la ruta de recuperación de contraseña.
"""

from __future__ import annotations

import pytest

from cacao_accounting.auth.forms import (
    ForgotPasswordForm,
    ProfileForm,
    UserCreateForm,
    UserEditForm,
)


def _datos(**overrides) -> dict:
    """Datos mínimos de un formulario de usuario con correo configurable."""
    datos = {
        "e_mail": "valido@example.com",
        "usuario": "valido",
        "password": "ClaveSegura1",
        "confirm_password": "ClaveSegura1",
        "classification": "system",
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize("form_class", [ProfileForm, UserCreateForm, UserEditForm])
def test_correo_invalido_produce_error_de_formulario(app, form_class):
    """Un correo inválido marca el campo sin lanzar excepción."""
    datos = _datos(e_mail="no-es-correo")
    with app.test_request_context("/", method="POST", data=datos):
        form = form_class()
        assert form.validate() is False
        assert form.e_mail.errors


@pytest.mark.parametrize("form_class", [ProfileForm, UserCreateForm, UserEditForm])
def test_correo_valido_no_marca_error_de_formato(app, form_class):
    """Un correo válido pasa el validador de formato."""
    datos = _datos()
    with app.test_request_context("/", method="POST", data=datos):
        form = form_class()
        form.validate()
        assert form.e_mail.errors == []


@pytest.mark.parametrize("form_class", [ProfileForm, UserCreateForm, UserEditForm])
def test_correo_vacio_es_opcional_en_los_formularios_de_perfil(app, form_class):
    """El correo vacío no lanza excepción en los formularios con Optional."""
    datos = _datos(e_mail="")
    with app.test_request_context("/", method="POST", data=datos):
        form = form_class()
        form.validate()
        assert form.e_mail.errors == []


def test_recuperacion_rechaza_correo_vacio_sin_excepcion(app):
    """El formulario de recuperación exige correo y no lanza excepción."""
    with app.test_request_context("/", method="POST", data={"email": ""}):
        form = ForgotPasswordForm()
        assert form.validate() is False
        assert form.email.errors


def test_recuperacion_rechaza_correo_invalido_sin_excepcion(app):
    """El formato inválido se informa como error del formulario."""
    with app.test_request_context("/", method="POST", data={"email": "sin-arroba"}):
        form = ForgotPasswordForm()
        assert form.validate() is False
        assert form.email.errors


def test_ruta_recuperacion_no_devuelve_500_con_correo_invalido(client):
    """La ruta pública procesa el correo inválido sin error interno."""
    response = client.post("/auth/forgot-password", data={"email": "sin-arroba"})

    assert response.status_code < 500
