# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2052: un usuario de Inventario completa los selectores de la remisión."""

from __future__ import annotations

from uuid import uuid4


def test_inventario_consulta_party_y_secuencia(app, entorno_contable):
    """El CTA y el POST aceptan Inventario; los selectores deben permitirlo."""
    from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser, User, UserCompanyAccess, database

    suffix = uuid4().hex[:6]
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="inventory")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="inventory", default=False, enabled=True)
            database.session.add(modulo)
            database.session.flush()
        role = Roles(name=f"inventario-{suffix}", note="Inventario")
        user_id = f"inventario-{suffix}"
        database.session.add_all(
            [
                User(id=user_id, user=user_id, name="Inventario", password=b"unused", active=True, company="cacao"),
                role,
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=modulo.id, access=True, view=True, create=True),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True

    for doctype in ("party", "naming_series"):
        response = client.get("/api/search-select", query_string={"doctype": doctype, "company": "cacao"})
        assert response.status_code == 200, (doctype, response.get_data(as_text=True))

    contable = client.get("/api/search-select", query_string={"doctype": "account", "company": "cacao"})
    assert contable.status_code == 403
