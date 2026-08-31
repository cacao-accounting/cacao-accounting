"""Pruebas unitarias para las reglas puras de conciliación bancaria."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.bancos import reconciliation_service as service


def test_amount_and_direction_helpers_cover_bank_payment_and_gl_cases() -> None:
    """Calcula importes y direcciones para depósitos, retiros y transferencias."""
    deposit = SimpleNamespace(deposit=Decimal("25"), withdrawal=Decimal("0"))
    withdrawal = SimpleNamespace(deposit=Decimal("0"), withdrawal=Decimal("30"))
    empty = SimpleNamespace(deposit=None, withdrawal=None)
    assert service._bank_amount(deposit) == Decimal("25")
    assert service._bank_amount(withdrawal) == Decimal("30")
    assert service._bank_direction(deposit) == "deposit"
    assert service._bank_direction(withdrawal) == "withdrawal"
    assert service._bank_direction(empty) is None

    receive = SimpleNamespace(payment_type="receive", received_amount=Decimal("40"), paid_amount=None)
    pay = SimpleNamespace(payment_type="pay", received_amount=None, paid_amount=Decimal("50"))
    credit = SimpleNamespace(payment_type="credit_note", received_amount=Decimal("60"), paid_amount=None)
    debit = SimpleNamespace(payment_type="debit_note", received_amount=None, paid_amount=Decimal("70"))
    transfer_out = SimpleNamespace(payment_type="internal_transfer", bank_account_id="source", target_bank_account_id="target")
    transfer_in = SimpleNamespace(payment_type="internal_transfer", bank_account_id="source", target_bank_account_id="target")
    unsupported = SimpleNamespace(payment_type="journal", received_amount=None, paid_amount=None)
    assert service._payment_amount(receive) == Decimal("40")
    assert service._payment_amount(pay) == Decimal("50")
    assert service._payment_amount(credit) == Decimal("60")
    assert service._payment_amount(debit) == Decimal("70")
    transfer_amounts = SimpleNamespace(
        payment_type="internal_transfer",
        bank_account_id="source",
        target_bank_account_id="target",
        paid_amount=Decimal("100"),
        received_amount=Decimal("110"),
    )
    assert service._payment_amount(transfer_amounts, "source") == Decimal("100")
    assert service._payment_amount(transfer_amounts, "target") == Decimal("110")
    assert service._payment_direction(receive, deposit) == "deposit"
    assert service._payment_direction(pay, withdrawal) == "withdrawal"
    assert service._payment_direction(transfer_out, SimpleNamespace(bank_account_id="source")) == "withdrawal"
    assert service._payment_direction(transfer_in, SimpleNamespace(bank_account_id="target")) == "deposit"
    assert service._payment_direction(unsupported, deposit) is None

    gl_debit = SimpleNamespace(debit=Decimal("80"), credit=Decimal("0"))
    gl_credit = SimpleNamespace(debit=Decimal("0"), credit=Decimal("90"))
    gl_empty = SimpleNamespace(debit=None, credit=None)
    assert service._gl_direction(gl_debit) == "deposit"
    assert service._gl_direction(gl_credit) == "withdrawal"
    assert service._gl_direction(gl_empty) is None
    assert service._gl_amount(gl_debit) == Decimal("80")


def test_candidate_scoring_and_append_calculate_exact_and_partial_matches() -> None:
    """Asigna score, importe asignable y estado al candidato bancario."""
    transaction = SimpleNamespace(
        deposit=Decimal("100"),
        withdrawal=Decimal("0"),
        posting_date=date(2026, 8, 16),
        reference_number="BANK-001",
    )
    assert (
        service._candidate_score(
            bank_transaction=transaction,
            amount=Decimal("100"),
            posting_date=date(2026, 8, 16),
            reference_no="BANK-001",
        )
        == 100
    )
    candidates = []
    service._append_candidate(
        candidates,
        reference_type="payment_entry",
        reference_id="payment-1",
        amount=Decimal("100"),
        posting_date=date(2026, 8, 16),
        reference_no="BANK-001",
        bank_transaction=transaction,
        pending=Decimal("100"),
    )
    service._append_candidate(
        candidates,
        reference_type="payment_entry",
        reference_id="payment-2",
        amount=Decimal("75"),
        posting_date=date(2026, 8, 15),
        reference_no=None,
        bank_transaction=transaction,
        pending=Decimal("50"),
    )
    assert [(candidate.amount, candidate.status) for candidate in candidates] == [
        (Decimal("100"), "exact"),
        (Decimal("50"), "partial"),
    ]


def test_target_amounts_and_company_validation_raise_controlled_errors(monkeypatch) -> None:
    """Resuelve destinos aprobados y rechaza monedas, estados y tipos inválidos."""
    payment = SimpleNamespace(
        docstatus=1,
        currency="USD",
        payment_type="receive",
        received_amount=Decimal("100"),
        paid_amount=None,
        base_received_amount=Decimal("3650"),
        base_paid_amount=None,
        company="cacao",
    )
    gl_entry = SimpleNamespace(
        account_currency="USD",
        company_currency="NIO",
        debit=Decimal("100"),
        credit=Decimal("0"),
        debit_in_account_currency=Decimal("100"),
        credit_in_account_currency=None,
        company="cacao",
        account_id="bank-gl",
    )
    bank_account = SimpleNamespace(company="cacao", currency="USD", gl_account_id="bank-gl")

    def fake_get(model, ident, **kwargs):
        del kwargs
        if model is service.PaymentEntry:
            return payment if ident == "payment-1" else None
        if model is service.GLEntry:
            return gl_entry if ident == "gl-1" else None
        if model is service.BankAccount:
            return bank_account
        return None

    monkeypatch.setattr(service.database.session, "get", fake_get)
    assert service._target_amount("payment_entry", "payment-1") == Decimal("100")
    assert service._target_amount("gl_entry", "gl-1") == Decimal("100")
    assert service._target_company("payment_entry", "payment-1") == "cacao"
    assert service._target_company("gl_entry", "gl-1") == "cacao"
    with pytest.raises(service.BankReconciliationError, match="no existe"):
        service._target_amount("payment_entry", "missing")
    with pytest.raises(service.BankReconciliationError, match="no soportado"):
        service._target_amount("unsupported", "target")
    with pytest.raises(service.BankReconciliationError, match="no existe"):
        service._target_company("gl_entry", "missing")


def test_cancelled_or_secondary_ledger_gl_entries_are_not_eligible(monkeypatch) -> None:
    """Bank reconciliation rejects cancelled, reversed and secondary-ledger GL."""
    cancelled = SimpleNamespace(company="cacao", is_cancelled=True, is_reversal=False, ledger_id="PRIMARY")
    with pytest.raises(service.BankReconciliationError, match="cancelada"):
        service._validate_gl_entry_eligibility(cancelled)

    reversed_entry = SimpleNamespace(company="cacao", is_cancelled=False, is_reversal=True, ledger_id="PRIMARY")
    with pytest.raises(service.BankReconciliationError, match="cancelada"):
        service._validate_gl_entry_eligibility(reversed_entry)

    monkeypatch.setattr(service, "primary_ledger_id", lambda company: "PRIMARY")
    secondary = SimpleNamespace(company="cacao", is_cancelled=False, is_reversal=False, ledger_id="SECONDARY")
    with pytest.raises(service.BankReconciliationError, match="libro primario"):
        service._validate_gl_entry_eligibility(secondary)


def test_validate_reconciliation_match_accepts_gl_and_payment_targets(monkeypatch) -> None:
    """Valida los dos tipos de destino sin mezclar sus reglas específicas."""
    transaction = SimpleNamespace(
        id="bank-1", bank_account_id="account-1", company="cacao", deposit=Decimal("100"), withdrawal=Decimal("0")
    )
    gl_entry = SimpleNamespace(account_id="bank-gl", bank_account_id="account-1")
    payment = SimpleNamespace(
        bank_account_id="account-1",
        target_bank_account_id=None,
        payment_type="receive",
    )

    def fake_get(model, identifier, **kwargs):
        del kwargs
        if model is service.BankTransaction:
            return transaction
        if model is service.GLEntry:
            return gl_entry if identifier == "gl-1" else None
        if model is service.PaymentEntry:
            return payment if identifier == "payment-1" else None
        return None

    monkeypatch.setattr(service.database.session, "get", fake_get)
    monkeypatch.setattr(service, "_bank_company", lambda _transaction: "cacao")
    monkeypatch.setattr(service, "_target_company", lambda _type, _id: "cacao")
    monkeypatch.setattr(service, "_lock_reconciliation_target", lambda _type, _id: None)
    monkeypatch.setattr(service, "_bank_gl_account_id", lambda _transaction: "bank-gl")
    monkeypatch.setattr(service, "_validate_gl_entry_eligibility", lambda _entry: None)

    gl_match = SimpleNamespace(
        allocated_amount=Decimal("10"), bank_transaction_id="bank-1", target_type="gl_entry", target_id="gl-1"
    )
    payment_match = SimpleNamespace(
        allocated_amount=Decimal("10"), bank_transaction_id="bank-1", target_type="payment_entry", target_id="payment-1"
    )

    assert service._validate_reconciliation_match(match=gl_match, company="cacao") is transaction
    assert service._validate_reconciliation_match(match=payment_match, company="cacao") is transaction


def test_payment_link_population_only_sets_empty_bank_transaction() -> None:
    """Relaciona una transacción con pago una sola vez."""
    transaction = SimpleNamespace(payment_entry_id=None)
    match = SimpleNamespace(bank_transaction_id="bank-1", target_type="payment_entry", target_id="payment-1")
    service._populate_payment_entry_id(transaction, "bank-1", [match])
    assert transaction.payment_entry_id == "payment-1"
    service._populate_payment_entry_id(transaction, "bank-1", [SimpleNamespace(target_type="gl_entry")])
    assert transaction.payment_entry_id == "payment-1"
