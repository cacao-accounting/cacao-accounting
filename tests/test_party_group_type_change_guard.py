# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1724: no se cambia el tipo de un grupo con terceros incompatibles.

La política aprobada es bloquear el cambio sin migrar ni reclasificar terceros.
El administrador debe reasignar las relaciones afectadas antes de cambiar el
tipo del grupo.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import Modules, Party, PartyGroup, User, database


@pytest.fixture(name="party_group_admin")
def party_group_admin_fixture(app):
    """Habilita administración y devuelve el id del administrador del sistema."""
    with app.app_context():
        admin_module = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if admin_module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            admin_module.enabled = True
        database.session.commit()
        return database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()


def _admin_client(app, user_id: str):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _crear_grupo_y_tercero(app, *, group_type: str, is_customer: bool, is_supplier: bool):
    sufijo = uuid4().hex[:8]
    with app.app_context():
        grupo = PartyGroup(
            group_type=group_type,
            name=f"Grupo guard {sufijo}",
            description="original",
            is_active=True,
        )
        database.session.add(grupo)
        database.session.flush()
        tercero = Party(
            code=f"TER-GUARD-{sufijo}",
            name="Tercero guard",
            is_customer=is_customer,
            is_supplier=is_supplier,
            party_group_id=grupo.id,
        )
        database.session.add(tercero)
        database.session.commit()
        return grupo.id, grupo.name, tercero.id


def _limpiar(app, group_id: str, party_id: str) -> None:
    with app.app_context():
        database.session.execute(database.delete(Party).where(Party.id == party_id))
        database.session.execute(database.delete(PartyGroup).where(PartyGroup.id == group_id))
        database.session.commit()


@pytest.mark.parametrize(
    ("group_type", "nuevo_tipo", "is_customer", "is_supplier"),
    [
        ("customer", "supplier", True, False),
        ("supplier", "customer", False, True),
    ],
)
def test_bloquea_cambio_con_tercero_incompatible(app, party_group_admin, group_type, nuevo_tipo, is_customer, is_supplier):
    """El grupo y sus datos quedan intactos cuando un tercero no tiene el nuevo rol."""
    client = _admin_client(app, party_group_admin)
    group_id, group_name, party_id = _crear_grupo_y_tercero(
        app, group_type=group_type, is_customer=is_customer, is_supplier=is_supplier
    )
    try:
        response = client.post(
            f"/settings/party-groups/{group_id}/edit",
            data={"group_type": nuevo_tipo, "name": "Nombre mutado", "description": "mutado", "is_active": "on"},
        )

        assert response.status_code == 200
        assert "Reasigne esas relaciones primero." in response.get_data(as_text=True)
        with app.app_context():
            group = database.session.get(PartyGroup, group_id)
            assert (group.group_type, group.name, group.description, group.is_active) == (
                group_type,
                group_name,
                "original",
                True,
            )
    finally:
        _limpiar(app, group_id, party_id)


def test_bloquea_cambio_con_tercero_dual(app, party_group_admin):
    """Un tercero con ambos roles no puede quedar en un grupo de un solo tipo."""
    client = _admin_client(app, party_group_admin)
    group_id, group_name, party_id = _crear_grupo_y_tercero(app, group_type="customer", is_customer=True, is_supplier=True)
    try:
        response = client.post(
            f"/settings/party-groups/{group_id}/edit",
            data={"group_type": "supplier", "name": "Grupo no convertible", "is_active": "on"},
        )

        assert response.status_code == 200
        assert "Reasigne esas relaciones primero." in response.get_data(as_text=True)
        with app.app_context():
            group = database.session.get(PartyGroup, group_id)
            assert group.group_type == "customer"
            assert group.name == group_name
    finally:
        _limpiar(app, group_id, party_id)


def test_renombrar_sin_cambiar_tipo_no_consulta_dependencias(app, party_group_admin):
    """Mantener el tipo permite actualizar nombre y descripción con hijos asignados."""
    client = _admin_client(app, party_group_admin)
    group_id, _, party_id = _crear_grupo_y_tercero(app, group_type="customer", is_customer=True, is_supplier=False)
    try:
        response = client.post(
            f"/settings/party-groups/{group_id}/edit",
            data={"group_type": "customer", "name": "Grupo renombrado", "description": "nuevo", "is_active": "on"},
        )

        assert response.status_code == 302
        with app.app_context():
            group = database.session.get(PartyGroup, group_id)
            assert (group.group_type, group.name, group.description) == ("customer", "Grupo renombrado", "nuevo")
    finally:
        _limpiar(app, group_id, party_id)
