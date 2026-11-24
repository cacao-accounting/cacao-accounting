# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresiones del importe de candidatos reales de conciliación (#1644)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_login import login_user
from sqlalchemy import inspect
import pytest

from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    PaymentEntry,
    ReconciliationItem,
    User,
    database,
)


def _escenario():
    """Crea dos reglas reales y un pago para una transacción bancaria."""
    suffix = uuid4().hex[:8]
    bank = Bank(name=f"Banco {suffix}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(bank_id=bank.id, company="cacao", account_name=f"Cuenta {suffix}", account_no=suffix, currency="NIO")
    database.session.add(account)
    database.session.flush()
    transaction = BankTransaction(
        bank_account_id=account.id, posting_date=date(2026, 5, 15), deposit=Decimal("100"), withdrawal=Decimal("0")
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        payment_type="receive",
        bank_account_id=account.id,
        currency="NIO",
        received_amount=Decimal("102"),
    )
    database.session.add_all([transaction, payment])
    database.session.add_all(
        [
            BankMatchingRule(
                company="cacao",
                bank_account_id=account.id,
                name=f"Regla {n}",
                days_tolerance=0,
                amount_tolerance=Decimal(str(tol)),
                priority=n,
                is_active=True,
                auto_reconcile=True,
            )
            for n, tol in ((1, 2), (2, 5))
        ]
    )
    database.session.commit()
    return account, transaction, payment


def test_reglas_reales_obtienen_mismo_importe_y_concilian(entorno_contable_aislado):
    """Dos tolerancias aceptan el mismo destino y consumen el mismo importe."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        _, transaction, payment = _escenario()

        candidates = [
            find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal(tol))
            for tol in ("2", "5")
        ]
        for result in candidates:
            assert len(result) == 1
            assert result[0].reference_id == payment.id
            assert result[0].status == "exact"
            assert result[0].amount == Decimal("100")

        result = auto_reconcile_bank_transaction(transaction.id)
        assert result.reconciled is True
        assert result.allocated_amount == Decimal("100")
        rows = (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].target_id == payment.id
        assert rows[0].allocated_amount == Decimal("100")


def test_mismo_destino_con_importes_distintos_no_se_consolida(entorno_contable_aislado, monkeypatch):
    """Si dos reglas ven el mismo destino con importes distintos, no concilia.

    Las tolerancias reales no cambian el importe asignado al mismo pago; esta
    regresión protege el contrato ante una evaluación concurrente o futura que
    sí produjera esa discrepancia.
    """
    from cacao_accounting.bancos import statement_service

    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        _, transaction, payment = _escenario()
        real = statement_service.find_bank_reconciliation_candidates

        def candidato_con_importe_distinto(bank_transaction_id, *, lock=False, days_tolerance=None, amount_tolerance=None):
            base = real(
                bank_transaction_id,
                lock=lock,
                days_tolerance=days_tolerance,
                amount_tolerance=amount_tolerance,
            )
            if not base:
                return base
            importe = Decimal("100") if amount_tolerance == Decimal("2") else Decimal("90")
            return [replace(base[0], amount=importe)]

        monkeypatch.setattr(statement_service, "find_bank_reconciliation_candidates", candidato_con_importe_distinto)

        resultado = statement_service.auto_reconcile_bank_transaction(transaction.id)

        assert resultado.reconciled is False
        assert resultado.reason == "ambiguous"
        assert resultado.candidate_reference_id is None
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )
        assert payment.id


def test_destinos_reales_distintos_quedan_ambiguos(entorno_contable_aislado):
    """Dos pagos reales elegibles no producen conciliación automática."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, _ = _escenario()
        database.session.add(
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 5, 15),
                docstatus=1,
                payment_type="receive",
                bank_account_id=account.id,
                currency="NIO",
                received_amount=Decimal("102"),
            )
        )
        database.session.commit()
        result = auto_reconcile_bank_transaction(transaction.id)
        assert result.reconciled is False
        assert result.reason == "ambiguous"
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )


def test_saldo_cambiado_rechaza_candidato_obsoleto(entorno_contable_aislado):
    """La validación final rechaza un saldo consumido tras buscar candidatos."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, payment = _escenario()
        candidate = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("2"))[0]
        other = BankTransaction(
            bank_account_id=account.id, posting_date=date(2026, 5, 15), deposit=Decimal("40"), withdrawal=Decimal("0")
        )
        database.session.add(other)
        database.session.flush()
        reconcile_bank_items(
            BankReconciliationRequest(
                company="cacao",
                reconciliation_date=date(2026, 5, 15),
                matches=[BankReconciliationMatch(other.id, "payment_entry", payment.id, Decimal("40"))],
            )
        )
        database.session.commit()
        with pytest.raises(BankReconciliationError, match="saldo pendiente"), database.session.begin_nested():
            reconcile_bank_items(
                BankReconciliationRequest(
                    company="cacao",
                    reconciliation_date=date(2026, 5, 15),
                    matches=[
                        BankReconciliationMatch(
                            transaction.id, candidate.reference_type, candidate.reference_id, candidate.amount
                        )
                    ],
                )
            )
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )
        assert auto_reconcile_bank_transaction(transaction.id).reason == "no_unique_exact_match"
