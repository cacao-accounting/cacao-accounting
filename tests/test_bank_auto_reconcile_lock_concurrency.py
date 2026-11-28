# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2306: la regla activada durante la espera cambia el conjunto de candidatos."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos import statement_service
from cacao_accounting.bancos.reconciliation_service import BankCandidate
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    Currency,
    Entity,
    database,
)
from cacao_accounting.default_scope import lock_default_scopes

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'auto-reconcile-lock.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2306",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str):
    company = f"B{suffix}"
    account_id = None
    transaction_id = None
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}", is_active=True)
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(bank_id=bank.id, company=company, account_name=f"Cuenta {suffix}", account_no=f"ACC-{suffix}")
        database.session.add(account)
        database.session.flush()
        transaction = BankTransaction(
            identity_key=f"identity-{suffix}",
            bank_account_id=account.id,
            posting_date=date(2026, 10, 15),
            deposit=Decimal("100"),
            withdrawal=Decimal("0"),
            description="Depósito",
            is_reconciled=False,
        )
        database.session.add(transaction)
        database.session.add(
            BankMatchingRule(
                company=company,
                bank_account_id=account.id,
                name=f"Cercana {suffix}",
                days_tolerance=7,
                amount_tolerance=Decimal("0"),
                priority=1,
                is_active=True,
                auto_reconcile=True,
            )
        )
        database.session.commit()
        account_id = account.id
        transaction_id = transaction.id
        database.session.remove()
    return company, account_id, transaction_id


def _candidate(reference_id: str, amount: str) -> BankCandidate:
    return BankCandidate(
        reference_type="payment_entry",
        reference_id=reference_id,
        amount=Decimal(amount),
        posting_date=date(2026, 10, 15),
        reference_no=reference_id.upper(),
        score=100,
        status="exact",
    )


def test_regla_confirmada_durante_la_espera_deja_pendiente(tmp_path, monkeypatch):
    """La segunda regla convierte el candidato exacto en ambiguo antes del commit."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    company, account_id, transaction_id = _seed(app, suffix)
    candidate_a = _candidate("pe-cercana", "100")
    candidate_b = _candidate("pe-amplia", "105")
    search_started = Event()

    def candidates(_id, *, days_tolerance, amount_tolerance):
        search_started.set()
        return [candidate_a] if days_tolerance == 7 else [candidate_b]

    monkeypatch.setattr(statement_service, "find_bank_reconciliation_candidates", candidates)
    reconciliations: list[object] = []
    monkeypatch.setattr(
        statement_service,
        "reconcile_bank_items",
        lambda request: reconciliations.append(request) or SimpleNamespace(id="rec-1"),
    )
    second_rule_ready = Event()
    release_auto = Event()

    def create_second_rule() -> None:
        with app.app_context():
            lock_default_scopes("bank_auto_reconcile", [(company, None), (company, account_id)])
            database.session.add(
                BankMatchingRule(
                    company=company,
                    bank_account_id=account_id,
                    name=f"Amplia {suffix}",
                    days_tolerance=30,
                    amount_tolerance=Decimal("5"),
                    priority=2,
                    is_active=True,
                    auto_reconcile=True,
                )
            )
            database.session.flush()
            second_rule_ready.set()
            try:
                assert release_auto.wait(timeout=30)
                database.session.commit()
            finally:
                database.session.remove()

    def auto_reconcile():
        with app.app_context():
            try:
                return statement_service.auto_reconcile_bank_transaction(transaction_id)
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        rule_future = workers.submit(create_second_rule)
        assert second_rule_ready.wait(timeout=15)
        auto_future = workers.submit(auto_reconcile)
        # Sin lock la búsqueda ocurre de inmediato; con lock el hilo espera.
        search_started.wait(timeout=0.5)
        release_auto.set()
        rule_future.result(timeout=30)
        result = auto_future.result(timeout=30)

    assert result.reconciled is False
    assert result.reason == "ambiguous"
    assert reconciliations == []
