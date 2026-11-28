# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión para autorizar el cierre bancario con diferencia bajo controles internos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.bancos import services as bank_services
from cacao_accounting.database import Bank, BankAccount, BankTransaction, Reconciliation, database


def test_ajuste_de_diferencia_cierra_transaccion_con_guard_activo(entorno_contable_aislado, monkeypatch) -> None:
    """El servicio autoriza el flag de conciliación y conserva todos los cambios en la sesión."""
    app = entorno_contable_aislado.app
    append_calls = []
    with app.app_context():
        app.config["INTERNAL_CONTROLS_ENFORCE"] = True
        bank = Bank(name=f"Banco diferencia {uuid4().hex[:8]}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            bank_id=bank.id,
            company="cacao",
            account_name="Cuenta con diferencia",
            account_no=f"DIFF-{uuid4().hex[:8]}",
            currency="NIO",
            is_active=True,
        )
        database.session.add(account)
        database.session.flush()
        transaction = BankTransaction(
            bank_account_id=account.id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("100"),
            withdrawal=Decimal("0"),
            description="Depósito con diferencia",
            is_reconciled=False,
        )
        reconciliation = Reconciliation(company="cacao", recon_date=date(2026, 5, 15), recon_type="bank")
        database.session.add_all([transaction, reconciliation])
        database.session.commit()
        transaction_id = transaction.id

        monkeypatch.setattr(
            bank_services,
            "_submit_bank_difference_journal",
            lambda *_args, **_kwargs: SimpleNamespace(id="journal-difference"),
        )
        monkeypatch.setattr(
            bank_services,
            "_bank_difference_gl_entry",
            lambda *_args, **_kwargs: (account, SimpleNamespace(id="gl-difference")),
        )
        monkeypatch.setattr(
            bank_services,
            "_append_bank_difference_item",
            lambda *args: append_calls.append(args),
        )

        bank_services._post_bank_difference_adjustment(
            reconciliation.id,
            transaction,
            Decimal("2"),
            user_id="test-user",
        )
        database.session.flush()
        assert len(append_calls) == 1
        assert transaction.is_reconciled is True

        database.session.commit()
        database.session.expire_all()
        assert database.session.get(BankTransaction, transaction_id).is_reconciled is True
