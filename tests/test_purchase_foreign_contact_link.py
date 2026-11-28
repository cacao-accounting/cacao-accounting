# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1978: desactivar un contacto o dirección ajena no produce 500."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Address,
    CompanyParty,
    Contact,
    Party,
    PartyAddress,
    PartyContact,
    database,
)

pytestmark = pytest.mark.usefixtures("entorno_contable")


@pytest.mark.parametrize(
    ("rol", "ruta_base", "tipo"),
    [
        ("supplier", "/buying/supplier", "contacts"),
        ("supplier", "/buying/supplier", "addresses"),
        ("customer", "/sales/customer", "contacts"),
        ("customer", "/sales/customer", "addresses"),
    ],
)
def test_vinculo_ajeno_responde_404_sin_mutar(app, authenticated_client, rol, ruta_base, tipo):
    """Un vínculo que pertenece a otro tercero no se desactiva ni responde 500."""
    sufijo = uuid4().hex[:6]
    es_proveedor = rol == "supplier"
    with app.app_context():
        dueno = Party(
            code=f"OWN-{sufijo}",
            name="Tercero dueño",
            is_supplier=es_proveedor,
            is_customer=not es_proveedor,
            is_active=True,
        )
        ajeno = Party(
            code=f"FRN-{sufijo}",
            name="Tercero ajeno",
            is_supplier=es_proveedor,
            is_customer=not es_proveedor,
            is_active=True,
        )
        database.session.add_all([dueno, ajeno])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=dueno.id, is_active=True),
                CompanyParty(company="cacao", party_id=ajeno.id, is_active=True),
            ]
        )
        contacto = Contact(first_name="Contacto dueño", email=f"{sufijo}@example.com")
        direccion = Address(address_line1=f"Calle QA {sufijo}", city="Managua")
        database.session.add_all([contacto, direccion])
        database.session.flush()
        vinculo_contacto = PartyContact(party_id=dueno.id, contact_id=contacto.id)
        vinculo_direccion = PartyAddress(party_id=dueno.id, address_id=direccion.id)
        database.session.add_all([vinculo_contacto, vinculo_direccion])
        database.session.commit()
        ids = {
            "dueno": dueno.id,
            "ajeno": ajeno.id,
            "contacto": contacto.id,
            "direccion": direccion.id,
            "vinculo_contacto": vinculo_contacto.id,
            "vinculo_direccion": vinculo_direccion.id,
        }

    try:
        client = authenticated_client("admin")
        enlace = ids["vinculo_contacto"] if tipo == "contacts" else ids["vinculo_direccion"]
        respuesta = client.post(f"{ruta_base}/{ids['ajeno']}/{tipo}/{enlace}/deactivate")

        assert respuesta.status_code == 404
        with app.app_context():
            assert database.session.get(Contact, ids["contacto"]).is_active is True
            assert database.session.get(Address, ids["direccion"]).is_active is True
            assert database.session.get(PartyContact, ids["vinculo_contacto"]).party_id == ids["dueno"]
            assert database.session.get(PartyAddress, ids["vinculo_direccion"]).party_id == ids["dueno"]
    finally:
        with app.app_context():
            database.session.delete(database.session.get(PartyContact, ids["vinculo_contacto"]))
            database.session.delete(database.session.get(PartyAddress, ids["vinculo_direccion"]))
            database.session.delete(database.session.get(Contact, ids["contacto"]))
            database.session.delete(database.session.get(Address, ids["direccion"]))
            for party_id in (ids["ajeno"], ids["dueno"]):
                database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == party_id))
                database.session.delete(database.session.get(Party, party_id))
            database.session.commit()
