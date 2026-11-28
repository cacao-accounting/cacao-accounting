# SPDX-License-Identifier: Apache-2.0
"""#1498: desactivar caja chica conserva los vales existentes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.bancos.services import toggle_petty_cash_active
from cacao_accounting.database import Accounts, PettyCashAccount, PettyCashVoucher, database


@pytest.mark.parametrize("estado", ["borrador", "entregado", "liquidado", "cancelado"])
def test_toggle_petty_cash_active_con_vales_existentes(entorno_contable_aislado, estado: str):
    """La desactivación no borra ni bloquea los vales ya creados."""
    app = entorno_contable_aislado.app
    with app.app_context():
        account = Accounts(
            entity="cacao",
            code="1.1.1.01.1498",
            name="Caja chica 1498",
            account_type="petty_cash",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(company="cacao", account_id=account.id, name="Caja", is_active=True, currency="NIO")
        database.session.add(fund)
        database.session.flush()
        voucher = PettyCashVoucher(
            company="cacao",
            petty_cash_id=fund.id,
            amount=Decimal("10.00"),
            concept="Vale",
            voucher_status=estado,
            status="anulado" if estado == "cancelado" else "active",
        )
        database.session.add(voucher)
        database.session.commit()

        toggle_petty_cash_active(fund)
        database.session.refresh(fund)
        database.session.refresh(voucher)

        assert fund.is_active is False
        assert voucher.voucher_status == estado
