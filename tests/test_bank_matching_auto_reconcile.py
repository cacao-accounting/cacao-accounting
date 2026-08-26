# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para tolerancias de matching y conciliación automática (issue #721).

Cubre:
1. Las tolerancias configuradas en ``BankMatchingRule`` afectan realmente al
   motor de candidatos: ventana de días y rango de montos.
2. La auto-conciliación opcional al importar extractos: aplica cuando hay un
   único candidato exacto dentro de las tolerancias, configurable por regla
   (compañía/cuenta) y con registro auditable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "bnk8"
AS_OF = date(2026, 8, 21)


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con base SQLite en memoria."""
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
        from cacao_accounting.database import Currency, Entity

        database.create_all()
        database.session.add_all(
            [
                Entity(code=COMPANY, name="Banco8", company_name="Banco8", tax_id="BNK-8", currency="NIO"),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def chart(app_ctx):
    """Catalogo minimo: cuenta GL bancaria, banco, cuenta bancaria y libro primario."""
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        database,
    )

    bank_gl = Accounts(entity=COMPANY, code="1001", name="Banco A", classification="asset", account_type="bank")
    fx_gain = Accounts(entity=COMPANY, code="4102", name="Ganancia Cambiaria", classification="income")
    book = Book(entity=COMPANY, code="BNKLOC", name="Libro Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([bank_gl, fx_gain, book])
    database.session.flush()

    bank = Bank(name="Banco Nacional 8")
    database.session.add(bank)
    database.session.flush()

    account = BankAccount(
        bank_id=bank.id,
        company=COMPANY,
        account_name="Cuenta A",
        account_no="A-001",
        currency="NIO",
        gl_account_id=bank_gl.id,
    )
    database.session.add_all(
        [
            account,
            CompanyDefaultAccount(
                company=COMPANY,
                default_bank=bank_gl.id,
                exchange_gain_account_id=fx_gain.id,
                exchange_loss_account_id=fx_gain.id,
                unrealized_exchange_gain_account_id=fx_gain.id,
                unrealized_exchange_loss_account_id=fx_gain.id,
            ),
        ]
    )
    database.session.commit()
    return {"bank_gl_id": bank_gl.id, "book_id": book.id, "account": account}


def _make_bank_transaction(account, *, deposit=None, withdrawal=None, posting_date=AS_OF, reference=None):
    """Persiste una linea de extracto bancario."""
    from cacao_accounting.database import BankTransaction, database

    transaction = BankTransaction(
        bank_account_id=account.id,
        posting_date=posting_date,
        reference_number=reference,
        deposit=deposit,
        withdrawal=withdrawal,
    )
    database.session.add(transaction)
    database.session.commit()
    return transaction


def _make_payment(*, amount, payment_type="receive", bank_account, posting_date=AS_OF, currency="NIO", rate=Decimal("1")):
    """Crea un pago aprobado sin posting de GL."""
    from cacao_accounting.database import PaymentEntry, database

    is_inflow = payment_type in ("receive", "credit_note")
    received_amount = amount if is_inflow else None
    paid_amount = amount if not is_inflow else None
    base_received = (amount * rate) if received_amount is not None else None
    base_paid = (amount * rate) if paid_amount is not None else None
    payment = PaymentEntry(
        company=COMPANY,
        posting_date=posting_date,
        payment_type=payment_type,
        bank_account_id=bank_account.id,
        paid_from_account_id=bank_account.gl_account_id if not is_inflow else None,
        paid_to_account_id=bank_account.gl_account_id if is_inflow else None,
        transaction_currency=currency,
        base_currency="NIO",
        currency=currency,
        exchange_rate=rate,
        received_amount=received_amount,
        paid_amount=paid_amount,
        base_received_amount=base_received,
        base_paid_amount=base_paid,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()
    return payment


def _make_matching_rule(
    *,
    account_id=None,
    company=COMPANY,
    days_tolerance=7,
    amount_tolerance=Decimal("0"),
    reference_contains=None,
    auto_reconcile=False,
    is_active=True,
    priority=100,
    name="R1",
):
    """Crea y persiste una regla de matching bancario."""
    from cacao_accounting.database import BankMatchingRule, database

    rule = BankMatchingRule(
        company=company,
        bank_account_id=account_id,
        name=name,
        days_tolerance=days_tolerance,
        amount_tolerance=amount_tolerance,
        reference_contains=reference_contains,
        priority=priority,
        is_active=is_active,
        auto_reconcile=auto_reconcile,
    )
    database.session.add(rule)
    database.session.commit()
    return rule


# --------------------------------------------------------------------------- #
# 1. Tolerancias afectan el matching


def test_date_tolerance_extends_candidate_window(app_ctx, chart):
    """Un pago fuera de la ventana ±7 días no es candidato, pero sí con tolerancia amplia."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    transaction = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    _make_payment(
        amount=Decimal("100.00"),
        payment_type="receive",
        bank_account=chart["account"],
        posting_date=date(2026, 8, 31),
    )

    default_candidates = [
        c for c in find_bank_reconciliation_candidates(transaction.id) if c.reference_type == "payment_entry"
    ]
    assert default_candidates == []

    wide_candidates = [
        c
        for c in find_bank_reconciliation_candidates(transaction.id, days_tolerance=14)
        if c.reference_type == "payment_entry"
    ]
    assert len(wide_candidates) == 1
    assert wide_candidates[0].score == 60  # monto coincide (+60), fecha no (+0)


