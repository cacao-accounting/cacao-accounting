# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del Issue #721: tolerancias de matching bancario aplicadas y auto-conciliación.

Cubre:
- ``days_tolerance`` y ``amount_tolerance`` de ``BankMatchingRule`` afectan
  realmente la ventana y el scoring del motor de candidatos.
- La auto-conciliación opcional end-to-end al importar extractos aplica la
  conciliación solo ante un único candidato exacto dentro de tolerancias y
  deja registro auditable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"))
        database.session.commit()
        yield app


def _seed_bank_account(account_name: str = "Cuenta tolerancias"):
    from cacao_accounting.database import Bank, BankAccount, database

    bank = Bank(name=f"Banco {account_name}")
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(bank_id=bank.id, company="cacao", account_name=account_name, is_active=True)
    database.session.add(account)
    database.session.flush()
    return account


def _seed_payment(bank_account_id: str, amount: str, posting_date: date, payment_type: str = "receive"):
    from cacao_accounting.database import PaymentEntry, database

    kwargs: dict = {"paid_amount": amount} if payment_type == "pay" else {"received_amount": amount}
    payment = PaymentEntry(
        company="cacao",
        posting_date=posting_date,
        payment_type=payment_type,
        bank_account_id=bank_account_id,
        docstatus=1,
        **kwargs,
    )
    database.session.add(payment)
    database.session.flush()
    return payment


def _seed_transaction(bank_account_id: str, amount: str, posting_date: date):
    from cacao_accounting.database import BankTransaction, database

    transaction = BankTransaction(
        bank_account_id=bank_account_id,
        posting_date=posting_date,
        deposit=Decimal(amount),
    )
    database.session.add(transaction)
    database.session.flush()
    return transaction


def _seed_rule(
    bank_account_id: str | None,
    *,
    days_tolerance: int = 7,
    amount_tolerance: str = "0",
    auto_reconcile: bool = False,
    is_active: bool = True,
    reference_contains: str | None = None,
) -> object:
    from cacao_accounting.database import BankMatchingRule, database

    rule = BankMatchingRule(
        company="cacao",
        bank_account_id=bank_account_id,
        name="Regla tolerancias",
        days_tolerance=days_tolerance,
        amount_tolerance=Decimal(amount_tolerance),
        reference_contains=reference_contains,
        is_active=is_active,
        auto_reconcile=auto_reconcile,
    )
    database.session.add(rule)
    database.session.flush()
    return rule


def test_candidate_score_marks_amount_within_tolerance_as_full_match() -> None:
    """Un monto dentro de la tolerancia obtiene los mismos puntos que un monto exacto."""
    from types import SimpleNamespace

    from cacao_accounting.bancos.reconciliation_service import _candidate_score

    transaction = SimpleNamespace(deposit=Decimal("100"), withdrawal=Decimal("0"), posting_date=date(2026, 5, 5))

    exact = _candidate_score(
        bank_transaction=transaction, amount=Decimal("100"), posting_date=date(2026, 5, 5), reference_no=None
    )
    within = _candidate_score(
        bank_transaction=transaction,
        amount=Decimal("98"),
        posting_date=date(2026, 5, 5),
        reference_no=None,
        amount_tolerance=Decimal("2"),
    )
    outside = _candidate_score(
        bank_transaction=transaction,
        amount=Decimal("98"),
        posting_date=date(2026, 5, 5),
        reference_no=None,
        amount_tolerance=Decimal("1"),
    )

    assert exact == 85
    assert within == 85
    assert outside == 25


