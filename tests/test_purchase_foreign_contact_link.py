# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1978: desactivar un contacto ajeno no produce 500."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Contact, Party, PartyContact, database


def test_contacto_de_otro_proveedor_responde_404(app, authenticated_client, entorno_contable):
    """El vínculo debe pertenecer al proveedor de la ruta."""
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
        database.session.add(vinculo)
        database.session.commit()
        ajeno, contacto_id = dos.id, vinculo.id

    respuesta = authenticated_client("admin").post(f"/purchases/supplier/{ajeno}/contacts/{contacto_id}/deactivate")

    assert respuesta.status_code == 404
