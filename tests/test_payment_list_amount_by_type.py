# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1949: listados y detalle muestran los importes propios de cada pago."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Bank, BankAccount, PaymentEntry, database

pytestmark = pytest.mark.usefixtures("entorno_contable")


def _create_transfer_accounts(app, suffix: str) -> dict[str, str]:
    """Create source and destination accounts, including a duplicate GL mapping."""
    with app.app_context():
        source_gl = Accounts(
            entity="cacao",
            code=f"S{suffix}",
            name="Banco origen QA",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            group=False,
        )
        target_gl = Accounts(
            entity="cacao",
            code=f"T{suffix}",
            name="Banco destino QA",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            group=False,
        )
        source_bank = Bank(name=f"Banco origen {suffix}", is_active=True)
        target_bank = Bank(name=f"Banco destino {suffix}", is_active=True)
        database.session.add_all([source_gl, target_gl, source_bank, target_bank])
        database.session.flush()
        source_account = BankAccount(
            bank_id=source_bank.id,
            company="cacao",
            account_name="Cuenta origen QA",
            account_no=f"SRC-{suffix}",
            currency="NIO",
            gl_account_id=source_gl.id,
            is_active=True,
        )
        decoy_target_account = BankAccount(
            bank_id=target_bank.id,
            company="cacao",
            account_name="Cuenta alternativa QA",
            account_no=f"ALT-{suffix}",
            currency="NIO",
            gl_account_id=target_gl.id,
            is_active=True,
        )
        target_account = BankAccount(
            bank_id=target_bank.id,
            company="cacao",
            account_name="Cuenta destino QA",
            account_no=f"DST-{suffix}",
            currency="USD",
            gl_account_id=target_gl.id,
            is_active=True,
        )
        database.session.add_all([source_account, decoy_target_account, target_account])
        database.session.commit()
        return {
            "source_account": source_account.id,
            "decoy_target_account": decoy_target_account.id,
            "target_account": target_account.id,
            "source_bank": source_bank.id,
            "target_bank": target_bank.id,
            "source_gl": source_gl.id,
            "target_gl": target_gl.id,
        }


def _create_payment_rows(app, prefix: str, accounts: dict[str, str]) -> list[str]:
    """Persist representative receive/pay/note/transfer entries."""
    with app.app_context():
        payments = [
            PaymentEntry(
                company="cacao",
                payment_type="receive",
                posting_date=date(2026, 5, 15),
                paid_amount=Decimal("0"),
                received_amount=Decimal("321.00"),
                transaction_currency="NIO",
                party_name="Cliente cobro",
                document_no=f"{prefix}-REC",
            ),
            PaymentEntry(
                company="cacao",
                payment_type="pay",
                posting_date=date(2026, 5, 15),
                paid_amount=Decimal("654.00"),
                received_amount=Decimal("0"),
                transaction_currency="NIO",
                party_name="Proveedor pago",
                document_no=f"{prefix}-PAY",
            ),
            PaymentEntry(
                company="cacao",
                payment_type="credit_note",
                posting_date=date(2026, 5, 15),
                paid_amount=Decimal("0"),
                received_amount=Decimal("87.50"),
                transaction_currency="NIO",
                party_name="Nota crédito QA",
                document_no=f"{prefix}-CR",
            ),
            PaymentEntry(
                company="cacao",
                payment_type="debit_note",
                posting_date=date(2026, 5, 15),
                paid_amount=Decimal("98.75"),
                received_amount=Decimal("0"),
                transaction_currency="NIO",
                party_name="Nota débito QA",
                document_no=f"{prefix}-DR",
            ),
            PaymentEntry(
                company="cacao",
                payment_type="internal_transfer",
                posting_date=date(2026, 5, 15),
                bank_account_id=accounts["source_account"],
                target_bank_account_id=accounts["target_account"],
                paid_from_account_id=accounts["source_gl"],
                paid_to_account_id=accounts["target_gl"],
                currency="NIO",
                transaction_currency="NIO",
                paid_amount=Decimal("100.00"),
                received_amount=Decimal("110.00"),
                party_name="",
                document_no=f"{prefix}-TR",
            ),
        ]
        database.session.add_all(payments)
        database.session.commit()
        return [payment.id for payment in payments]


def _assert_payment_listings(client) -> None:
    """Assert amount and label for each payment type's list route."""
    expectations = {
        "/cash_management/payment/list": ("321.00", "654.00", "NIO"),
        "/cash_management/payment/credit-note/list": ("87.50", "Nota de crédito", "NIO"),
        "/cash_management/payment/debit-note/list": ("98.75", "Nota de débito", "NIO"),
        "/cash_management/transfer/list": ("100.0000 NIO → 110.0000 USD", "Transferencia interna"),
    }
    for path, expected_values in expectations.items():
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for expected_value in expected_values:
            assert expected_value in html


def _assert_payment_details(client, payment_ids: list[str]) -> None:
    """Assert amount, currencies, and localized type in all payment details."""
    expectations = (
        (payment_ids[0], "Recibir", "NIO 321.00"),
        (payment_ids[1], "Pagar", "NIO 654.00"),
        (payment_ids[2], "Nota de crédito", "NIO 87.50"),
        (payment_ids[3], "Nota de débito", "NIO 98.75"),
        (payment_ids[4], "Transferencia interna", "100.00 NIO → 110.00 USD"),
    )
    for payment_id, label, amount in expectations:
        response = client.get(f"/cash_management/payment/{payment_id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert label in html
        assert amount in html


def _delete_payment_scenario(app, prefix: str, accounts: dict[str, str]) -> None:
    """Remove only the payment and account records created by this test."""
    with app.app_context():
        payment_ids = database.select(PaymentEntry.id).where(PaymentEntry.document_no.like(f"{prefix}-%"))
        database.session.execute(database.delete(PaymentEntry).where(PaymentEntry.id.in_(payment_ids)))
        for key in ("source_account", "decoy_target_account", "target_account"):
            bank_account = database.session.get(BankAccount, accounts[key])
            if bank_account is not None:
                database.session.delete(bank_account)
        for key in ("source_bank", "target_bank"):
            bank = database.session.get(Bank, accounts[key])
            if bank is not None:
                database.session.delete(bank)
        for key in ("source_gl", "target_gl"):
            account = database.session.get(Accounts, accounts[key])
            if account is not None:
                database.session.delete(account)
        database.session.commit()


def test_montos_por_tipo_y_dos_monedas_de_transferencia(app, authenticated_client):
    """Las notas usan la dirección correcta y transferencias presentan ambas cuentas."""
    suffix = uuid4().hex[:8]
    prefix = f"QA1949-{suffix}"
    accounts = _create_transfer_accounts(app, suffix)
    payment_ids = _create_payment_rows(app, prefix, accounts)
    try:
        client = authenticated_client("admin")
        _assert_payment_listings(client)
        _assert_payment_details(client, payment_ids)
    finally:
        _delete_payment_scenario(app, prefix, accounts)
