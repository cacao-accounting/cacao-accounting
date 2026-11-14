# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Verifica el filtro de período para un usuario con acceso de Inventario."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import Roles, RolesAccess, RolesUser, User, UserCompanyAccess, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


def test_entregas_muestra_periodos_de_compania_autorizada(entorno_contable):
    """El picker de entregas incluye la compañía accesible por Inventario."""
    app = entorno_contable.app
    with app.app_context():
        user = User(
            user=f"inventory-reader-{uuid4().hex}",
            name="Consulta de Inventario",
            password=proteger_passwd("inventory-reader-test"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        role = Roles(name=f"inventory-reader-{uuid4().hex}", note="Consulta de Inventario")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=obtener_id_modulo_por_nombre("inventory"),
                    access=True,
                    view=True,
                ),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="cacao"),
            ]
        )
        database.session.commit()
        user_id, auth_version = user.id, user.auth_version

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get("/sales/delivery-note/list?company=cacao")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="list-company"' in html
    assert 'id="list-period-from"' in html
    assert 'id="list-period-to"' in html
    assert 'initialValue: "cacao"' in html
    assert 'initialLabel: "Mayo 2026"' in html
    assert 'initialValue: "alpha"' not in html
