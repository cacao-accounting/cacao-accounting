# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1204/#1205: la prevalidación de conciliación iguala al flujo de aplicación.

Cubre que los ajustes no igualen o superen el monto asignado y que el saldo
disponible del pago se acumule entre líneas de la misma carga.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.api.line_import import (
    _validate_payment_reconciliation_amounts,
    _validate_payment_reconciliation_row,
)
from cacao_accounting.database import Party, PaymentEntry, SalesInvoice, database


def _escenario(app) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"REC-{suffix}", name="Cliente rec", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"REC-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("500"),
            outstanding_amount=Decimal("500"),
        )
        pago = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal("100"),
            received_amount=Decimal("100"),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"PAY-{suffix}",
        )
        database.session.add_all([factura, pago])
        database.session.commit()
        return {"payment": pago.id, "reference": factura.id, "party": cliente.id}


def test_ajustes_iguales_al_monto_se_rechazan(app, entorno_contable):
    """#1204: descuento + diferencia >= monto aplicado se reporta como error."""
    ids = _escenario(app)
    errors: list[dict] = []
    with app.app_context():
        from cacao_accounting.database import PaymentEntry as PaymentModel

        payment = database.session.get(PaymentModel, ids["payment"])
        reference = database.session.get(SalesInvoice, ids["reference"])
        _validate_payment_reconciliation_amounts(
            {"allocated_amount": "100", "discount_amount": "60", "gain_loss_amount": "40"},
            payment,
            reference,
            Decimal("1"),
            1,
            errors,
        )

    assert any("igual o mayor al monto aplicado" in error["message"] for error in errors)


def test_ajustes_inferiores_al_monto_se_aceptan(app, entorno_contable):
    """Control positivo: un ajuste menor al monto no produce error."""
    ids = _escenario(app)
    errors: list[dict] = []
    with app.app_context():
        payment = database.session.get(PaymentEntry, ids["payment"])
        reference = database.session.get(SalesInvoice, ids["reference"])
        _validate_payment_reconciliation_amounts(
            {"allocated_amount": "100", "discount_amount": "10", "gain_loss_amount": "5"},
            payment,
            reference,
            Decimal("1"),
            1,
            errors,
        )

    assert errors == []


def test_saldo_del_pago_se_acumula_entre_lineas(app, entorno_contable):
    """#1205: dos filas de 80 sobre un pago de 100 no pueden ser válidas ambas."""
    ids = _escenario(app)
    errors: list[dict] = []
    remaining: dict[str, Decimal] = {}
    with app.app_context():
        row = {
            "payment_id": ids["payment"],
            "reference_type": "sales_invoice",
            "reference_id": ids["reference"],
            "allocated_amount": "80",
        }
        _validate_payment_reconciliation_row(
            dict(row), 1, "cacao", errors, party_type="customer", party_id=ids["party"], payment_remaining=remaining
        )
        _validate_payment_reconciliation_row(
            dict(row), 2, "cacao", errors, party_type="customer", party_id=ids["party"], payment_remaining=remaining
        )

    assert any(error.get("row") == 2 and "saldo disponible del pago" in error["message"] for error in errors)
    assert all(error.get("row") != 1 for error in errors)


def test_filas_dentro_del_saldo_disponible_se_aceptan(app, entorno_contable):
    """Control positivo: dos filas de 40 caben en el saldo de 100."""
    ids = _escenario(app)
    errors: list[dict] = []
    remaining: dict[str, Decimal] = {}
    with app.app_context():
        row = {
            "payment_id": ids["payment"],
            "reference_type": "sales_invoice",
            "reference_id": ids["reference"],
            "allocated_amount": "40",
        }
        _validate_payment_reconciliation_row(
            dict(row), 1, "cacao", errors, party_type="customer", party_id=ids["party"], payment_remaining=remaining
        )
        _validate_payment_reconciliation_row(
            dict(row), 2, "cacao", errors, party_type="customer", party_id=ids["party"], payment_remaining=remaining
        )

    assert errors == []