def test_days_tolerance_widens_candidate_window(app_ctx):
    """Un pago fuera de ±7 días entra en candidatos cuando la regla amplía la ventana."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    account = _seed_bank_account()
    far_date = date(2026, 5, 20)
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "100.00", far_date)
    _seed_rule(account.id, days_tolerance=20)

    candidates = find_bank_reconciliation_candidates(transaction.id)

    assert [candidate.reference_id for candidate in candidates] != []
    assert any(candidate.status == "exact" for candidate in candidates)


def test_amount_tolerance_marks_near_amount_as_exact_candidate(app_ctx):
    """Un pago con diferencia menor a la tolerancia se marca como candidato exacto."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "99.50", date(2026, 5, 5))
    _seed_rule(account.id, amount_tolerance="0.50")

    candidates = find_bank_reconciliation_candidates(transaction.id)

    assert len(candidates) == 1
    assert candidates[0].status == "exact"
    assert candidates[0].score >= 60

    # Sin tolerancia configurada el mismo pago permanece parcial.
    rule = _seed_rule(account.id, amount_tolerance="0")
    from cacao_accounting.bancos.statement_service import apply_bank_matching_rule

    run = apply_bank_matching_rule(
        rule.id if hasattr(rule, "id") else "",  # type: ignore[attr-defined]
        account.id,
        (date(2026, 5, 1), date(2026, 5, 31)),
    )
    strict_candidates = run.candidates_by_transaction[transaction.id]
    assert strict_candidates[0].status == "partial"


def test_inactive_rules_do_not_loosen_matching(app_ctx):
    """Las reglas inactivas no aflojan la ventana ni el scoring."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "100.00", date(2026, 5, 30))
    _seed_rule(account.id, days_tolerance=30, is_active=False)

    candidates = find_bank_reconciliation_candidates(transaction.id)

    assert candidates == []


def test_company_scoped_rule_applies_to_any_account(app_ctx):
    """Una regla sin cuenta específica aplica a todas las cuentas de la compañía."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    account = _seed_bank_account()
    other = _seed_bank_account("Otra cuenta")
    transaction = _seed_transaction(other.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "100.00", date(2026, 5, 5))  # ruido: otra cuenta
    _seed_payment(other.id, "99.90", date(2026, 5, 5))
    _seed_rule(None, amount_tolerance="0.10")

    candidates = find_bank_reconciliation_candidates(transaction.id)

    assert [candidate.reference_id for candidate in candidates if candidate.status == "exact"]


def test_auto_reconcile_unique_exact_match_applies_and_audits(app_ctx):
    """Con regla auto-conciliable y un único candidato exacto se aplica y audita."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
    from cacao_accounting.audit_trail_service import get_document_timeline
    from cacao_accounting.database import Reconciliation, ReconciliationItem, database

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    payment = _seed_payment(account.id, "100.00", date(2026, 5, 5))
    rule = _seed_rule(account.id, auto_reconcile=True)

    result = auto_reconcile_bank_transaction(str(transaction.id))
    database.session.commit()

    assert result.reconciled is True
    assert result.rule_id == rule.id
    assert result.candidate_reference_type == "payment_entry"
    assert result.candidate_reference_id == payment.id
    assert result.allocated_amount == Decimal("100.00")
    assert result.reason is None
    assert result.reconciliation_id

    database.session.expire_all()
    refreshed = database.session.get(type(transaction), transaction.id)
    assert refreshed.is_reconciled is True
    items = database.session.execute(database.select(ReconciliationItem)).scalars().all()
    assert len(items) == 1
    assert items[0].target_id == payment.id
    assert database.session.execute(database.select(Reconciliation)).scalars().all()

    timeline = get_document_timeline("BankTransaction", str(transaction.id))
    assert any(entry.action == "reconciled" for entry in timeline)


def test_auto_reconcile_skips_ambiguous_matches(app_ctx):
    """Dos candidatos exactos impiden la aplicación automática (ambigüedad)."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
    from cacao_accounting.database import ReconciliationItem, database

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "200.00", date(2026, 5, 5))
    _seed_payment(account.id, "200.00", date(2026, 5, 5))
    _seed_payment(account.id, "200.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=True)

    result = auto_reconcile_bank_transaction(str(transaction.id))
    database.session.commit()

    assert result.reconciled is False
    assert result.reason == "ambiguous"
    assert database.session.execute(database.select(ReconciliationItem)).scalars().all() == []


def test_auto_reconcile_without_rules_is_noop(app_ctx):
    """Sin reglas activas auto-conciliables no se aplica nada y se reporta la causa."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "100.00", date(2026, 5, 5))

    result = auto_reconcile_bank_transaction(str(transaction.id))

    assert result.reconciled is False
    assert result.reason == "no_active_rule"


def test_auto_reconcile_requires_flag_on_rule(app_ctx):
    """Una regla activa sin la bandera auto_reconcile no dispara la conciliación."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "100.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=False)

    result = auto_reconcile_bank_transaction(str(transaction.id))

    assert result.reconciled is False
    assert result.reason == "no_active_rule"


