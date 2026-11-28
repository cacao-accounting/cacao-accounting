# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2266: el portal de proveedores pagina más de 100 documentos y preserva el alcance.

La cobertura equivalente del portal de clientes no ejercita las consultas ni la
plantilla propias del proveedor, que filtran por compañía y por tercero.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Party,
    PurchaseInvoice,
    User,
    database,
)

FECHA = date(2026, 5, 15)
TOTAL_FACTURAS = 101


@pytest.fixture(name="portal_proveedor")
def portal_proveedor_fixture():
    """Proveedor con 101 facturas propias y dos facturas ajenas al alcance."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
                Entity(code="otra", name="Otra", company_name="Otra SA", tax_id="J-2", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        proveedor = Party(code=f"PRO-{suffix}", name="Proveedor Portal", is_supplier=True, is_active=True)
        ajeno = Party(code=f"OTR-{suffix}", name="Proveedor Ajeno", is_supplier=True, is_active=True)
        database.session.add_all([proveedor, ajeno])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=proveedor.id, is_active=True),
                CompanyParty(company="cacao", party_id=ajeno.id, is_active=True),
                CompanyParty(company="otra", party_id=proveedor.id, is_active=True),
                User(
                    id=f"portal-proveedor-{suffix}",
                    user=f"portal_proveedor_{suffix}",
                    name="Proveedor Portal",
                    password=b"x",
                    active=True,
                    classification="supplier",
                    party_id=proveedor.id,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()

        def factura(compania: str, proveedor_id: str, numero: str) -> PurchaseInvoice:
            return PurchaseInvoice(
                company=compania,
                posting_date=FECHA,
                docstatus=1,
                document_no=numero,
                document_type="purchase_invoice",
                supplier_id=proveedor_id,
                supplier_name="Proveedor Portal",
                supplier_invoice_no=f"FAC-{numero}",
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
                grand_total=Decimal("10"),
                total=Decimal("10"),
                outstanding_amount=Decimal("10"),
            )

        database.session.add_all(
            [factura("cacao", proveedor.id, f"PRO-{suffix}-{index:03d}") for index in range(TOTAL_FACTURAS)]
        )
        database.session.add(factura("cacao", ajeno.id, f"AJENO-{suffix}"))
        database.session.add(factura("otra", proveedor.id, f"OTRA-{suffix}"))
        database.session.commit()
        user_id = f"portal-proveedor-{suffix}"
        ids = {"proveedor": proveedor.id, "ajeno": ajeno.id}
    yield application, user_id, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente(application, user_id: str):
    """Autentica al proveedor sin seguir la redirección del login."""
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def _ids_factura(body: str) -> set[str]:
    """Extrae los IDs enlazados por el portal de proveedor."""
    return set(re.findall(r"/portal/supplier/(?:invoice|note)/([A-Za-z0-9]+)", body))


def test_dashboard_proveedor_muestra_el_total_real_y_navega(portal_proveedor):
    """El badge usa 101 y la primera página ofrece navegación a la segunda."""
    application, user_id, _ids = portal_proveedor
    response = _cliente(application, user_id).get("/portal/supplier")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ">101<" in body
    assert "/portal/supplier?page=2" in body
    assert "Siguiente" in body


def test_pagina_dos_expone_la_factura_101_del_proveedor(portal_proveedor):
    """La segunda página contiene solo el documento que no cupo en la primera."""
    application, user_id, _ids = portal_proveedor
    client = _cliente(application, user_id)

    primera = client.get("/portal/supplier")
    segunda = client.get("/portal/supplier?page=2")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert len(_ids_factura(primera.get_data(as_text=True))) == 100
    assert len(_ids_factura(segunda.get_data(as_text=True))) == 1
    assert "Página 2 de 2" in segunda.get_data(as_text=True)


def test_paginas_no_se_solapan_y_excluyen_documentos_ajenos(portal_proveedor):
    """La paginación conserva las 101 facturas propias y ninguna ajena."""
    application, user_id, _ids = portal_proveedor
    client = _cliente(application, user_id)

    primera = _ids_factura(client.get("/portal/supplier").get_data(as_text=True))
    segunda = _ids_factura(client.get("/portal/supplier?page=2").get_data(as_text=True))

    assert primera.isdisjoint(segunda)
    assert len(primera | segunda) == TOTAL_FACTURAS
    with application.app_context():
        ajenas = database.session.execute(database.select(PurchaseInvoice.id).filter_by(company="otra")).scalars().all()
        propias_ajenas = (
            database.session.execute(database.select(PurchaseInvoice.id).filter_by(company="cacao", supplier_id=_ids["ajeno"]))
            .scalars()
            .all()
        )
    assert set(ajenas).isdisjoint(primera | segunda)
    assert set(propias_ajenas).isdisjoint(primera | segunda)
