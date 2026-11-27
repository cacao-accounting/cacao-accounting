# SPDX-License-Identifier: Apache-2.0
"""#1498: no desactivar caja chica con vales entregados pendientes de liquidacion."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.database import Accounts, PettyCashAccount, PettyCashVoucher, database
from cacao_accounting.bancos.services import toggle_petty_cash_active


def test_toggle_petty_cash_active_rejects_open_delivered_voucher(app):
    with app.app_context():
        fund = database.session.execute(database.select(PettyCashAccount).limit(1)).scalar_one_or_none()
        if fund is None:
            acct = Accounts(
                entity="cacao",
                code="1.1.1.01.1498",
                name="Caja chica 1498",
                account_type="petty_cash",
                group=False,
                active=True,
                enabled=True,
            )
            database.session.add(acct)
            database.session.flush()
            fund = PettyCashAccount(company="cacao", account_id=acct.id, name="Caja", is_active=True, currency="NIO")
            database.session.add(fund)
            database.session.flush()
        fund.is_active = True
        voucher = PettyCashVoucher(
            company=fund.company,
            petty_cash_id=fund.id,
            amount=Decimal("10.00"),
            concept="Vale",
            voucher_status="entregado",
            status="active",
        )
        database.session.add(voucher)
        database.session.commit()

        with pytest.raises(ValueError, match="vales"):
            toggle_petty_cash_active(fund)
        database.session.refresh(fund)
        assert fund.is_active is True