def test_auto_reconcile_ignores_already_reconciled(app_ctx):
    """Una transacción ya conciliada se omite con reason already_reconciled."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    transaction.is_reconciled = True
    _seed_rule(account.id, auto_reconcile=True)

    result = auto_reconcile_bank_transaction(str(transaction.id))

    assert result.reconciled is False
    assert result.reason == "already_reconciled"


def test_auto_reconcile_no_unique_exact_match_reports_reason(app_ctx):
    """Sin candidato exacto único (solo parciales) no se aplica y se reporta la causa."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
    from cacao_accounting.database import ReconciliationItem, database

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "40.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=True)

    result = auto_reconcile_bank_transaction(str(transaction.id))
    database.session.commit()

    assert result.reconciled is False
    assert result.reason == "no_unique_exact_match"
    assert database.session.execute(database.select(ReconciliationItem)).scalars().all() == []


MAPPING = {
    "date": "date",
    "reference": "reference",
    "description": "description",
    "deposit": "deposit",
    "withdrawal": "withdrawal",
}


def test_import_statement_end_to_end_auto_reconciles(app_ctx):
    """La importación de extracto aplica la conciliación automática end-to-end."""
    from cacao_accounting.bancos.statement_service import import_bank_statement
    from cacao_accounting.database import BankTransaction, ReconciliationItem, database

    account = _seed_bank_account()
    csv_data = (
        "date,reference,description,deposit,withdrawal\n"
        "2026-05-05,PAY-1,Cobro conciliable,100.00,\n"
        "2026-05-06,PAY-2,Cobro manual,55.55,\n"
    )
    _seed_payment(account.id, "100.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=True)

    result = import_bank_statement(StringIO(csv_data), MAPPING, account.id, company="cacao")

    assert result.imported_count == 2
    reconciled_rows = [row for row in result.rows if row.bank_transaction_id]
    auto_by_reference = {}
    for auto in result.auto_reconciled:
        row = next(r for r in reconciled_rows if r.bank_transaction_id == auto.bank_transaction_id)
        auto_by_reference[row.reference_number] = auto

    assert auto_by_reference["PAY-1"].reconciled is True
    assert auto_by_reference["PAY-2"].reconciled is False
    assert auto_by_reference["PAY-2"].reason == "no_unique_exact_match"

    database.session.expire_all()
    transactions = database.session.execute(database.select(BankTransaction)).scalars().all()
    by_reference = {t.reference_number: t for t in transactions}
    assert by_reference["PAY-1"].is_reconciled is True
    assert by_reference["PAY-2"].is_reconciled is False
    items = database.session.execute(database.select(ReconciliationItem)).scalars().all()
    assert len(items) == 1


def test_import_statement_preview_never_auto_reconciles(app_ctx):
    """La previsualización nunca persiste ni auto-concilia."""
    from cacao_accounting.bancos.statement_service import import_bank_statement
    from cacao_accounting.database import BankTransaction, ReconciliationItem, database

    account = _seed_bank_account()
    csv_data = "date,reference,description,deposit,withdrawal\n2026-05-05,PRE-1,Vista previa,100.00,\n"
    _seed_payment(account.id, "100.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=True)

    result = import_bank_statement(StringIO(csv_data), MAPPING, account.id, company="cacao", preview=True)

    assert result.imported_count == 0
    assert all(row.bank_transaction_id is None for row in result.rows)
    assert result.auto_reconciled == []
    assert database.session.execute(database.select(BankTransaction)).scalars().all() == []
    assert database.session.execute(database.select(ReconciliationItem)).scalars().all() == []


def test_apply_bank_matching_rule_uses_rule_tolerances(app_ctx):
    """La ejecución de una regla respeta sus tolerancias al buscar candidatos."""
    from cacao_accounting.bancos.statement_service import apply_bank_matching_rule

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    _seed_payment(account.id, "99.00", date(2026, 5, 5))
    rule = _seed_rule(account.id, days_tolerance=7, amount_tolerance="1.00")

    run = apply_bank_matching_rule(
        getattr(rule, "id"),  # type: ignore[attr-defined]
        account.id,
        (date(2026, 5, 1), date(2026, 5, 31)),
    )

    candidates = run.candidates_by_transaction[transaction.id]
    assert len(candidates) == 1
    assert candidates[0].status == "exact"


def test_import_adapter_persists_and_auto_reconciles(app_ctx):
    """El asistente de importación también dispara la auto-conciliación."""
    from cacao_accounting.database import BankTransaction, database
    from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

    account = _seed_bank_account()
    _seed_payment(account.id, "80.00", date(2026, 5, 5))
    _seed_rule(account.id, auto_reconcile=True)

    document = [
        {
            "bank_account_id": account.id,
            "posting_date": "2026-05-05",
            "reference_number": "ADP-1",
            "description": "Desde asistente",
            "deposit": "80.00",
            "withdrawal": "",
        }
    ]
    built = BankStatementAdapter().build_document(document, {"company_id": "cacao"})
    BankStatementAdapter().persist_document(built)
    database.session.commit()

    transaction = database.session.execute(database.select(BankTransaction)).scalars().one()
    assert transaction.is_reconciled is True


def test_import_adapter_survives_auto_reconcile_failure(app_ctx, monkeypatch):
    """Un fallo de auto-conciliación no revierte la fila importada."""
    from cacao_accounting.database import BankTransaction, database
    from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

    account = _seed_bank_account()
    _seed_rule(account.id, auto_reconcile=True)

    from cacao_accounting.bancos.reconciliation_service import BankReconciliationError

    def broken_auto(_transaction_id: str):
        raise BankReconciliationError("fallo simulado de conciliacion")

    from cacao_accounting.bancos import statement_service

    monkeypatch.setattr(statement_service, "auto_reconcile_bank_transaction", broken_auto)

    document = [
        {
            "bank_account_id": account.id,
            "posting_date": "2026-05-05",
            "reference_number": "FAIL-1",
            "description": "Fallo controlado",
            "deposit": "10.00",
            "withdrawal": "",
        }
    ]
    built = BankStatementAdapter().build_document(document, {"company_id": "cacao"})
    BankStatementAdapter().persist_document(built)
    database.session.commit()

    persisted = database.session.execute(database.select(BankTransaction)).scalars().all()
    assert len(persisted) == 1
    assert persisted[0].is_reconciled is False


def test_legacy_default_window_without_rules_remains_seven_days(app_ctx):
    """Sin reglas configuradas se conserva la ventana histórica de ±7 días."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    account = _seed_bank_account()
    transaction = _seed_transaction(account.id, "100.00", date(2026, 5, 5))
    inside = _seed_payment(account.id, "100.00", date(2026, 5, 12))
    outside = _seed_payment(account.id, "100.00", date(2026, 5, 13))

    candidates = find_bank_reconciliation_candidates(transaction.id)
    candidate_ids = {candidate.reference_id for candidate in candidates}

    assert inside.id in candidate_ids
    assert outside.id not in candidate_ids
