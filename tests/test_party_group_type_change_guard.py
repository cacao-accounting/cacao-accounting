# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1724: no se cambia el tipo de un grupo con terceros incompatibles.

La política aprobada es bloquear el cambio sin migrar ni reclasificar terceros.
El administrador debe reasignar las relaciones afectadas antes de cambiar el
tipo del grupo.
"""

from __future__ import annotations

import sys
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import Modules, Party, PartyGroup, User, database


@pytest.fixture
def admin_module_snapshot(app):
    """Verifica al final de la prueba que el módulo admin conserva su estado."""
    with app.app_context():
        previous = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one()
        previous_enabled = previous.enabled
    yield
    with app.app_context():
        current = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one()
        assert current.enabled == previous_enabled


@pytest.fixture(name="party_group_admin")
def party_group_admin_fixture(app, admin_module_snapshot):
    """Habilita administración y restaura su estado previo al terminar la prueba."""
    del admin_module_snapshot
    module_created = False
    previous_enabled = None
    try:
        with app.app_context():
            admin_module = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one_or_none()
            module_created = admin_module is None
            previous_enabled = None if module_created else admin_module.enabled
            if module_created:
                database.session.add(Modules(module="admin", default=False, enabled=True))
            else:
                admin_module.enabled = True
            database.session.commit()
            admin_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        yield admin_id
    finally:
        with app.app_context():
            database.session.rollback()
            current = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if module_created:
                if current is not None:
                    database.session.delete(current)
            elif current is not None:
                current.enabled = previous_enabled
            database.session.commit()


def test_fixture_restaura_modulo_admin_si_falla_la_carga_del_usuario(app, admin_module_snapshot, monkeypatch):
    """#2284: el módulo admin vuelve a su estado si falla el setup posterior."""
    with app.app_context():
        previous_enabled = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one().enabled
    real_select = select
    calls = {"count": 0}

    def failing_select(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise RuntimeError("fallo de setup")
        return real_select(*args, **kwargs)

    monkeypatch.setattr(sys.modules[__name__], "select", failing_select)
    generator = party_group_admin_fixture.__wrapped__(app, admin_module_snapshot)
    with pytest.raises(RuntimeError, match="fallo de setup"):
        next(generator)

    with app.app_context():
        assert (
            database.session.execute(real_select(Modules).filter_by(module="admin")).scalar_one().enabled == previous_enabled
        )


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
