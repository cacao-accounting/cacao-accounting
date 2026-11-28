# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1556/#1806: el monto bancario se resuelve por el lado positivo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.bancos import statement_service
from cacao_accounting.bancos.reconciliation_service import BankCandidate
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    database,
)


def _withdrawal_transaction() -> BankTransaction:
    """Crea una transacción válida con depósito en cero y retiro positivo."""
    suffix = uuid4().hex[:8]
    bank = Bank(name=f"Banco {suffix}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(bank_id=bank.id, company="cacao", account_name=f"Cuenta {suffix}", account_no=f"ACC-{suffix}")
    database.session.add(account)
    database.session.flush()
    transaction = BankTransaction(
        identity_key=f"identity-{suffix}",
        bank_account_id=account.id,
        posting_date=date(2026, 5, 15),
        deposit=Decimal("0"),
        withdrawal=Decimal("125"),
        description="Pago de servicios",
        is_reconciled=False,
    )
    database.session.add(transaction)
    database.session.commit()
    return transaction


def test_pantalla_de_conciliacion_muestra_el_retiro_positivo(app, authenticated_client):
    """La tabla y el monto sugerido no toman el depósito en cero."""
    with app.app_context():
        transaction = _withdrawal_transaction()
        transaction_id = transaction.id
    client = authenticated_client("admin")

    response = client.get("/cash_management/bank-reconciliation?company=cacao")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'name="amount_{transaction_id}" class="form-control form-control-sm" value="125' in body
    assert "<td>125" in body


def test_autoconciliacion_usa_el_retiro_positivo(app, monkeypatch):
    """El servicio concilia 125 y no cero cuando el depósito está en cero."""
    with app.app_context():
        transaction = _withdrawal_transaction()
        database.session.add(
            BankMatchingRule(
                company="cacao",
                bank_account_id=transaction.bank_account_id,
                name="Regla exacta",
                days_tolerance=0,
                amount_tolerance=Decimal("0"),
                priority=1,
                is_active=True,
                auto_reconcile=True,
            )
        )
        database.session.commit()
        transaction_id = transaction.id

    candidate = BankCandidate(
        reference_type="payment_entry",
        reference_id="pe-1",
        amount=Decimal("125"),
        posting_date=date(2026, 5, 15),
        reference_no="PE-1",
        score=100,
        status="exact",
    )
    asignado: dict[str, Decimal] = {}

    monkeypatch.setattr(statement_service, "find_bank_reconciliation_candidates", lambda *_args, **_kwargs: [candidate])

    def _reconciliar(request):
        asignado["amount"] = request.matches[0].allocated_amount
        return SimpleNamespace(id="rec-1")

    monkeypatch.setattr(statement_service, "reconcile_bank_items", _reconciliar)

    with app.app_context():
        result = statement_service.auto_reconcile_bank_transaction(transaction_id)

        assert asignado["amount"] == Decimal("125")
        assert result.allocated_amount == Decimal("125")
        assert result.reconciled is True


@pytest.fixture(autouse=True)
def _sin_transacciones_previas(app):
    """Aísla la pantalla de otras transacciones pendientes del mismo fixture."""
    with app.app_context():
        database.session.execute(database.delete(BankTransaction))
        database.session.commit()
