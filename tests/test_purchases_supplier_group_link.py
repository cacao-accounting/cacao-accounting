# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2144: Compras no ofrece un enlace que exige administración global.

`admin.lista_grupos_terceros` requiere administrador del sistema. Un usuario
con `purchases.configurar` pero sin rol admin no debe ver el enlace habilitado
ni un badge «Todo ok».
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

SUPPLIER_GROUPS_LINK = "/settings/party-groups?group_type=supplier"


def test_purchases_hides_supplier_groups_link_from_non_admin_configurator(app, entorno_contable):
    """El permiso de configuración de Compras no simula acceso de administrador."""
    suffix = uuid4().hex[:6]
    user_id = f"purchases-config-{suffix}"
    with app.app_context():
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        role = Roles(name=f"purchases-config-{suffix}", note="Configura Compras")
        database.session.add(role)
        database.session.flush()
        user = User(
            id=user_id,
            user=user_id,
            name="Configurador de Compras",
            password=proteger_passwd("ConfigPurchases-2026!"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True, setup=True),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()
        auth_version = 0

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get("/buying/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert SUPPLIER_GROUPS_LINK not in html
    assert "Tipos de Proveedor" not in html
