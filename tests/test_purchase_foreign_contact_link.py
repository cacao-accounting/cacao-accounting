# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1978: desactivar un contacto ajeno no produce 500."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Address, Contact, Party, PartyAddress, PartyContact, database

pytestmark = pytest.mark.usefixtures("entorno_contable")


def test_contacto_de_otro_proveedor_responde_404(app, authenticated_client):
    """Los vínculos ajenos de contacto/dirección no responden 500 ni se mutan."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uno = Party(code=f"PRV-A-{sufijo}", name="Proveedor A", is_supplier=True, is_active=True)
        dos = Party(code=f"PRV-B-{sufijo}", name="Proveedor B", is_supplier=True, is_active=True)
        database.session.add_all([uno, dos])
        database.session.flush()
        contacto = Contact(first_name="Contacto A", email="a@example.com")
        database.session.add(contacto)
        database.session.flush()
        vinculo = PartyContact(party_id=uno.id, contact_id=contacto.id)
        direccion = Address(address_line1=f"Calle QA {sufijo}", city="Managua")
        database.session.add(direccion)
        database.session.flush()
        vinculo_direccion = PartyAddress(party_id=uno.id, address_id=direccion.id)
        database.session.add_all([vinculo, vinculo_direccion])
        database.session.commit()
        records = {
            "foreign_party": dos.id,
            "owner_party": uno.id,
            "contact": contacto.id,
            "address": direccion.id,
            "contact_link": vinculo.id,
            "address_link": vinculo_direccion.id,
        }

    try:
        client = authenticated_client("admin")
        respuesta = client.post(
            f"/purchases/supplier/{records['foreign_party']}/contacts/{records['contact_link']}/deactivate"
        )
        respuesta_direccion = client.post(
            f"/purchases/supplier/{records['foreign_party']}/addresses/{records['address_link']}/deactivate"
        )

        assert respuesta.status_code == 404
        assert respuesta_direccion.status_code == 404
        with app.app_context():
            assert database.session.get(Contact, records["contact"]).is_active is True
            assert database.session.get(Address, records["address"]).is_active is True
            assert database.session.get(PartyContact, records["contact_link"]).party_id == records["owner_party"]
            assert database.session.get(PartyAddress, records["address_link"]).party_id == records["owner_party"]
    finally:
        with app.app_context():
            database.session.delete(database.session.get(PartyContact, records["contact_link"]))
            database.session.delete(database.session.get(PartyAddress, records["address_link"]))
            database.session.delete(database.session.get(Contact, records["contact"]))
            database.session.delete(database.session.get(Address, records["address"]))
            database.session.delete(database.session.get(Party, records["foreign_party"]))
            database.session.delete(database.session.get(Party, records["owner_party"]))
            database.session.commit()
