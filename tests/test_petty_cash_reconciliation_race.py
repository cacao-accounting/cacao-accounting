# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2082: la conciliación de caja chica serializa su creación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.bancos import services as bank_services
from cacao_accounting.database import Accounts, PettyCashAccount, database


def test_creacion_serializa_y_rechaza_duplicado(app, entorno_contable, monkeypatch):
    """El lock precede al chequeo y la segunda creación es un ValueError."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name=f"Caja {suffix}",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        fondo_id = fondo.id

    llamadas: list[tuple] = []
    original = bank_services.lock_default_scope

    def tracking(*args, **kwargs):
        llamadas.append(args)
        original(*args, **kwargs)

    monkeypatch.setattr(bank_services, "lock_default_scope", tracking)
    with app.app_context():
        bank_services.create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo_id,
            reconciliation_date=date(2026, 5, 15),
            counted_cash=Decimal("100"),
        )
        with pytest.raises(ValueError, match="Ya existe una conciliación"):
            bank_services.create_petty_cash_reconciliation(
                company="cacao",
                petty_cash_id=fondo_id,
                reconciliation_date=date(2026, 5, 15),
                counted_cash=Decimal("100"),
            )

    assert any(args and args[0] == "petty_cash_reconciliation" for args in llamadas)
