# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Bank reconciliation diagnostics stay within the requested company."""

from datetime import date

from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Entity,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    database,
)
from cacao_accounting.reportes.services import _reconciliation_item_diagnostics, get_reconciliation_report


def test_reconciliation_item_diagnostics_excludes_other_companies(app):
    """Orphan and missing-context diagnostics use the parent reconciliation company."""
    with app.app_context():
        for code in ("alpha", "beta"):
            if database.session.get(Entity, code) is None:
                database.session.add(
                    Entity(
                        code=code,
                        name=code.title(),
                        company_name=f"{code.title()} SA",
                        tax_id=f"TEST-{code.upper()}",
                        currency="NIO",
                        enabled=True,
                        status="activo",
                    )
                )
        database.session.flush()
        bank = Bank(name="Banco Alpha")
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            company="alpha",
            bank_id=bank.id,
            account_name="Cuenta Alpha",
            currency="NIO",
        )
        database.session.add(bank_account)
        database.session.flush()
        payment = PaymentEntry(
            company="alpha",
            payment_type="receive",
            docstatus=0,
            posting_date=date(2026, 10, 31),
            bank_account_id=bank_account.id,
        )
        database.session.add(payment)
        database.session.flush()
        database.session.add(
            BankTransaction(
                id="txn-alpha",
                identity_key="test-transaction",
                bank_account_id=bank_account.id,
                posting_date=date(2026, 10, 31),
                deposit=40,
                payment_entry_id=payment.id,
            )
        )
        alpha_reconciliation = Reconciliation(company="alpha", recon_date=date(2026, 10, 31), recon_type="bank")
        beta_reconciliation = Reconciliation(company="beta", recon_date=date(2026, 10, 31), recon_type="bank")
        database.session.add_all([alpha_reconciliation, beta_reconciliation])
        database.session.flush()
        database.session.add_all(
            [
                ReconciliationItem(
                    reconciliation_id=alpha_reconciliation.id,
                    reference_type="bank_transaction",
                    reference_id="missing-alpha",
                    source_type="bank_transaction",
                    source_id="missing-alpha",
                    target_type="payment_entry",
                    target_id="payment-alpha",
                    reconciliation_date=date(2026, 10, 31),
                    amount=75,
                    allocated_amount=75,
                    status="reconciled",
                    currency="NIO",
                ),
                ReconciliationItem(
                    reconciliation_id=beta_reconciliation.id,
                    reference_type="bank_transaction",
                    reference_id="missing-beta-secret",
                    source_type="bank_transaction",
                    source_id="missing-beta-secret",
                    target_type="payment_entry",
                    target_id="payment-beta-secret",
                    reconciliation_date=date(2026, 10, 31),
                    amount=125,
                    allocated_amount=125,
                    status="reconciled",
                    currency="NIO",
                ),
                ReconciliationItem(
                    reconciliation_id=alpha_reconciliation.id,
                    reference_type="bank_transaction",
                    reference_id="txn-alpha",
                    source_type="bank_transaction",
                    source_id="txn-alpha",
                    target_type="payment_entry",
                    target_id="payment-alpha-context",
                    reconciliation_date=date(2026, 10, 31),
                    amount=40,
                    allocated_amount=40,
                    status="reconciled",
                    currency=None,
                ),
                ReconciliationItem(
                    reconciliation_id=beta_reconciliation.id,
                    reference_type="bank_transaction",
                    reference_id="txn-beta-secret",
                    source_type="bank_transaction",
                    source_id="txn-beta-secret",
                    target_type="payment_entry",
                    target_id="payment-beta-context-secret",
                    reconciliation_date=date(2026, 10, 31),
                    amount=60,
                    allocated_amount=60,
                    status="reconciled",
                    currency=None,
                ),
            ]
        )
        database.session.flush()

        helper_rows = _reconciliation_item_diagnostics({"txn-alpha"}, "alpha")
        report = get_reconciliation_report("alpha")
        rows = [row for row in report.rows if row.values["recon_type"] == "bank_diagnostic"]

    expected_diagnostics = {
        ("orphan_reconciliation_item", "missing-alpha"),
        ("reconciliation_item_missing_context", "txn-alpha"),
    }
    assert {(row.values["status"], row.values["source_id"]) for row in helper_rows} == expected_diagnostics
    assert {(row.values["status"], row.values["source_id"]) for row in rows} == {
        *expected_diagnostics,
    }
    assert all("beta-secret" not in str(row.values) for row in rows)
