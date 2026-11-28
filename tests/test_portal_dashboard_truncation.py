# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1564: el portal distingue el total real de los registros mostrados.

Con más documentos que `PORTAL_PAGE_SIZE`, el dashboard debe mostrar la
cantidad real en el encabezado y avisar que el listado está truncado, en vez
de presentar la página (100) como el total.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import CompanyParty, Currency, Entity, Party, SalesInvoice, User, database

FECHA = date(2026, 5, 15)
TOTAL_FACTURAS = 101


@pytest.fixture
def portal_truncado():
    """Cliente con 101 facturas posteadas (> PORTAL_PAGE_SIZE)."""
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
            ]
        )
        database.session.flush()
        cliente = Party(code=f"CLI-{suffix}", name="Cliente Portal", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                User(
                    id=f"portal-cliente-{suffix}",
                    user=f"portal_cliente_{suffix}",
                    name="Cliente Portal",
                    password=b"x",
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        for index in range(TOTAL_FACTURAS):
            database.session.add(
                SalesInvoice(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no=f"FAC-{suffix}-{index:03d}",
                    document_type="sales_invoice",
                    customer_id=cliente.id,
                    customer_name=cliente.name,
                    transaction_currency="NIO",
                    base_currency="NIO",
                    exchange_rate=Decimal("1"),
                    grand_total=Decimal("10"),
                    total=Decimal("10"),
                    outstanding_amount=Decimal("10"),
                )
            )
        database.session.commit()
        user_id = f"portal-cliente-{suffix}"
    yield application, {"user": user_id}
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _client_for(application, user_id: str):
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def test_dashboard_muestra_el_total_real_y_navega_al_resto(portal_truncado):
    """El badge usa 101 y la página 1 ofrece navegación a la página 2."""
    application, ids = portal_truncado
    response = _client_for(application, ids["user"]).get("/portal/customer")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ">101<" in body
    assert "page=2" in body
    assert "Siguiente" in body
    assert "Mostrando los primeros" not in body


def test_pagina_dos_expone_los_documentos_posteriores(portal_truncado):
    """La segunda página muestra la factura 101 que la página 1 ocultaba."""
    application, ids = portal_truncado
    client = _client_for(application, ids["user"])

    primera = client.get("/portal/customer")
    segunda = client.get("/portal/customer?page=2")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.get_data(as_text=True).count("/portal/customer/invoice/") == 100
    cuerpo_segunda = segunda.get_data(as_text=True)
    assert cuerpo_segunda.count("/portal/customer/invoice/") == 1
    assert "Página 2 de 2" in cuerpo_segunda


def _invoice_ids(body: str) -> set[str]:
    """Extrae los IDs de factura enlazados por el portal."""
    import re

    return set(re.findall(r"/portal/customer/invoice/([A-Za-z0-9]+)", body))


def test_paginas_no_repten_ni_omitan_facturas_con_la_misma_fecha(portal_truncado):
    """El desempate por PK evita solapamientos aunque compartan posting_date."""
    application, ids = portal_truncado
    client = _client_for(application, ids["user"])

    primera = _invoice_ids(client.get("/portal/customer").get_data(as_text=True))
    segunda = _invoice_ids(client.get("/portal/customer?page=2").get_data(as_text=True))

    assert len(primera) == 100
    assert len(segunda) == 1
    assert primera.isdisjoint(segunda)
    assert len(primera | segunda) == TOTAL_FACTURAS
