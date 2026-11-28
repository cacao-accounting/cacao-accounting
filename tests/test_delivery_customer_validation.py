# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2116: la remisión manual valida el cliente en servidor."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import CompanyParty, DeliveryNote, DeliveryNoteItem, Party, database

FECHA = date(2026, 5, 15)
MENSAJE_CLIENTE = "no está habilitado como cliente"
MENSAJE_COMPANIA = "no está habilitado para la compañía"


def _tercero(app, *, customer: bool, active: bool, membership: bool) -> str:
    suffix = uuid4().hex[:8]
    with app.app_context():
        party = Party(
            code=f"REM-{suffix}",
            name=f"Tercero remisión {suffix}",
            is_customer=customer,
            is_supplier=not customer,
            is_active=active,
        )
        database.session.add(party)
        database.session.flush()
        if membership:
            database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
        database.session.commit()
        return str(party.id)


def _form(customer_id: str, suffix: str) -> dict[str, str]:
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": customer_id,
        "remarks": f"REM-{suffix}",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
        "from_warehouse": "BOD01",
    }


@pytest.mark.parametrize(
    ("customer", "active", "membership", "mensaje"),
    [
        (False, True, True, MENSAJE_CLIENTE),
        (True, False, True, MENSAJE_CLIENTE),
        (True, True, False, MENSAJE_COMPANIA),
    ],
    ids=["proveedor", "inactivo", "sin_vinculo"],
)
def test_alta_rechaza_clientes_invalidos(app, authenticated_client, entorno_contable, customer, active, membership, mensaje):
    """Proveedor, cliente inactivo o sin vínculo no crean la remisión."""
    suffix = uuid4().hex[:8]
    customer_id = _tercero(app, customer=customer, active=active, membership=membership)
    respuesta = authenticated_client().post("/sales/delivery-note/new", data=_form(customer_id, suffix))

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(DeliveryNote).filter_by(remarks=f"REM-{suffix}")).first() is None


def test_alta_acepta_cliente_valido(app, authenticated_client, entorno_contable):
    """Un cliente activo con vínculo vigente crea la remisión."""
    suffix = uuid4().hex[:8]
    customer_id = _tercero(app, customer=True, active=True, membership=True)
    respuesta = authenticated_client().post("/sales/delivery-note/new", data=_form(customer_id, suffix))

    assert respuesta.status_code == 302
    with app.app_context():
        assert database.session.execute(database.select(DeliveryNote).filter_by(remarks=f"REM-{suffix}")).first() is not None


def test_edicion_rechaza_cambiar_a_proveedor(app, authenticated_client, entorno_contable):
    """La edición conserva el cliente original si se intenta poner un proveedor."""
    suffix = uuid4().hex[:8]
    cliente_id = _tercero(app, customer=True, active=True, membership=True)
    proveedor_id = _tercero(app, customer=False, active=True, membership=True)
    with app.app_context():
        cliente = database.session.get(Party, cliente_id)
        nota = DeliveryNote(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=f"EDIT-{suffix}",
        )
        database.session.add(nota)
        database.session.commit()
        note_id = nota.id

    datos = _form(proveedor_id, suffix)
    datos.pop("from_warehouse")
    datos["warehouse_0"] = "BOD01"
    respuesta = authenticated_client().post(f"/sales/delivery-note/{note_id}/edit", data=datos)

    assert respuesta.status_code == 302
    with app.app_context():
        nota = database.session.get(DeliveryNote, note_id)
        assert nota.customer_id == cliente_id


def _nota_origen(app, customer_id: str, suffix: str) -> str:
    """Crea una nota de entrega aprobada que sirve como origen de devolución."""
    with app.app_context():
        cliente = database.session.get(Party, customer_id)
        nota = DeliveryNote(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=f"ORIGEN-{suffix}",
        )
        database.session.add(nota)
        database.session.commit()
        return str(nota.id)


def _borrador_devolucion(app, customer_id: str, source_id: str, suffix: str) -> str:
    """Crea un borrador de devolución con una línea válida."""
    with app.app_context():
        cliente = database.session.get(Party, customer_id)
        nota = DeliveryNote(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            is_return=True,
            reversal_of=source_id,
            remarks=f"DEV-{suffix}",
        )
        database.session.add(nota)
        database.session.flush()
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=nota.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("10"),
                warehouse="BOD01",
            )
        )
        database.session.commit()
        return str(nota.id)


def test_edicion_rechaza_otro_cliente_valido_del_origen(app, authenticated_client, entorno_contable):
    """Una devolución no puede cambiar a otro cliente aunque sea válido."""
    suffix = uuid4().hex[:8]
    cliente_origen = _tercero(app, customer=True, active=True, membership=True)
    cliente_alterno = _tercero(app, customer=True, active=True, membership=True)
    source_id = _nota_origen(app, cliente_origen, suffix)
    note_id = _borrador_devolucion(app, cliente_origen, source_id, suffix)

    datos = _form(cliente_alterno, suffix)
    datos.pop("from_warehouse")
    datos["warehouse_0"] = "BOD01"
    respuesta = authenticated_client().post(f"/sales/delivery-note/{note_id}/edit", data=datos)

    assert respuesta.status_code == 302
    with app.app_context():
        nota = database.session.get(DeliveryNote, note_id)
        assert nota.customer_id == cliente_origen


def test_submit_rechaza_cliente_divergente_del_origen(app, authenticated_client, entorno_contable):
    """El submit vuelve a comparar el cliente con la nota de devolución."""
    suffix = uuid4().hex[:8]
    cliente_origen = _tercero(app, customer=True, active=True, membership=True)
    cliente_alterno = _tercero(app, customer=True, active=True, membership=True)
    source_id = _nota_origen(app, cliente_origen, suffix)
    note_id = _borrador_devolucion(app, cliente_alterno, source_id, suffix)

    respuesta = authenticated_client().post(f"/sales/delivery-note/{note_id}/submit", follow_redirects=True)

    assert respuesta.status_code == 200
    assert "debe coincidir con el documento origen" in respuesta.get_data(as_text=True)
    with app.app_context():
        nota = database.session.get(DeliveryNote, note_id)
        assert nota.docstatus == 0
