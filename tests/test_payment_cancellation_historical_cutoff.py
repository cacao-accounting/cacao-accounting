# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El detalle bancario respeta el corte histórico de pagos cancelados."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import Bank, BankAccount, DocumentTransition, PaymentEntry, User, database
from cacao_accounting.reportes.services import BankingFilters, _process_payment_entries


def test_detalle_incluye_pago_hasta_su_fecha_efectiva_de_cancelacion(entorno_contable_aislado):
    """Un pago cancelado después del corte permanece en el detalle histórico."""
    app = entorno_contable_aislado.app
    with app.app_context():
        bank = Bank(name="Banco corte de cancelación", is_active=True)
        database.session.add(bank)
        database.session.flush()
        bank_account = BankAccount(
            bank_id=bank.id,
            company="cacao",
            account_name="Cuenta histórica",
            currency="NIO",
        )
        payment = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=2,
            payment_type="receive",
            bank_account_id=bank_account.id,
            currency="NIO",
            received_amount=Decimal("100"),
        )
        database.session.add(bank_account)
        database.session.flush()
        payment.bank_account_id = bank_account.id
        database.session.add(payment)
        database.session.flush()
        actor_id = database.session.execute(select(User.id).where(User.classification == "admin").limit(1)).scalar_one()
        database.session.add(
            DocumentTransition(
                source_type="payment_entry",
                source_id=payment.id,
                transition_type="cancellation",
                company="cacao",
                posting_date=date(2026, 5, 20),
                accounting_period_id="P2026-05",
                actor_user_id=actor_id,
                reason="Registro heredado para corte histórico",
            )
        )
        database.session.flush()

        bank_accounts = {bank_account.id: bank_account}
        before_cancel, before_incoming, _ = _process_payment_entries(
            BankingFilters(company="cacao", date_from=date(2026, 5, 1), date_to=date(2026, 5, 15)),
            bank_accounts,
            {},
        )
        after_cancel, after_incoming, _ = _process_payment_entries(
            BankingFilters(company="cacao", date_from=date(2026, 5, 1), date_to=date(2026, 5, 20)),
            bank_accounts,
            {},
        )

    assert len(before_cancel) == 1
    assert before_incoming == Decimal("100")
    assert after_cancel == []
    assert after_incoming == Decimal("0")
