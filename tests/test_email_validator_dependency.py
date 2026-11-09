# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La validación de correo funciona con las dependencias declaradas.

Escenario de negocio (issue #1948): los formularios usan ``Email()`` de WTForms,
que importa ``email_validator``. Sin la dependencia declarada, cualquier correo
no vacío lanzaba una excepción no manejada y la recuperación de contraseña
respondía 500 en una instalación limpia.
"""

from __future__ import annotations

from cacao_accounting.auth.forms import ForgotPasswordForm, UserEditForm


def test_el_validador_de_correo_esta_disponible(app):
    """Importar y validar no depende de una instalación manual adicional."""
    with app.test_request_context("/forgot-password", method="POST"):
        valido = ForgotPasswordForm(data={"email": "persona@example.com"})
        invalido = ForgotPasswordForm(data={"email": "no-es-un-correo"})

        assert valido.validate() is True
        assert invalido.validate() is False
        assert invalido.email.errors


def test_el_correo_opcional_vacio_no_falla_en_edicion(app):
    """Un correo vacío sigue siendo válido para los formularios opcionales."""
    with app.test_request_context("/settings/users/admin/edit", method="POST"):
        formulario = UserEditForm(data={"usuario": "admin", "classification": "system", "e_mail": ""})

        assert formulario.validate() is True
