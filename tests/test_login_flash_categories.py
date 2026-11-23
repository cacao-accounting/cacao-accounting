# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1908: un fallo de acceso no se presenta con estilo de éxito."""

from __future__ import annotations

from cacao_accounting.database import User, database


def test_login_fallido_muestra_alerta_de_error(app):
    """Credenciales inválidas usan alert-danger, no alert-success."""
    with app.app_context():
        database.session.add(User(id="login-fail", user="login-fail", name="Fallo", password=b"x", active=False))
        database.session.commit()

    respuesta = app.test_client().post("/login", data={"usuario": "login-fail", "acceso": "mala"}, follow_redirects=True)
    html = respuesta.get_data(as_text=True)

    assert "alert-danger" in html
    assert "alert-success" not in html
