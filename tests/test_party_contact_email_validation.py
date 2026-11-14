# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""La validación del correo de contactos de terceros falla de forma controlada.

Escenario (#2202): un usuario captura un correo con formato inválido al crear
o editar un contacto de cliente o proveedor. El sistema debe responder con una
redirección controlada (nunca 500), mostrar el mensaje de validación y no
persistir el contacto ni alterar el correo previamente guardado.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import CompanyParty, Contact, Party, PartyContact, database

MENSAJE_EMAIL_INVALIDO = "El correo electrónico del contacto no es válido."


def _crear_tercero_con_vinculo(**roles: bool) -> Party:
    """Crea un tercero con código único y vínculo activo en la compañía cacao."""
    suffix = uuid4().hex[:10]
    party = Party(
        code=f"QA-C-{suffix}",
        name=f"Tercero de contacto QA {suffix}",
        is_customer=roles.get("customer", False),
        is_supplier=roles.get("supplier", False),
    )
    database.session.add(party)
    database.session.flush()
    database.session.add(CompanyParty(party_id=party.id, company="cacao", is_active=True))
    database.session.commit()
    return party


def _contactos_del_tercero(party_id: str) -> list[Contact]:
    """Devuelve los contactos vinculados al tercero."""
    return (
        database.session.execute(
            select(Contact).join(PartyContact, PartyContact.contact_id == Contact.id).where(PartyContact.party_id == party_id)
        )
        .scalars()
        .all()
    )


@pytest.fixture
def cliente_qa(app):
    """Cliente aislado por identificador para la duración del worker pytest."""
    with app.app_context():
        yield _crear_tercero_con_vinculo(customer=True)


@pytest.fixture
def proveedor_qa(app):
    """Proveedor aislado por identificador para la duración del worker pytest."""
    with app.app_context():
        yield _crear_tercero_con_vinculo(supplier=True)


def test_correo_invalido_en_cliente_responde_controlado_y_no_persiste(app, authenticated_client, cliente_qa):
    """El POST con correo inválido no es un 500 y no crea la fila de contacto."""
    assert cliente_qa.is_customer is True
    marcador = f"QA-{uuid4().hex[:8]}"

    client = authenticated_client()
    response = client.post(
        f"/sales/customer/{cliente_qa.id}/contacts",
        data={"first_name": f"Contacto {marcador}", "email": "not-an-email"},
    )

    assert response.status_code == 302
    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert MENSAJE_EMAIL_INVALIDO in detail.get_data(as_text=True)

    with app.app_context():
        assert _contactos_del_tercero(cliente_qa.id) == []


def test_correo_vacio_es_aceptado_en_cliente(app, authenticated_client, cliente_qa):
    """Un contacto sin correo es válido y se crea con email nulo."""
    marcador = f"QA-{uuid4().hex[:8]}"

    client = authenticated_client()
    response = client.post(
        f"/sales/customer/{cliente_qa.id}/contacts",
        data={"first_name": f"Sin correo {marcador}", "email": ""},
    )

    assert response.status_code == 302
    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "Contacto agregado correctamente." in detail.get_data(as_text=True)

    with app.app_context():
        contactos = _contactos_del_tercero(cliente_qa.id)
        assert len(contactos) == 1
        assert contactos[0].email is None
        assert contactos[0].is_active is True


def test_correo_valido_persiste_en_cliente(app, authenticated_client, cliente_qa):
    """Un correo con formato válido se guarda normalizado."""
    marcador = f"QA-{uuid4().hex[:8]}"
    email = f"contacto.{marcador}@example.com"

    response = authenticated_client().post(
        f"/sales/customer/{cliente_qa.id}/contacts",
        data={"first_name": f"Válido {marcador}", "email": email},
    )

    assert response.status_code == 302
    with app.app_context():
        contactos = _contactos_del_tercero(cliente_qa.id)
        assert len(contactos) == 1
        assert contactos[0].email == email


def test_correo_invalido_en_proveedor_responde_controlado_y_no_persiste(app, authenticated_client, proveedor_qa):
    """La ruta de proveedor también rechaza el correo inválido sin 500."""
    assert proveedor_qa.is_supplier is True
    marcador = f"QA-{uuid4().hex[:8]}"

    client = authenticated_client()
    response = client.post(
        f"/buying/supplier/{proveedor_qa.id}/contacts",
        data={"first_name": f"Contacto proveedor {marcador}", "email": "not-an-email"},
    )

    assert response.status_code == 302
    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert MENSAJE_EMAIL_INVALIDO in detail.get_data(as_text=True)

    with app.app_context():
        assert _contactos_del_tercero(proveedor_qa.id) == []


def test_edicion_con_correo_invalido_conserva_el_correo_previo(app, authenticated_client, cliente_qa):
    """Rechazar la edición no debe borrar ni cambiar el correo ya guardado."""
    marcador = f"QA-{uuid4().hex[:8]}"
    email_original = f"original.{marcador}@example.com"
    client = authenticated_client()
    alta = client.post(
        f"/sales/customer/{cliente_qa.id}/contacts",
        data={"first_name": f"Editable {marcador}", "email": email_original},
    )
    assert alta.status_code == 302

    with app.app_context():
        vinculo = database.session.execute(select(PartyContact).filter_by(party_id=cliente_qa.id)).scalar_one()
        link_id = vinculo.id

    edicion = client.post(
        f"/sales/customer/{cliente_qa.id}/contacts/{link_id}/edit",
        data={"first_name": f"Editable {marcador}", "email": "not-an-email"},
    )

    assert edicion.status_code == 302
    detail = client.get(edicion.headers["Location"])
    assert detail.status_code == 200
    assert MENSAJE_EMAIL_INVALIDO in detail.get_data(as_text=True)

    with app.app_context():
        contactos = _contactos_del_tercero(cliente_qa.id)
        assert len(contactos) == 1
        assert contactos[0].email == email_original
