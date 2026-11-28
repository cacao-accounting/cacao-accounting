# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1495: un anticipo solo se aplica a la factura de su dirección.

Un pago a proveedor no puede aplicarse a una cuenta por cobrar de cliente
ni un cobro de cliente a una cuenta por pagar; además, el documento debe
ser una factura estándar y no una nota del mismo modelo.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.database import (
    Party,
    PaymentEntry,
    PurchaseInvoice,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.payment import (
    _load_advance_invoice,
    _validate_advance_allocation,
)
from cacao_accounting.document_flow.service import DocumentFlowError

FECHA = date(2026, 5, 15)


def _parties() -> tuple[str, str]:
    """Devuelve cliente y proveedor del escenario."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
    return customer_id, supplier_id


def _sales_invoice(customer_id: str, document_type: str = "sales_invoice") -> SalesInvoice:
    """Crea una factura de venta publicada por 100."""
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type=document_type,
        document_no=f"FAC-1495-{document_type}",
        posting_date=FECHA,
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _purchase_invoice(supplier_id: str) -> PurchaseInvoice:
    """Crea una factura de compra publicada por 100."""
    invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier_id,
        document_type="purchase_invoice",
        document_no="FAC-1495-COMPRA",
        posting_date=FECHA,
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _payment(payment_type: str, party_type: str, party_id: str) -> PaymentEntry:
    """Crea un anticipo aprobado por 100."""
    payment = PaymentEntry(
        company="cacao",
        payment_type=payment_type,
        party_type=party_type,
        party_id=party_id,
        posting_date=FECHA,
        paid_amount=Decimal("100"),
        received_amount=Decimal("100"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        is_advance=True,
        document_no=f"ADV-1495-{payment_type}-{party_type}",
    )
    database.session.add(payment)
    database.session.flush()
    return payment


def test_pago_a_proveedor_no_se_aplica_a_factura_de_venta(entorno_contable_aislado):
    """La dirección 'pay' se rechaza contra una cuenta por cobrar."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_id, supplier_id = _parties()
        invoice = _sales_invoice(customer_id)
        payment = _payment("pay", "supplier", supplier_id)

        with pytest.raises(DocumentFlowError, match="tipo de pago"):
            _validate_advance_allocation(payment, invoice, customer_id, Decimal("25"), FECHA)


def test_cobro_de_cliente_no_se_aplica_a_factura_de_compra(entorno_contable_aislado):
    """La dirección 'receive' se rechaza contra una cuenta por pagar."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_id, supplier_id = _parties()
        invoice = _purchase_invoice(supplier_id)
        payment = _payment("receive", "customer", customer_id)

        with pytest.raises(DocumentFlowError, match="tipo de pago"):
            _validate_advance_allocation(payment, invoice, supplier_id, Decimal("25"), FECHA)


def test_tipo_de_tercero_debe_coincidir_con_la_factura(entorno_contable_aislado):
    """Un cobro con party_type supplier no se acepta contra una venta."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_id, supplier_id = _parties()
        invoice = _sales_invoice(customer_id)
        payment = _payment("receive", "supplier", supplier_id)

        with pytest.raises(DocumentFlowError, match="tipo de tercero"):
            _validate_advance_allocation(payment, invoice, customer_id, Decimal("25"), FECHA)


@pytest.mark.parametrize(
    ("payment_type", "party_type", "invoice_kind"),
    [("receive", "customer", "sales"), ("pay", "supplier", "purchase")],
)
def test_direcciones_validas_conservan_el_flujo(entorno_contable_aislado, payment_type, party_type, invoice_kind):
    """Los emparejamientos correctos siguen devolviendo el saldo posterior."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_id, supplier_id = _parties()
        if invoice_kind == "sales":
            invoice = _sales_invoice(customer_id)
            party_id = customer_id
        else:
            invoice = _purchase_invoice(supplier_id)
            party_id = supplier_id
        payment = _payment(payment_type, party_type, party_id)

        outstanding, after, rate = _validate_advance_allocation(payment, invoice, party_id, Decimal("25"), FECHA)

        assert (outstanding, after, rate) == (Decimal("100"), Decimal("75"), Decimal("1"))


def test_carga_de_anticipo_rechaza_notas_del_modelo(entorno_contable_aislado):
    """Una nota de crédito no se trata como factura estándar."""
    app = entorno_contable_aislado.app
    with app.app_context():
        customer_id, _supplier_id = _parties()
        note = _sales_invoice(customer_id, document_type="sales_credit_note")

        with pytest.raises(DocumentFlowError, match="subtipo"):
            _load_advance_invoice(note.id)