def _escenario_documental(app, *, document_total: str, payment_total: str) -> dict[str, str]:
    """Crea una factura con saldo menor que el pago disponible."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"DOC-{suffix}", name="Cliente doc", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"DOC-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal(document_total),
            outstanding_amount=Decimal(document_total),
        )
        pago = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal(payment_total),
            received_amount=Decimal(payment_total),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"PAYDOC-{suffix}",
        )
        database.session.add_all([factura, pago])
        database.session.commit()
        return {"payment": pago.id, "reference": factura.id, "party": cliente.id}


def test_saldo_del_documento_se_acumula_entre_lineas(app, entorno_contable):
    """#1205: dos filas de 80 sobre una factura de 100 no pueden ser válidas ambas."""
    ids = _escenario_documental(app, document_total="100", payment_total="160")
    errors: list[dict] = []
    payment_remaining: dict[str, Decimal] = {}
    document_remaining: dict[str, Decimal] = {}
    with app.app_context():
        row = {
            "payment_id": ids["payment"],
            "reference_type": "sales_invoice",
            "reference_id": ids["reference"],
            "allocated_amount": "80",
        }
        _validate_payment_reconciliation_row(
            dict(row),
            1,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )
        _validate_payment_reconciliation_row(
            dict(row),
            2,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )

    assert any(error.get("row") == 2 and "saldo pendiente del documento" in error["message"] for error in errors)
    assert all(error.get("row") != 1 for error in errors)


def test_documento_con_saldo_suficiente_acepta_dos_filas(app, entorno_contable):
    """Control positivo: con saldo documental de 200, dos filas de 80 caben."""
    ids = _escenario_documental(app, document_total="200", payment_total="160")
    errors: list[dict] = []
    payment_remaining: dict[str, Decimal] = {}
    document_remaining: dict[str, Decimal] = {}
    with app.app_context():
        row = {
            "payment_id": ids["payment"],
            "reference_type": "sales_invoice",
            "reference_id": ids["reference"],
            "allocated_amount": "80",
        }
        _validate_payment_reconciliation_row(
            dict(row),
            1,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )
        _validate_payment_reconciliation_row(
            dict(row),
            2,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )

    assert errors == []


def _escenario_dual(app, *, document_total: str, payment_small: str, payment_large: str) -> dict[str, str]:
    """Factura con dos pagos: uno insuficiente y otro suficiente."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"DUAL-{suffix}", name="Cliente dual", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"DUAL-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal(document_total),
            outstanding_amount=Decimal(document_total),
        )
        pago_chico = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal(payment_small),
            received_amount=Decimal(payment_small),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"SMALL-{suffix}",
        )
        pago_grande = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal(payment_large),
            received_amount=Decimal(payment_large),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"LARGE-{suffix}",
        )
        database.session.add_all([factura, pago_chico, pago_grande])
        database.session.commit()
        return {
            "reference": factura.id,
            "party": cliente.id,
            "small": pago_chico.id,
            "large": pago_grande.id,
        }


def test_fila_rechazada_no_consume_saldo_del_documento(app, entorno_contable):
    """#1205: una fila rechazada por el pago no descuenta el saldo documental.

    Factura 100; fila 1 asigna 80 con pago disponible 20 → falla por pago.
    Fila 2 asigna 50 con otro pago suficiente → debe ser válida (la fila 1 no
    se aplicó y no debe consumir 80 del documento).
    """
    ids = _escenario_dual(app, document_total="100", payment_small="20", payment_large="60")
    errors: list[dict] = []
    payment_remaining: dict[str, Decimal] = {}
    document_remaining: dict[str, Decimal] = {}
    with app.app_context():
        _validate_payment_reconciliation_row(
            {
                "payment_id": ids["small"],
                "reference_type": "sales_invoice",
                "reference_id": ids["reference"],
                "allocated_amount": "80",
            },
            1,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )
        _validate_payment_reconciliation_row(
            {
                "payment_id": ids["large"],
                "reference_type": "sales_invoice",
                "reference_id": ids["reference"],
                "allocated_amount": "50",
            },
            2,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            payment_remaining=payment_remaining,
            document_remaining=document_remaining,
        )

    assert any(error.get("row") == 1 and "saldo disponible del pago" in error["message"] for error in errors)
    assert all(error.get("row") != 2 for error in errors)
