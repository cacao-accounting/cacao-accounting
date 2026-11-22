# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1919: el portal revoca el acceso cuando el tercero o su vínculo se desactiva.

La decisión acordada exige `Party.is_active` y `CompanyParty.is_active` para la
compañía del usuario en cada consulta del portal, incluidos documentos
históricos. La desactivación no modifica la evidencia.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
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
    SalesInvoice,
    User,
    database,
)

FECHA = date(2026, 5, 15)


@pytest.fixture
def portal_revocable():
    """Portal cloud con cliente y proveedor activos en la compañía."""
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
        proveedor = Party(code=f"PRV-{suffix}", name="Proveedor Portal", is_supplier=True, is_active=True)
        database.session.add_all([cliente, proveedor])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor.id, is_active=True),
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
        factura_venta = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="FAC-PORTAL-1919",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("100"),
            total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        factura_compra = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="CMP-PORTAL-1919",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
        )
        database.session.add_all([factura_venta, factura_compra])
        database.session.commit()
        ids = {
            "cliente": cliente.id,
            "proveedor": proveedor.id,
            "cliente_user": f"portal-cliente-{suffix}",
            "proveedor_user": f"portal-proveedor-{suffix}",
            "factura_venta": factura_venta.id,
            "factura_compra": factura_compra.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _client_for(application: Any, user_id: str):
    """Cliente HTTP con sesión del usuario indicado."""
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def _deactivate_party(application: Any, party_id: str) -> None:
    """Desactiva el tercero conservando la evidencia."""
    with application.app_context():
        party = database.session.get(Party, party_id)
        party.is_active = False
        database.session.commit()


def _deactivate_link(application: Any, party_id: str) -> None:
    """Desactiva el vínculo del tercero con la compañía."""
    with application.app_context():
        link = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=party_id)
        ).scalar_one()
        link.is_active = False
        database.session.commit()


def test_portal_cliente_activo_consulta_su_factura(portal_revocable):
    """Con tercero y vínculo activos el cliente ve su dashboard y su factura."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])

    assert client.get("/portal/customer").status_code == 200
    detail = client.get(f"/portal/customer/invoice/{ids['factura_venta']}")
    assert detail.status_code == 200
    assert "FAC-PORTAL-1919" in detail.get_data(as_text=True)


def test_portal_cliente_revocado_por_tercero_inactivo(portal_revocable):
    """Desactivar el tercero revoca dashboard y documento histórico."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])
    _deactivate_party(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_portal_cliente_revocado_por_vinculo_inactivo(portal_revocable):
    """Desactivar el vínculo con la compañía también revoca el acceso."""
    application, ids = portal_revocable
    client = _client_for(application, ids["cliente_user"])
    _deactivate_link(application, ids["cliente"])

    assert client.get("/portal/customer").status_code == 403
    assert client.get(f"/portal/customer/invoice/{ids['factura_venta']}").status_code == 403


def test_portal_proveedor_revocado_por_tercero_inactivo(portal_revocable):
    """El proveedor inactivo pierde el acceso a su dashboard y documento."""
    application, ids = portal_revocable
    client = _client_for(application, ids["proveedor_user"])
    assert client.get("/portal/supplier").status_code == 200
    _deactivate_party(application, ids["proveedor"])

    assert client.get("/portal/supplier").status_code == 403
    assert client.get(f"/portal/supplier/invoice/{ids['factura_compra']}").status_code == 403


def test_portal_conserva_la_evidencia_tras_la_revocacion(portal_revocable):
    """La revocación no elimina ni modifica las facturas del tercero."""
    application, ids = portal_revocable
    _deactivate_party(application, ids["cliente"])

    with application.app_context():
        factura = database.session.get(SalesInvoice, ids["factura_venta"])
        assert factura is not None
        assert factura.docstatus == 1
        assert factura.document_no == "FAC-PORTAL-1919"
