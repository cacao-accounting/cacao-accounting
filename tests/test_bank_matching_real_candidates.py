# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresiones del importe de candidatos reales de conciliación (#1644)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_login import login_user
from sqlalchemy import inspect, select
import pytest

from cacao_accounting.bancos.reconciliation_service import (
    BankCandidate,
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.bancos.statement_service import _accumulate_exact_candidate, auto_reconcile_bank_transaction
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
    """Dos tolerancias reales conservan el importe del mismo destino.

    El importe del candidato se calcula desde el saldo pendiente del pago y del
    importe bancario, sin intervención de la tolerancia. Esta prueba aporta la
    evidencia de que la discrepancia de importes para un mismo destino no es
    alcanzable en una evaluación real del motor sobre la misma transacción.
    """
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


def test_importes_distintos_para_mismo_destino_son_ambiguos(entorno_contable_aislado):
    """El consenso rechaza importes dispares para un mismo destino real.

    El candidato y las reglas salen del escenario persistido; solo se modela
    directamente la revisión de estado entre evaluaciones que representaría un
    saldo modificado, sin sustituir funciones del servicio.
    """
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        cuenta, transaction, _ = _escenario()
        candidato = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("2"))[0]
        reglas = (
            database.session.execute(
                select(BankMatchingRule)
                .where(BankMatchingRule.company == "cacao", BankMatchingRule.bank_account_id == cuenta.id)
                .order_by(BankMatchingRule.priority)
            )
            .scalars()
            .all()
        )

        vistos: dict[tuple[str, str], tuple[BankCandidate, BankMatchingRule]] = {}
        assert _accumulate_exact_candidate(vistos, candidato, reglas[0]) is True
        revisado = replace(candidato, amount=candidato.amount - Decimal("10"), score=candidato.score + 10)
        assert _accumulate_exact_candidate(vistos, revisado, reglas[1]) is False

        assert len(vistos) == 1
        assert next(iter(vistos.values()))[0].amount == candidato.amount


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
