# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1228: cancelar un pago recalcula el estado bancario restante.

Un movimiento conciliado contra varios pagos debe conservar
``is_reconciled`` solo si las asignaciones activas restantes cubren su
importe; la referencia singular ``payment_entry_id`` no basta.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.bancos.services import _apply_payment_cancellation_hooks
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    database,
)

FECHA = date(2026, 5, 15)


def _scenario(amounts: tuple[str, str] = ("40", "60")) -> tuple[str, list[str]]:
    """Crea movimiento de 100 conciliado contra dos pagos."""
    bank = Bank(name="Banco 1228", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta 1228",
        account_no="ACC-1228",
        currency="NIO",
    )
    database.session.add(account)
    database.session.flush()
    payments = []
    for index, amount in enumerate(amounts, start=1):
        payment = PaymentEntry(
            company="cacao",
            payment_type="pay",
            party_type="supplier",
            bank_account_id=account.id,
            posting_date=FECHA,
            paid_amount=Decimal(amount),
            received_amount=Decimal(amount),
            currency="NIO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=1,
            document_no=f"PAY-1228-{index}",
        )
        database.session.add(payment)
        database.session.flush()
        payments.append(str(payment.id))
    transaction = BankTransaction(
        identity_key="BANK-1228",
        bank_account_id=account.id,
        posting_date=FECHA,
        deposit=Decimal("100"),
        description="Movimiento conciliado con dos pagos",
        is_reconciled=True,
        payment_entry_id=payments[0],
    )
    database.session.add(transaction)
    database.session.flush()
    reconciliation = Reconciliation(company="cacao", recon_date=FECHA, recon_type="bank")
    database.session.add(reconciliation)
    database.session.flush()
    for payment_id, amount in zip(payments, amounts, strict=True):
        database.session.add(
            ReconciliationItem(
                reconciliation_id=reconciliation.id,
                reference_type="bank_transaction",
                reference_id=transaction.id,
                amount=Decimal(amount),
                allocated_amount=Decimal(amount),
                reconciliation_date=FECHA,
                status="reconciled",
                source_type="bank_transaction",
                source_id=transaction.id,
                target_type="payment_entry",
                target_id=payment_id,
                company="cacao",
                bank_account_id=account.id,
                currency="NIO",
                direction="deposit",
            )
        )
    database.session.commit()
    return str(transaction.id), payments


@pytest.mark.parametrize("cancelled_index", [0, 1])
def test_cancelar_un_pago_deja_el_movimiento_pendiente(entorno_contable_aislado, cancelled_index):
    """Con solo 40 o 60 asignados de 100 el movimiento vuelve a pendiente."""
    app = entorno_contable_aislado.app
    with app.app_context():
        transaction_id, payments = _scenario()
        cancelled_id = payments[cancelled_index]
        remaining_id = payments[1 - cancelled_index]

        _apply_payment_cancellation_hooks(database.session.get(PaymentEntry, cancelled_id))
        database.session.commit()

        transaction = database.session.get(BankTransaction, transaction_id)
        assert transaction is not None
        assert transaction.is_reconciled is False
        assert transaction.payment_entry_id == remaining_id
        statuses = dict(
            database.session.execute(
                select(ReconciliationItem.target_id, ReconciliationItem.status).where(
                    ReconciliationItem.source_id == transaction_id
                )
            ).all()
        )
        assert statuses[cancelled_id] == "cancelled"
        assert statuses[remaining_id] == "reconciled"


def test_cancelar_todas_las_asignaciones_limpia_la_referencia(entorno_contable_aislado):
    """Al cancelar los dos pagos el movimiento queda pendiente y sin pago."""
    app = entorno_contable_aislado.app
    with app.app_context():
        transaction_id, payments = _scenario()

        for payment_id in payments:
            _apply_payment_cancellation_hooks(database.session.get(PaymentEntry, payment_id))
            database.session.commit()

        transaction = database.session.get(BankTransaction, transaction_id)
        assert transaction is not None
        assert transaction.is_reconciled is False
        assert transaction.payment_entry_id is None


def test_cancelar_pago_legacy_sin_partidas_limpia_el_movimiento(entorno_contable_aislado):
    """Un movimiento descubierto solo por payment_entry_id conserva el contrato previo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        transaction_id, payments = _scenario()
        database.session.execute(database.update(ReconciliationItem).values(status="cancelled"))
        transaction = database.session.get(BankTransaction, transaction_id)
        transaction.is_reconciled = True
        transaction.payment_entry_id = payments[0]
        database.session.commit()

        _apply_payment_cancellation_hooks(database.session.get(PaymentEntry, payments[0]))
        database.session.commit()

        transaction = database.session.get(BankTransaction, transaction_id)
        assert transaction is not None
        assert transaction.is_reconciled is False
        assert transaction.payment_entry_id is None
