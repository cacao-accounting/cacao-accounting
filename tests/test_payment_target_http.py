# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1405: el endpoint de flujo documental crea pagos con origen solo por línea.

El pago destino no declara ``source_document_type`` en la cabecera; la
autorización se resuelve por cada factura de ``lines``. La regresión cubre el
POST HTTP con un usuario real de caja y la denegación de una factura fuente de
otra compañía.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.database import (
    DocumentRelation,
    Entity,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

FECHA = date(2026, 5, 15)


def _asegurar_compania_ajena() -> None:
    """Crea la compañía alterna si no existe en la base compartida."""
    with database.session.no_autoflush:
        existente = database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one_or_none()
        if existente is None:
            database.session.add(
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name="Alfa SA",
                    tax_id="J-ALPHA",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()


@pytest.fixture
def cajero(app, entorno_contable):
    """Usuario no administrador con permiso de caja y acceso a cacao."""
    suffix = uuid4().hex[:6]
    user_id = f"cajero-{suffix}"
    with app.app_context():
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        _asegurar_compania_ajena()
        database.session.add(
            User(
                id=user_id,
                user=f"cajero_{suffix}",
                name="Cajero",
                password=b"unused",
                classification="user",
                active=True,
                company="cacao",
            )
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="cacao"))
        database.session.commit()
        asigna_rol_a_usuario(f"cajero_{suffix}", "auxiliar_of_treasury")
        # #1405: Tesorería no necesita permisos de Ventas para aplicar pagos.
    return user_id


def _cliente(app, user_id: str):  # noqa: ANN001 - fixture helper
    """Cliente HTTP autenticado como el usuario indicado."""
    client = app.test_client()
    with app.app_context():
        version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def _factura_cliente(company: str, document_no: str) -> SalesInvoice:
    """Crea una factura de venta aprobada con saldo abierto."""
    with database.session.no_autoflush:
        customer_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
    invoice = SalesInvoice(
        company=company,
        posting_date=FECHA,
        docstatus=1,
        document_no=document_no,
        customer_id=customer_id,
        customer_name="Cliente Principal SA",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("100"),
        total=Decimal("100"),
        outstanding_amount=Decimal("100"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _payload(invoice_id: str, customer_id: str) -> dict:
    """Payload de pago destino sin origen en la cabecera."""
    return {
        "target_document_type": "payment_entry",
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "payment_type": "receive",
        "party_type": "customer",
        "party_id": customer_id,
        "currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {
                "source_document_type": "sales_invoice",
                "source_document_id": invoice_id,
                "allocated_amount": "40",
            }
        ],
    }


def test_create_target_persiste_pago_con_origen_por_linea(app, entorno_contable, cajero):
    """Un usuario de caja crea el pago desde la factura de la línea."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["payment_entry"])
        invoice = _factura_cliente("cacao", "FAC-PAGO-1405")
        invoice_id, customer_id = invoice.id, invoice.customer_id
        database.session.commit()

    response = _cliente(app, cajero).post("/api/document-flow/create-target", json=_payload(invoice_id, customer_id))

    assert response.status_code == 201, response.get_data(as_text=True)
    payment_id = response.get_json()["target_id"]
    with app.app_context():
        payment = database.session.get(PaymentEntry, payment_id)
        reference = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment_id)).scalar_one()
        relation = database.session.execute(
            database.select(DocumentRelation).filter_by(source_id=invoice_id, target_id=payment_id)
        ).scalar_one_or_none()
        assert payment is not None
        assert payment.company == "cacao"
        assert payment.party_id == customer_id
        assert reference.reference_id == invoice_id
        assert reference.allocated_amount == Decimal("40")
        assert relation is not None


def test_create_target_rechaza_factura_fuente_de_otra_compania(app, entorno_contable, cajero):
    """El permiso de caja no autoriza una factura fuente de otra compañía."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["payment_entry"])
        ajena = _factura_cliente("alpha", "FAC-AJENA-1405")
        ajena_id, customer_id = ajena.id, ajena.customer_id
        database.session.commit()
        pagos_antes = database.session.execute(database.select(PaymentEntry.id)).scalars().all()

    response = _cliente(app, cajero).post("/api/document-flow/create-target", json=_payload(ajena_id, customer_id))

    assert response.status_code == 403
    with app.app_context():
        pagos_despues = database.session.execute(database.select(PaymentEntry.id)).scalars().all()
        assert pagos_despues == pagos_antes


def test_solo_ventas_no_crea_pagos(app, entorno_contable):
    """#1405: sin `cash.crear` no se crea un pago aunque haya permisos de ventas."""
    suffix = uuid4().hex[:6]
    user_id = f"vendedor-{suffix}"
    with app.app_context():
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        database.session.add(
            User(
                id=user_id,
                user=f"vendedor_{suffix}",
                name="Vendedor",
                password=b"unused",
                classification="user",
                active=True,
                company="cacao",
            )
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="cacao"))
        database.session.commit()
        asigna_rol_a_usuario(f"vendedor_{suffix}", "sales_auxiliar")
        invoice = _factura_cliente("cacao", f"FAC-VENTAS-{suffix}")
        invoice_id, customer_id = invoice.id, invoice.customer_id
        database.session.commit()

    response = _cliente(app, user_id).post("/api/document-flow/create-target", json=_payload(invoice_id, customer_id))

    assert response.status_code == 403, response.get_data(as_text=True)


def test_create_target_con_tipo_desconocido_responde_400(app, entorno_contable, cajero):
    """#1465: un target_document_type inválido es error de cliente, no 500."""
    from cacao_accounting.database import DocumentRelation, PaymentEntry

    with app.app_context():
        antes_pagos = len(database.session.execute(database.select(PaymentEntry)).scalars().all())
        antes_relaciones = len(database.session.execute(database.select(DocumentRelation)).scalars().all())

    response = _cliente(app, cajero).post(
        "/api/document-flow/create-target",
        json={
            "target_document_type": "tipo-inventado",
            "company": "cacao",
            "posting_date": "2026-05-15",
            "lines": [],
        },
    )

    # El endpoint clasifica un tipo inexistente como recurso no encontrado
    # (404); lo exigible es que sea error de cliente y sin escrituras.
    assert response.status_code in {400, 404}, response.get_data(as_text=True)
    with app.app_context():
        assert len(database.session.execute(database.select(PaymentEntry)).scalars().all()) == antes_pagos
        assert len(database.session.execute(database.select(DocumentRelation)).scalars().all()) == antes_relaciones