def test_amount_tolerance_affects_scoring(app_ctx, chart):
    """Un pago con monto dentro de la tolerancia gana los 60 puntos de monto."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    transaction = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    _make_payment(amount=Decimal("105.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)

    strict = find_bank_reconciliation_candidates(transaction.id, amount_tolerance=Decimal("0"))
    assert strict[0].score == 25  # solo fecha coincide, no monto

    tolerant = find_bank_reconciliation_candidates(transaction.id, amount_tolerance=Decimal("10"))
    assert tolerant[0].score == 85  # monto +60, fecha +25


def test_amount_tolerance_marks_status_exact(app_ctx, chart):
    """El estado del candidato es 'exact' cuando el monto está dentro de la tolerancia."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    transaction = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    _make_payment(amount=Decimal("102.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)

    strict = find_bank_reconciliation_candidates(transaction.id, amount_tolerance=Decimal("0"))
    assert strict[0].status == "partial"

    tolerant = find_bank_reconciliation_candidates(transaction.id, amount_tolerance=Decimal("5"))
    assert tolerant[0].status == "exact"


def test_apply_bank_matching_rule_uses_rule_tolerances(app_ctx, chart):
    """apply_bank_matching_rule pasa las tolerancias de la regla al motor de candidatos."""
    from cacao_accounting.bancos.statement_service import apply_bank_matching_rule

    transaction = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    _make_payment(amount=Decimal("103.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    rule = _make_matching_rule(account_id=chart["account"].id, days_tolerance=7, amount_tolerance=Decimal("5"))

    run = apply_bank_matching_rule(rule.id, chart["account"].id, (AS_OF, AS_OF))
    candidates = run.candidates_by_transaction[transaction.id]
    payment_candidates = [c for c in candidates if c.reference_type == "payment_entry"]
    assert len(payment_candidates) == 1
    assert payment_candidates[0].score == 85
    assert payment_candidates[0].status == "exact"


# --------------------------------------------------------------------------- #
# 2. Auto-conciliación al importar extracto


def test_import_auto_reconciles_single_exact_match(app_ctx, chart):
    """Al importar con una regla auto_reconcile, el depósito único se concilia."""
    from cacao_accounting.bancos.statement_service import import_bank_statement
    from cacao_accounting.database import BankTransaction, Reconciliation, database

    _make_payment(amount=Decimal("100.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    _make_matching_rule(account_id=chart["account"].id, days_tolerance=7, amount_tolerance=Decimal("0"), auto_reconcile=True)

    csv_data = "fecha,referencia,deposito\n2026-08-21,DEP-1,100.00\n"
    mapping = {"date": "fecha", "reference": "referencia", "deposit": "deposito", "withdrawal": ""}
    result = import_bank_statement(StringIO(csv_data), mapping, chart["account"].id, company=COMPANY, preview=False)

    assert result.imported_count == 1
    tx = database.session.execute(select(BankTransaction).filter_by(bank_account_id=chart["account"].id)).scalar_one()
    assert tx.is_reconciled is True
    assert tx.payment_entry_id is not None
    assert len(result.auto_reconciled) == 1
    assert result.auto_reconciled[0].reconciled is True
    assert result.auto_reconciled[0].reason is None
    assert result.auto_reconciled[0].reconciliation_id is not None
    assert database.session.get(Reconciliation, result.auto_reconciled[0].reconciliation_id) is not None


def test_import_does_not_auto_reconcile_when_disabled(app_ctx, chart):
    """Sin regla auto_reconcile, la importación no concilia nada."""
    from cacao_accounting.bancos.statement_service import import_bank_statement
    from cacao_accounting.database import BankTransaction, database

    _make_payment(amount=Decimal("100.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    _make_matching_rule(account_id=chart["account"].id, auto_reconcile=False)

    csv_data = "fecha,referencia,deposito\n2026-08-21,DEP-1,100.00\n"
    mapping = {"date": "fecha", "reference": "referencia", "deposit": "deposito", "withdrawal": ""}
    result = import_bank_statement(StringIO(csv_data), mapping, chart["account"].id, company=COMPANY, preview=False)

    tx = database.session.execute(select(BankTransaction).filter_by(bank_account_id=chart["account"].id)).scalar_one()
    assert tx.is_reconciled is False
    assert len(result.auto_reconciled) == 1
    assert result.auto_reconciled[0].reconciled is False
    assert result.auto_reconciled[0].reason == "no_active_rule"


def test_auto_reconcile_ambiguous_multiple_exact(app_ctx, chart):
    """Cuando dos pagos coinciden exactamente, no se autoconcilia (ambigüedad)."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
    from cacao_accounting.database import BankTransaction, database

    _make_payment(amount=Decimal("100.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    _make_payment(amount=Decimal("100.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    _make_matching_rule(account_id=chart["account"].id, auto_reconcile=True)

    tx = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    result = auto_reconcile_bank_transaction(tx.id)

    assert result.reconciled is False
    assert result.reason == "ambiguous"
    assert database.session.get(BankTransaction, tx.id).is_reconciled is False


def test_find_auto_reconcile_rules_scopes_by_bank_account(app_ctx, chart):
    """Una regla para otra cuenta no aplica a la cuenta actual."""
    from cacao_accounting.bancos.statement_service import _find_auto_reconcile_rules
    from cacao_accounting.database import Accounts, Bank, BankAccount, database

    other_gl = Accounts(entity=COMPANY, code="1002", name="Banco B", classification="asset", account_type="bank")
    database.session.add(other_gl)
    database.session.flush()
    other_bank = Bank(name="Otro Banco")
    database.session.add(other_bank)
    database.session.flush()
    other_account = BankAccount(
        bank_id=other_bank.id,
        company=COMPANY,
        account_name="Cuenta B",
        account_no="B-001",
        currency="NIO",
        gl_account_id=other_gl.id,
    )
    database.session.add(other_account)
    database.session.commit()

    rule_account = _make_matching_rule(account_id=chart["account"].id, auto_reconcile=True, name="AcctRule")
    rule_other = _make_matching_rule(account_id=other_account.id, auto_reconcile=True, name="OtherRule")
    _make_matching_rule(account_id=None, auto_reconcile=True, name="CompanyRule")

    rules = _find_auto_reconcile_rules(chart["account"].id, COMPANY)
    rule_ids = {rule.id for rule in rules}
    assert rule_account.id in rule_ids
    assert rule_other.id not in rule_ids
    assert any(rule.bank_account_id is None for rule in rules)


def test_auto_reconcile_respects_amount_tolerance(app_ctx, chart):
    """Un pago cuya diferencia está dentro de la tolerancia se concilia automáticamente."""
    from cacao_accounting.bancos.statement_service import auto_reconcile_bank_transaction
    from cacao_accounting.database import BankTransaction, database

    _make_payment(amount=Decimal("105.00"), payment_type="receive", bank_account=chart["account"], posting_date=AS_OF)
    _make_matching_rule(account_id=chart["account"].id, auto_reconcile=True, amount_tolerance=Decimal("10"))

    tx = _make_bank_transaction(chart["account"], deposit=Decimal("100.00"), posting_date=AS_OF)
    result = auto_reconcile_bank_transaction(tx.id)

    assert result.reconciled is True
    assert result.reason is None
    assert database.session.get(BankTransaction, tx.id).is_reconciled is True
