# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1722: alta y edición de terceros rechazan nombre vacío o solo espacios."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import CompanyParty, Party, database


@pytest.fixture(autouse=True)
def _modulos_de_terceros(app):
    """Activa ventas/compras y restaura su estado previo al terminar."""
    previos: dict[str, tuple[bool, bool | None]] = {}
    with app.app_context():
        from cacao_accounting.database import Modules

        for module in ("sales", "purchases"):
            registro = database.session.execute(database.select(Modules).filter_by(module=module)).scalar_one_or_none()
            previos[module] = (registro is None, None if registro is None else registro.enabled)
            if registro is None:
                database.session.add(Modules(module=module, default=False, enabled=True))
            else:
                registro.enabled = True
        database.session.commit()
    try:
        yield
    finally:
        with app.app_context():
            from cacao_accounting.database import Modules

            for module, (no_existia, enabled) in previos.items():
                registro = database.session.execute(database.select(Modules).filter_by(module=module)).scalar_one_or_none()
                if registro is not None:
                    if no_existia:
                        database.session.delete(registro)
                    else:
                        registro.enabled = enabled
            database.session.commit()


@pytest.mark.parametrize(
    ("path", "role_flag"),
    [
        ("/sales/customer/new", "is_customer"),
        ("/buying/supplier/new", "is_supplier"),
    ],
)
def test_alta_rechaza_nombre_vacio_o_solo_espacios(app, authenticated_client, entorno_contable, path, role_flag):
    """El POST no crea terceros cuando el nombre queda vacío tras strip."""
    del entorno_contable
    with app.app_context():
        antes = database.session.execute(database.select(database.func.count(Party.id))).scalar_one()

    client = authenticated_client("admin")
    for nombre in ("", "   "):
        response = client.post(path, data={"company": "cacao", "name": nombre, "is_active": "on"})
        assert response.status_code == 200
        assert "El nombre del tercero es obligatorio." in response.get_data(as_text=True)

    with app.app_context():
        despues = database.session.execute(database.select(database.func.count(Party.id))).scalar_one()
    assert despues == antes


@pytest.mark.parametrize(
    ("role_flag", "path"),
    [
        ("is_customer", "/sales/customer/{}/edit"),
        ("is_supplier", "/buying/supplier/{}/edit"),
    ],
)
def test_edicion_conserva_nombre_si_el_nuevo_esta_vacio(app, authenticated_client, entorno_contable, role_flag, path):
    """Un nombre en blanco no sobrescribe el nombre persistido."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        kwargs = {"is_customer": role_flag == "is_customer", "is_supplier": role_flag == "is_supplier"}
        tercero = Party(code=f"TER-1722-{sufijo}", name=f"Nombre original {sufijo}", **kwargs)
        database.session.add(tercero)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=tercero.id, is_active=True))
        database.session.commit()
        party_id = tercero.id

    try:
        client = authenticated_client("admin")
        for nombre in ("", "   "):
            response = client.post(
                path.format(party_id),
                data={"company": "cacao", "name": nombre, "is_active": "on"},
            )
            assert response.status_code == 200
            assert "El nombre del tercero es obligatorio." in response.get_data(as_text=True)

        with app.app_context():
            assert database.session.get(Party, party_id).name == f"Nombre original {sufijo}"
    finally:
        with app.app_context():
            database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == party_id))
            database.session.execute(database.delete(Party).where(Party.id == party_id))
            database.session.commit()
