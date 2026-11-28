# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1732: desactivar un usuario invalida las sesiones Flask ya emitidas."""

from __future__ import annotations


def test_loader_rechaza_usuario_desactivado(app, entorno_contable):
    """cargar_sesion deja de reconocer al usuario cuando la cuenta se desactiva."""
    del entorno_contable
    from cacao_accounting.auth import cargar_sesion
    from cacao_accounting.database import User, database

    with app.app_context():
        user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user_id = user.id
        active_previa = user.active
        version_previa = user.auth_version
        assert cargar_sesion(user_id) is not None

        try:
            user.active = False
            user.auth_version = (user.auth_version or 0) + 1
            database.session.commit()

            assert cargar_sesion(user_id) is None
        finally:
            user.active = active_previa
            user.auth_version = version_previa
            database.session.commit()
