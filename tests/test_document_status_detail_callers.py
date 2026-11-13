# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Badges de detalle que deben consumir el estado calculado.

Escenario de negocio: una solicitud de anulación pendiente debe verse en el
detalle de factura, remisión, movimiento de inventario y pago. Varias
plantillas pasaban ``docstatus`` crudo al macro y solo mostraban «presentado»;
el estado calculado es la fuente común para esos badges.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalRequest,
    Currency,
    DeliveryNote,
    Entity,
    Modules,
    PaymentEntry,
    SalesInvoice,
    StockEntry,
    User,
    database,
)

CONTRASENA = "detalle-estado-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def documentos_pendientes():
    """Documentos aprobados con solicitud de anulación pendiente."""
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
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-DETALLE",
            document_type="sales_invoice",
            customer_name="Cliente Cacao",
            transaction_currency="NIO",
            grand_total=Decimal("100"),
            total=Decimal("100"),
        )
        entrega = DeliveryNote(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="DN-DETALLE",
            customer_name="Cliente Cacao",
        )
        movimiento = StockEntry(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SE-DETALLE",
            purpose="receipt",
        )
        pago = PaymentEntry(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="PAY-DETALLE",
            payment_type="receive",
            transaction_currency="NIO",
            currency="NIO",
            received_amount=Decimal("10"),
        )
        database.session.add_all([factura, entrega, movimiento, pago])
        database.session.flush()
        database.session.add_all(
            [
                ApprovalRequest(
                    document_type=f"cancel_{documento.__tablename__}",
                    document_id=documento.id,
                    company_id="cacao",
                    requested_by="admin",
                    status="Pending Cancellation",
                )
                for documento in (factura, entrega, movimiento, pago)
            ]
        )
        database.session.commit()
        ids = {
            "factura": factura.id,
            "entrega": entrega.id,
            "movimiento": movimiento.id,
            "pago": pago.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "ruta, clave",
    [
        ("/sales/sales-invoice/{id}", "factura"),
        ("/sales/delivery-note/{id}", "entrega"),
        ("/inventory/stock-entry/{id}", "movimiento"),
        ("/cash_management/payment/{id}", "pago"),
    ],
)
def test_detalle_muestra_anulacion_pendiente(documentos_pendientes, ruta, clave):
    """Cada detalle representa la solicitud de anulación vigente."""
    application, ids = documentos_pendientes
    client = application.test_client()
    _iniciar(client)

    response = client.get(ruta.format(id=ids[clave]))

    assert response.status_code == 200
    assert "Anulación Pendiente" in response.get_data(as_text=True)
