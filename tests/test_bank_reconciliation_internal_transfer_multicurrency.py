# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1317: la pata destino de una transferencia usa su propia moneda.

USD→EUR con funcional NIO: la candidata y la validación manual deben usar
``received_amount`` en EUR, no rechazar la transferencia por la moneda
origen del encabezado.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.bancos.reconciliation_service import (
    _candidate_payment_amount,
    _target_payment_amount,
    find_bank_reconciliation_candidates,
)
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    PaymentEntry,
    database,
)

FECHA = date(2026, 5, 15)


def _accounts() -> tuple[str, str, str]:
    """Crea una cuenta bancaria USD y otra EUR de la misma compañía."""
    from cacao_accounting.database import Currency

    for code, name in (("USD", "Dólar"), ("EUR", "Euro")):
        exists = database.session.execute(select(Currency.id).filter_by(code=code)).scalar_one_or_none()
        if exists is None:
            database.session.add(Currency(code=code, name=name, decimals=2, active=True, default=False))
    database.session.flush()
    bank = Bank(name="Banco 1317", is_active=True)
    database.session.add(bank)
    database.session.flush()
    source = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta USD",
        account_no="USD-1317",
        currency="USD",
    )
    target = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta EUR",
        account_no="EUR-1317",
        currency="EUR",
    )
    database.session.add_all([source, target])
    database.session.flush()
    return str(bank.id), str(source.id), str(target.id)


def _transfer(source_id: str, target_id: str) -> str:
    """Crea una transferencia interna aprobada USD→EUR."""
    payment = PaymentEntry(
        company="cacao",
        payment_type="internal_transfer",
        bank_account_id=source_id,
        target_bank_account_id=target_id,
        posting_date=FECHA,
        paid_amount=Decimal("100"),
        received_amount=Decimal("91.50"),
        base_received_amount=None,
        currency="USD",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        document_no="TRF-1317",
    )
    database.session.add(payment)
    database.session.commit()
    return str(payment.id)


def _transaction(account_id: str, *, deposit: Decimal | None = None, withdrawal: Decimal | None = None) -> str:
    """Crea el movimiento de extracto de la pierna indicada."""
    transaction = BankTransaction(
        identity_key=f"BANK-1317-{account_id}-{deposit or withdrawal}",
        bank_account_id=account_id,
        posting_date=FECHA,
        deposit=deposit,
        withdrawal=withdrawal,
        is_reconciled=False,
    )
    database.session.add(transaction)
    database.session.commit()
    return str(transaction.id)


def test_pata_destino_eur_aparece_como_candidata(entorno_contable_aislado):
    """La transferencia USD→EUR se ofrece por los 91.50 EUR recibidos."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _bank_id, source_id, target_id = _accounts()
        payment_id = _transfer(source_id, target_id)
        transaction_id = _transaction(target_id, deposit=Decimal("91.50"))

        candidates = find_bank_reconciliation_candidates(transaction_id)

        payment_candidates = [item for item in candidates if item.reference_id == payment_id]
        assert len(payment_candidates) == 1
        assert payment_candidates[0].amount == Decimal("91.5000")


def test_validacion_manual_usa_la_moneda_de_la_cuenta_destino(entorno_contable_aislado):
    """La asignación manual no rechaza USD≠EUR cuando la pata es EUR."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _bank_id, source_id, target_id = _accounts()
        payment_id = _transfer(source_id, target_id)
        transaction_id = _transaction(target_id, deposit=Decimal("91.50"))
        transaction = database.session.get(BankTransaction, transaction_id)
        payment = database.session.get(PaymentEntry, payment_id)

        assert _target_payment_amount(payment_id, "EUR", "NIO", target_id) == Decimal("91.50")
        assert _candidate_payment_amount(payment, transaction, "EUR", "NIO") == Decimal("91.50")


def test_pata_origen_conserva_su_importe_en_usd(entorno_contable_aislado):
    """La pierna origen sigue exponiendo los 100 USD pagados."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _bank_id, source_id, target_id = _accounts()
        payment_id = _transfer(source_id, target_id)
        transaction_id = _transaction(source_id, withdrawal=Decimal("100"))
        transaction = database.session.get(BankTransaction, transaction_id)
        payment = database.session.get(PaymentEntry, payment_id)

        assert _candidate_payment_amount(payment, transaction, "USD", "NIO") == Decimal("100")
        candidates = find_bank_reconciliation_candidates(transaction_id)
        payment_candidates = [item for item in candidates if item.reference_id == payment_id]
        assert len(payment_candidates) == 1
        assert payment_candidates[0].amount == Decimal("100.0000")
