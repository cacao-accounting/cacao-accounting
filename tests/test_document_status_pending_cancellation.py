# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Estado visible de anulaciones pendientes en documentos aprobados.

Escenario de negocio: una factura de venta aprobada recibe una solicitud de
anulación que queda en aprobación. El badge debe mostrar «Anulación Pendiente»
mientras esa solicitud siga viva; el documento no debe seguir apareciendo como
simplemente «Abierto».
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
    Entity,
    Modules,
    SalesInvoice,
    SalesQuotation,
    User,
    database,
)
from cacao_accounting.document_flow.status import calculate_document_status

FECHA = date(2026, 10, 20)


@pytest.fixture
def factura_aprobada():
    """Factura de venta aprobada lista para solicitar su anulación."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-CANCEL-1",
            customer_name="Cliente Cacao",
            transaction_currency="NIO",
            grand_total=Decimal("100"),
            total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id
    yield application, factura_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _solicitud(application, factura_id: str, document_type: str, status: str) -> None:
    with application.app_context():
        database.session.add(
            ApprovalRequest(
                document_type=document_type,
                document_id=factura_id,
                company_id="cacao",
                requested_by="admin",
                status=status,
            )
        )
        database.session.commit()


def test_solicitud_de_anulacion_muestra_anulacion_pendiente(factura_aprobada):
    """La solicitud cancel_<doctype> gobierna el badge de anulación."""
    application, factura_id = factura_aprobada
    _solicitud(application, factura_id, "cancel_sales_invoice", "Pending Cancellation")

    with application.app_context():
        estado = calculate_document_status("sales_invoice", factura_id)

    assert estado.code == "pending_cancellation"
    assert estado.full_label == "Anulación Pendiente"


def test_solicitud_de_aprobacion_sigue_mostrando_pendiente_aprobacion(factura_aprobada):
    """Control de regresión: el tipo base conserva su estado de aprobación."""
    application, factura_id = factura_aprobada
    _solicitud(application, factura_id, "sales_invoice", "Pending Approval")

    with application.app_context():
        estado = calculate_document_status("sales_invoice", factura_id)

    assert estado.code == "pending_approval"
    assert estado.full_label == "Pendiente de Aprobación"


CONTRASENA = "estado-cotizacion-2026"


@pytest.fixture
def cotizacion_pendiente():
    """Cotización aprobada con solicitud de anulación pendiente y usuario admin."""
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
                Modules(module="sales", default=False, enabled=True),
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
        cotizacion = SalesQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SQ-CANCEL-1",
            customer_name="Cliente Cacao",
            transaction_currency="NIO",
            grand_total=Decimal("100"),
            total=Decimal("100"),
        )
        database.session.add(cotizacion)
        database.session.flush()
        database.session.add(
            ApprovalRequest(
                document_type="cancel_sales_quotation",
                document_id=cotizacion.id,
                company_id="cacao",
                requested_by="admin",
                status="Pending Cancellation",
            )
        )
        database.session.commit()
        cotizacion_id = cotizacion.id
    yield application, cotizacion_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_detalle_de_cotizacion_muestra_anulacion_pendiente(cotizacion_pendiente):
    """El detalle de cotización consume el estado calculado, no el docstatus crudo."""
    application, cotizacion_id = cotizacion_pendiente
    client = application.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.get(f"/sales/quotation/{cotizacion_id}")

    assert response.status_code == 200
    assert "Anulación Pendiente" in response.get_data(as_text=True)
