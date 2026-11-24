# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1704: el anticipo creado en banca persiste, recarga y se aplica después."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import submit_document
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    CompanyDefaultAccount,
    Party,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseOrder,
    User,
    database,
)
from cacao_accounting.document_flow.payment import apply_advance_to_invoice
from cacao_accounting.internal_control_service import audit_actor


def _crear_cuenta_anticipo() -> str:
    """Garantiza una cuenta de anticipo a proveedores para la compañía."""
    cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1201")).scalar_one_or_none()
    if cuenta is None:
        cuenta = Accounts(
            entity="cacao",
            code="1201",
            name="Anticipos a proveedores",
            classification="asset",
            account_type="supplier_advance",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add(cuenta)
        database.session.flush()
    return cuenta.id


def _preparar(app) -> dict[str, str]:
    """Crea banco, cuenta bancaria, orden y factura para el anticipo."""
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        banco = Bank(name=f"Banco anticipo {uuid4().hex[:6]}", is_active=True)
        database.session.add(banco)
        database.session.flush()
        banco_gl = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
        cuenta_bancaria = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta anticipo",
            account_no=f"ANT-{uuid4().hex[:6]}",
            currency="NIO",
            gl_account_id=banco_gl.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        anticipo_id = _crear_cuenta_anticipo()
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.supplier_advance_account_id = anticipo_id
        orden = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PO-1704-{uuid4().hex[:6]}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("25"),
        )
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PI-1704-{uuid4().hex[:6]}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("25"),
            outstanding_amount=Decimal("25"),
        )
        database.session.add_all([orden, factura])
        database.session.commit()
        return {
            "banco": cuenta_bancaria.id,
            "orden": orden.id,
            "factura": factura.id,
            "proveedor": supplier.id,
        }


def _pagar(client, ids: dict[str, str], *, advance: bool, amount: str, lines: list[dict]) -> None:
    """Envía el formulario de pago por la ruta real."""
    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": ids["banco"],
        "posting_date": "2026-05-15",
        "paid_amount": amount,
        "party_type": "supplier",
        "party_id": ids["proveedor"],
        "advance_mode": advance,
        "lines": lines,
    }
    response = client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(payload)})
    assert response.status_code == 302, response.get_data(as_text=True)


def _ultimo_pago(company: str) -> str:
    """Devuelve el último pago persistido de la compañía."""
    pago = (
        database.session.execute(
            database.select(PaymentEntry).filter_by(company=company).order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert pago is not None
    return pago.id


def _aprobar(app, payment_id: str) -> None:
    """Aprueba y contabiliza el pago recién creado."""
    with app.test_request_context("/"):
        pago = database.session.get(PaymentEntry, payment_id)
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name), approved_execution(pago, actor.id):
            submit_document(pago)
        database.session.commit()


def test_anticipo_creado_en_banca_persiste_recarga_y_se_aplica(app, entorno_contable, authenticated_client):
    """El flujo real conserva is_advance y permite la aplicación posterior."""
    ids = _preparar(app)
    client = authenticated_client("admin")
    original_mode = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = False
    try:
        _pagar(
            client,
            ids,
            advance=True,
            amount="25",
            lines=[],
        )
        with app.app_context():
            payment_id = _ultimo_pago("cacao")
            database.session.remove()
            recargado = database.session.get(PaymentEntry, payment_id)
            assert recargado is not None
            assert recargado.is_advance is True
            assert recargado.docstatus == 0

        _aprobar(app, payment_id)
        with app.app_context():
            database.session.remove()
            aprobado = database.session.get(PaymentEntry, payment_id)
            assert aprobado is not None
            assert aprobado.docstatus == 1
            assert aprobado.is_advance is True

            referencia = apply_advance_to_invoice(
                payment_id,
                ids["factura"],
                Decimal("25"),
                date(2026, 5, 20),
            )
            database.session.commit()
            assert referencia.payment_id == payment_id
            assert referencia.reference_id == ids["factura"]
            assert referencia.allocated_amount == Decimal("25")
            assert database.session.get(PaymentReference, referencia.id) is not None
    finally:
        app.config["MODO_ESCRITORIO"] = original_mode


def test_pago_normal_persiste_sin_advance_y_no_se_aplica_como_anticipo(app, entorno_contable, authenticated_client):
    """Control negativo: un pago normal no adquiere is_advance ni aplica después."""
    ids = _preparar(app)
    client = authenticated_client("admin")
    original_mode = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = False
    try:
        _pagar(client, ids, advance=False, amount="10", lines=[])
        with app.app_context():
            payment_id = _ultimo_pago("cacao")
            database.session.remove()
            recargado = database.session.get(PaymentEntry, payment_id)
            assert recargado is not None
            assert recargado.is_advance is False

        _aprobar(app, payment_id)
        with app.app_context():
            database.session.remove()
            with pytest.raises(ValueError):
                apply_advance_to_invoice(
                    payment_id,
                    ids["factura"],
                    Decimal("10"),
                    date(2026, 5, 20),
                )
                database.session.commit()
    finally:
        app.config["MODO_ESCRITORIO"] = original_mode
