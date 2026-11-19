# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""P4/#1355: el cambio administrativo de clave revoca credenciales.

Cambiar la contraseña desde administración debe invalidar sesiones y tokens
del usuario afectado, igual que el restablecimiento por correo.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import Modules, User, database


def test_admin_password_change_revokes_token_and_auth_version(app, authenticated_client):
    """The administrative password form bumps auth_version and clears token."""
    suffix = uuid4().hex[:6]
    user_id = f"target-{suffix}"
    with app.app_context():
        admin_module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if admin_module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            admin_module.enabled = True
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Usuario objetivo",
                password=proteger_passwd("ClaveAnterior-2026!"),
                active=True,
                token="jwt-previo",
                auth_version=0,
            )
        )
        database.session.commit()

    response = authenticated_client().post(
        f"/settings/users/{user_id}/password",
        data={"password": "NuevaClave-2026!", "confirm_password": "NuevaClave-2026!"},
    )

    assert response.status_code == 302
    with app.app_context():
        user = database.session.get(User, user_id)
        assert user is not None
        assert user.token is None
        assert user.auth_version == 1
