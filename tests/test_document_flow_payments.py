# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Resumen de pagos alineado al saldo canónico del árbol documental.

Escenario de negocio (issue #975): una empresa cobra una factura de venta y
registra el importe en ``received_amount``, que es donde el flujo de cobros
guarda el efectivo; ``paid_amount`` queda en cero. El nodo del árbol debe
mostrar el importe cobrado y el saldo no aplicado calculado por el servicio
canónico de pagos, no un total de cero.

También cubre el caso multimoneda: la referencia se expresa en la moneda de la
factura y el efectivo aplicado en la moneda del pago. Sumar ambas magnitudes
produce un saldo no aplicado incorrecto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.payment import compute_payment_unallocated_amount
from cacao_accounting.document_flow.tree import get_document_node

FECHA = date(2026, 10, 18)


@pytest.fixture
def cobros_app():
    """Compañía con moneda local NIO y una factura de venta por 100."""
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
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _factura(company: str, total: Decimal, currency: str = "NIO") -> SalesInvoice:
    """Factura de venta posteada con su saldo canónico."""
    factura = SalesInvoice(
        company=company,
        posting_date=FECHA,
        docstatus=1,
        customer_name="Cliente Mostrador",
        transaction_currency=currency,
        total=total,
        grand_total=total,
    )
    database.session.add(factura)
    database.session.flush()
    return factura


def test_cobro_parcial_usa_received_amount_y_saldo_canonico(cobros_app):
    """#975: un cobro con paid_amount=0 muestra el importe recibido, no cero."""
    with cobros_app.app_context():
        factura = _factura("cacao", Decimal("100"))
        cobro = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=FECHA,
            docstatus=1,
            party_type="customer",
            party_name="Cliente Mostrador",
            currency="NIO",
            paid_amount=Decimal("0"),
            received_amount=Decimal("100"),
        )
        database.session.add(cobro)
        database.session.flush()
        database.session.add(
            PaymentReference(
                payment_id=cobro.id,
                reference_type="sales_invoice",
                reference_id=factura.id,
                reference_document_no=factura.document_no,
                company="cacao",
                currency="NIO",
                total_amount=Decimal("100"),
                outstanding_amount=Decimal("100"),
                outstanding_amount_after=Decimal("0"),
                allocated_amount=Decimal("100"),
                payment_currency="NIO",
                payment_amount=Decimal("100"),
            )
        )
        database.session.commit()

        nodo = get_document_node("payment_entry", cobro.id, include_payment_balance=True)
        saldo = compute_payment_unallocated_amount(cobro)

    assert Decimal(nodo["total"]) == Decimal("100")
    assert Decimal(nodo["unallocated_amount"]) == Decimal("0")
    assert saldo == Decimal("0")


def test_pago_multimoneda_aplica_efectivo_en_la_moneda_del_pago(cobros_app):
    """#975: 100 USD aplicados a una factura de 3.600 NIO consumen 100 USD, no 3.600."""
    with cobros_app.app_context():
        factura = _factura("cacao", Decimal("3600"))
        pago = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=FECHA,
            docstatus=1,
            party_type="customer",
            party_name="Cliente Mostrador",
            currency="USD",
            exchange_rate=Decimal("36"),
            paid_amount=Decimal("100"),
            received_amount=Decimal("100"),
        )
        database.session.add(pago)
        database.session.flush()
        database.session.add(
            PaymentReference(
                payment_id=pago.id,
                reference_type="sales_invoice",
                reference_id=factura.id,
                company="cacao",
                currency="NIO",
                total_amount=Decimal("3600"),
                outstanding_amount=Decimal("3600"),
                outstanding_amount_after=Decimal("0"),
                allocated_amount=Decimal("3600"),
                payment_currency="USD",
                payment_amount=Decimal("100"),
                payment_exchange_rate=Decimal("36"),
            )
        )
        database.session.commit()

        nodo = get_document_node("payment_entry", pago.id, include_payment_balance=True)

    assert nodo["currency"] == "USD"
    assert Decimal(nodo["total"]) == Decimal("100")
    assert Decimal(nodo["unallocated_amount"]) == Decimal("0")
    aplicado = Decimal(nodo["total"]) - Decimal(nodo["unallocated_amount"])
    assert aplicado == Decimal("100")


def test_anticipo_sin_aplicar_expone_el_saldo_completo(cobros_app):
    """Control de negocio: un anticipo sin referencias mantiene todo su saldo."""
    with cobros_app.app_context():
        anticipo = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=FECHA,
            docstatus=1,
            party_type="customer",
            party_name="Cliente Mostrador",
            currency="NIO",
            paid_amount=Decimal("250"),
            received_amount=Decimal("250"),
        )
        database.session.add(anticipo)
        database.session.commit()

        nodo = get_document_node("payment_entry", anticipo.id, include_payment_balance=True)

    assert Decimal(nodo["total"]) == Decimal("250")
    assert Decimal(nodo["unallocated_amount"]) == Decimal("250")
