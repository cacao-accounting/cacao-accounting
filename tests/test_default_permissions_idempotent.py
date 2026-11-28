# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1730: la carga inicial de permisos es idempotente al reintentar."""

from __future__ import annotations

from sqlalchemy import func, select

from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import crea_roles_predeterminados
from cacao_accounting.database import RolesAccess, database


def test_recargar_permisos_no_duplica_filas(app, entorno_contable):
    """Un reintento tras inicialización parcial conserva el mismo conjunto."""
    del entorno_contable
    with app.app_context():
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        antes = database.session.execute(select(func.count(RolesAccess.id))).scalar_one()
        cargar_permisos_predeterminados()
        despues = database.session.execute(select(func.count(RolesAccess.id))).scalar_one()

    assert antes > 0
    assert despues == antes
