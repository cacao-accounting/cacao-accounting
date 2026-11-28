# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2024: la navegación de caja muestra los reportes con permiso `reportes`."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser, User, UserCompanyAccess, database


def _usuario(report: bool) -> str:
    sufijo = uuid4().hex[:6]
    user_id = f"cash-rep-{sufijo}"
    modulo = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one_or_none()
    if modulo is None:
        modulo = Modules(module="cash", default=False, enabled=True)
        database.session.add(modulo)
        database.session.flush()
    rol = Roles(name=f"rol-cash-{sufijo}", note="Caja reportes")
    database.session.add_all(
        [
            User(id=user_id, user=user_id, name="Reportes", password=b"unused", active=True, company="cacao"),
            rol,
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            RolesAccess(rol_id=rol.id, module_id=modulo.id, access=False, view=True, report=report),
            RolesUser(user_id=user_id, role_id=rol.id, active=True),
            UserCompanyAccess(user_id=user_id, company_code="cacao"),
        ]
    )
    database.session.commit()
    return user_id


def _cliente(app, user_id: str):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_reportes_visibles_con_permiso_reportes(app, entorno_contable):
    """Sin `access` pero con `reportes` los enlaces aparecen."""
    with app.app_context():
        user_id = _usuario(report=True)
    html = _cliente(app, user_id).get("/cash_management/").get_data(as_text=True)

    assert "Resumen de Saldos Bancarios" in html
    assert "Detalle de Movimiento Bancario" in html


def test_reportes_ocultos_sin_permiso(app, entorno_contable):
    """Sin `reportes` los enlaces no se ofrecen."""
    with app.app_context():
        user_id = _usuario(report=False)
    html = _cliente(app, user_id).get("/cash_management/").get_data(as_text=True)

    assert "Resumen de Saldos Bancarios" not in html
