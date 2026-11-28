# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1230: confirmar una conciliación recalcula sus cifras al corte.

Un gasto contabilizado después de crear el borrador debe actualizar el
efectivo esperado y la diferencia antes de fijar la conciliación.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.bancos.services import (
    create_petty_cash_reconciliation,
    reconcile_petty_cash,
)
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    PettyCashAccount,
    database,
)

FECHA = date(2026, 5, 15)


def _fund() -> str:
    """Crea un fondo de caja chica sobre la cuenta de caja del escenario."""
    account = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
    fund = PettyCashAccount(
        company="cacao",
        account_id=account.id,
        name="Caja 1230",
        currency="NIO",
        float_amount=Decimal("100"),
        is_default=False,
        is_active=True,
    )
    database.session.add(fund)
    database.session.flush()
    return str(fund.id)


def _gl(account_id: str, debit: Decimal, credit: Decimal, reference: str) -> None:
    """Registra un movimiento GL del fondo en el libro primario."""
    book = database.session.execute(select(Book).where(Book.entity == "cacao", Book.is_primary.is_(True))).scalar_one()
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book.id,
            account_id=account_id,
            debit=debit,
            credit=credit,
            is_cancelled=False,
            is_reversal=False,
            posting_date=FECHA,
            voucher_type="petty_cash_expense" if credit > 0 else "petty_cash_voucher",
            voucher_id=reference,
        )
    )
    database.session.flush()


def test_confirmacion_recalcula_el_efectivo_esperado(entorno_contable_aislado):
    """Un gasto posterior al borrador cambia expected_cash y exige explicación."""
    app = entorno_contable_aislado.app
    with app.app_context():
        fund_id = _fund()
        account_id = str(database.session.get(PettyCashAccount, fund_id).account_id)
        _gl(account_id, Decimal("100"), Decimal("0"), "FUND-1230")
        reconciliation = create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fund_id,
            reconciliation_date=FECHA,
            counted_cash=Decimal("100"),
        )
        assert reconciliation.expected_cash == Decimal("100.00000000")
        assert reconciliation.difference == Decimal("0E-8")

        _gl(account_id, Decimal("0"), Decimal("30"), "EXP-1230")
        database.session.commit()
        with pytest.raises(ValueError, match="explicacion"):
            reconcile_petty_cash(reconciliation)
        database.session.rollback()

        reconciliation = database.session.get(type(reconciliation), reconciliation.id)
        reconciliation.explanation = "Faltante por gasto registrado"
        confirmed = reconcile_petty_cash(reconciliation)

        assert confirmed.status == "conciliado"
        assert confirmed.docstatus == 1
        assert confirmed.expected_cash == Decimal("70.00000000")
        assert confirmed.difference == Decimal("30.00000000")


def test_confirmacion_sin_cambios_conserva_las_cifras(entorno_contable_aislado):
    """Sin movimientos nuevos la confirmación mantiene el snapshot."""
    app = entorno_contable_aislado.app
    with app.app_context():
        fund_id = _fund()
        account_id = str(database.session.get(PettyCashAccount, fund_id).account_id)
        _gl(account_id, Decimal("100"), Decimal("0"), "FUND-1230-B")
        reconciliation = create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fund_id,
            reconciliation_date=FECHA,
            counted_cash=Decimal("100"),
        )

        confirmed = reconcile_petty_cash(reconciliation)

        assert confirmed.expected_cash == Decimal("100.00000000")
        assert confirmed.difference == Decimal("0E-8")
        assert confirmed.status == "conciliado"
