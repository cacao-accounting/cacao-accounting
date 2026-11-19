# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2153: el cierre de sesión exige POST y token CSRF.

Un enlace GET permitía que un sitio externo cerrara la sesión de la víctima.
La ruta ya es POST-only; esta regresión fija el contrato y comprueba que un
POST sin token no muta la sesión.
"""

from __future__ import annotations

import re

CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf_token(client) -> str:
    """Read the session CSRF token rendered by the authenticated shell."""
    response = client.get("/")
    assert response.status_code == 200
    match = CSRF_PATTERN.search(response.get_data(as_text=True))
    assert match is not None, "La página autenticada no expone csrf_token."
    return match.group(1)


def test_logout_requires_post_and_csrf(app, authenticated_client):
    """GET se rechaza; POST sin CSRF no cierra; POST con CSRF sí cierra."""
    app.config["WTF_CSRF_ENABLED"] = True
    client = authenticated_client("admin")
    token = _csrf_token(client)

    get_response = client.get("/logout")
    assert get_response.status_code == 405
    with client.session_transaction() as session:
        assert "_user_id" in session

    missing_token = client.post("/logout")
    assert missing_token.status_code == 400
    with client.session_transaction() as session:
        assert "_user_id" in session

    logged_out = client.post("/logout", data={"csrf_token": token})
    assert logged_out.status_code == 302
    with client.session_transaction() as session:
        assert "_user_id" not in session
