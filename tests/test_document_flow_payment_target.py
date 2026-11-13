# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alta de pago destino sin documento fuente en la cabecera.

Escenario de negocio: un cobrador autorizado registra un pago aplicado a una
factura de venta. El payload identifica la factura en la línea de conciliación,
no en la cabecera; el endpoint no debe confundir esa ausencia con un documento
inexistente ni perder la autorización de la factura origen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    Modules,
    Currency,
    PaymentEntry,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_flow.service import create_target_document

CONTRASENA = "pago-destino-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def pagos_cloud():
    """Compañía cacao con una factura de venta aprobada y un cobrador."""
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
        database.session.add(Currency(code="NIO", name="Córdoba", active=True, default=True))
        database.session.commit()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="otra",
                    name="Otra compañía",
                    company_name="Otra SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="cobrador",
                    user="cobrador",
                    name="Cobrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="cobrador", company_code="cacao"),
                SalesInvoice(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="INV-COBRO-1",
                    customer_name="Cliente Cacao",
                    transaction_currency="NIO",
                    grand_total=Decimal("100"),
                    total=Decimal("100"),
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("cobrador", "sales_auxiliar")
        asigna_rol_a_usuario("cobrador", "head_of_treasury")
        database.session.commit()
        factura_id = database.session.execute(database.select(SalesInvoice)).scalar_one().id
    yield application, factura_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "cobrador", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _payload(factura_id: str) -> dict:
    return {
        "target_document_type": "payment_entry",
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "payment_type": "receive",
        "party_type": "customer",
        "currency": "NIO",
        "lines": [
            {
                "source_document_type": "sales_invoice",
                "source_document_id": factura_id,
                "qty": 40,
            }
        ],
    }


def test_pago_destino_usa_la_factura_de_la_linea(pagos_cloud):
    """La cabecera sin origen no debe responder 404 si la línea trae la factura."""
    application, factura_id = pagos_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.post("/api/document-flow/create-target", json=_payload(factura_id))

    assert response.status_code == 201
    datos = response.get_json()
    assert datos["target_type"] == "payment_entry"
    with application.app_context():
        pago = database.session.get(PaymentEntry, datos["target_id"])
        assert pago is not None
        assert Decimal(str(pago.received_amount)) == Decimal("40")


def test_pago_destino_respeta_commit_diferido_y_rollback(pagos_cloud):
    """El servicio llamador debe poder revertir el pago antes de confirmarlo."""
    application, factura_id = pagos_cloud

    with application.app_context():
        result = create_target_document(_payload(factura_id), commit=False)
        payment_id = result["target_id"]

        database.session.rollback()

        assert database.session.get(PaymentEntry, payment_id) is None


def test_pago_destino_rechaza_una_factura_ajena(pagos_cloud):
    """Aunque la cabecera no traiga origen, la factura de la línea se autoriza."""
    application, factura_id = pagos_cloud
    with application.app_context():
        factura_ajena = SalesInvoice(
            company="otra",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-AJENA-1",
            customer_name="Cliente Ajeno",
            transaction_currency="NIO",
            grand_total=Decimal("500"),
            total=Decimal("500"),
        )
        database.session.add(factura_ajena)
        database.session.commit()
        ajena_id = factura_ajena.id

    client = application.test_client()
    _iniciar(client)

    response = client.post("/api/document-flow/create-target", json=_payload(ajena_id))

    assert response.status_code in {403, 409}
    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []


@pytest.mark.parametrize(
    "line_changes, expected_status",
    [
        ({"source_document_type": ""}, 400),
        ({"source_document_id": ""}, 400),
        ({"source_document_type": "sales_order"}, 400),
        ({"source_document_id": "missing-invoice"}, 404),
    ],
)
def test_pago_destino_rechaza_referencias_incompletas_o_invalidas(pagos_cloud, line_changes, expected_status):
    """Una referencia que el servicio no puede resolver no debe saltar el ACL."""
    application, factura_id = pagos_cloud
    client = application.test_client()
    _iniciar(client)
    payload = _payload(factura_id)
    payload["lines"][0].update(line_changes)

    response = client.post("/api/document-flow/create-target", json=payload)

    assert response.status_code == expected_status
    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []


def test_pago_destino_rechaza_factura_ajena_bajo_compania_autorizada(pagos_cloud):
    """El acceso al destino no concede acceso a una factura de otra compañía."""
    application, _ = pagos_cloud
    with application.app_context():
        factura_ajena = SalesInvoice(
            company="otra",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-AJENA-CAMUFLADA",
            customer_name="Cliente Ajeno",
            transaction_currency="NIO",
            grand_total=Decimal("500"),
            total=Decimal("500"),
        )
        database.session.add(factura_ajena)
        database.session.commit()
        ajena_id = factura_ajena.id

    client = application.test_client()
    _iniciar(client)
    payload = _payload(ajena_id)
    payload["company"] = "cacao"

    response = client.post("/api/document-flow/create-target", json=payload)

    assert response.status_code == 403
    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []
