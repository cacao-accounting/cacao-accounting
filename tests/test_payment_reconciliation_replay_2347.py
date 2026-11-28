# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2347: un replay idéntico de conciliación no indexa un plan vacío.

El planner devuelve ``lines=()`` cuando la clave y la huella ya están
persistidas. El caller de pagos debe tratar ese caso como idempotente y no
volver a aplicar la referencia ni consumir efectivo disponible.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cacao_accounting.contabilidad.arap_allocation import (
    AllocationLine,
    allocation_fingerprint,
)
from cacao_accounting.database import (
    PaymentEntry,
    PaymentReference,
    Party,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.payment import (
    PaymentAllocationContext,
    _ReconciliationLineValues,
    _apply_standard_reconciliation_allocation,
    _plan_reconciliation_allocation,
)
from cacao_accounting.document_flow.service import DocumentFlowError

FECHA = date(2026, 5, 15)


def _scenario(amount: str = "25") -> tuple[str, str, str, str]:
    """Crea pago, factura y referencia con clave y huella persistidas."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    invoice = SalesInvoice(
        company="cacao",
        posting_date=FECHA,
        document_no="SI-2347",
        document_type="sales_invoice",
        customer_id=customer_id,
        customer_name="Cliente de prueba",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("100"),
        outstanding_amount=Decimal("100"),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("100"),
        paid_amount=Decimal("100"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        document_no="PAY-2347",
        docstatus=1,
    )
    database.session.add(payment)
    database.session.flush()
    key = f"{payment.id}:sales_invoice:{invoice.id}"
    line = AllocationLine(
        document_id=invoice.id,
        document_type="sales_invoice",
        document_currency="NIO",
        source_currency="NIO",
        document_amount=Decimal(amount),
        source_amount=Decimal(amount),
        rate=Decimal("1"),
        idempotency_key=key,
    )
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            party_type="customer",
            party_id=customer_id,
            company="cacao",
            currency="NIO",
            allocated_amount=Decimal(amount),
            payment_amount=Decimal(amount),
            idempotency_key=key,
            allocation_fingerprint=allocation_fingerprint(line),
        )
    )
    database.session.commit()
    return str(payment.id), str(invoice.id), key, customer_id


def _plan(payment_id: str, invoice_id: str, allocated: str):
    """Invoca el planner del caller con el saldo y efectivo del escenario."""
    payment = database.session.get(PaymentEntry, payment_id)
    invoice = database.session.get(SalesInvoice, invoice_id)
    return _plan_reconciliation_allocation(
        raw_line={},
        payment=payment,
        document=invoice,
        flow_source_type="sales_invoice",
        document_id=invoice_id,
        outstanding=Decimal("100"),
        allocated=Decimal(allocated),
        available=Decimal("100"),
        allocation_date=FECHA,
    )


def test_replay_identico_devuelve_la_linea_sin_plan_nuevo(entorno_contable_aislado):
    """La misma clave y contenido no provoca IndexError ni una segunda línea."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, invoice_id, _key, _customer_id = _scenario()

        line, replayed = _plan(payment_id, invoice_id, "25")

        assert replayed is True
        assert line.document_amount == Decimal("25")
        assert line.source_amount == Decimal("25")
        assert database.session.execute(select(func.count(PaymentReference.id))).scalar_one() == 1


def test_apply_standard_no_duplica_evidencia_en_replay(entorno_contable_aislado):
    """El replay idéntico no vuelve a persistir la referencia ni GL."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, invoice_id, _key, customer_id = _scenario()
        payment = database.session.get(PaymentEntry, payment_id)
        invoice = database.session.get(SalesInvoice, invoice_id)
        values = _ReconciliationLineValues(
            payment_id=payment_id,
            document_id=invoice_id,
            flow_source_type="sales_invoice",
            model_type="sales_invoice",
            allocated=Decimal("25"),
            discount=Decimal("0"),
            gain_loss=Decimal("0"),
            difference=Decimal("0"),
        )
        context = PaymentAllocationContext(
            allocation_date=FECHA,
            allocated=Decimal("25"),
            discount=Decimal("0"),
            gain_loss=Decimal("0"),
            difference=Decimal("0"),
            outstanding=Decimal("100"),
        )

        line, replayed = _apply_standard_reconciliation_allocation(
            raw_line={},
            payment=payment,
            document=invoice,
            values=values,
            allocation_ctx=context,
            company="cacao",
            party_type="customer",
            party_id=customer_id,
            available=Decimal("100"),
            outstanding=Decimal("100"),
            reconciliation_id="rec-2347",
        )

        assert replayed is True
        assert line.idempotency_key.startswith(payment_id)
        assert database.session.execute(select(func.count(PaymentReference.id))).scalar_one() == 1


def test_misma_clave_con_distribucion_distinta_se_rechaza(entorno_contable_aislado):
    """Un contenido diferente bajo la misma clave no es un replay idempotente."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, invoice_id, _key, _customer_id = _scenario(amount="25")

        with pytest.raises(DocumentFlowError, match="otro contenido"):
            _plan(payment_id, invoice_id, "30")

        assert database.session.execute(select(func.count(PaymentReference.id))).scalar_one() == 1
