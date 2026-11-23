# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1886: la conciliación de caja chica compara importes en una sola moneda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.bancos.services import _petty_cash_reconciliation_derived_values
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    PettyCashAccount,
    PettyCashVoucher,
    database,
)

FECHA = date(2026, 5, 15)
_FONDOS_CREADOS: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def _limpia_fondos(app):
    """Elimina los fondos creados para no contaminar la base compartida del worker."""
    yield
    with app.app_context():
        for fondo_id, account_id in _FONDOS_CREADOS:
            database.session.execute(database.delete(PettyCashVoucher).where(PettyCashVoucher.petty_cash_id == fondo_id))
            database.session.execute(database.delete(GLEntry).where(GLEntry.account_id == account_id))
            fondo = database.session.get(PettyCashAccount, fondo_id)
            if fondo is not None:
                database.session.delete(fondo)
                database.session.flush()
            database.session.execute(database.delete(Accounts).where(Accounts.id == account_id))
            database.session.commit()
        _FONDOS_CREADOS.clear()


def _asegurar_moneda(code: str) -> None:
    """Crea la moneda de prueba si el fixture no la sembró."""
    from cacao_accounting.database import Currency

    if database.session.execute(select(Currency).filter_by(code=code)).scalar_one_or_none() is None:
        database.session.add(Currency(code=code, name=code, decimals=2, active=True))
        database.session.flush()


def _fondo_usd(company: str = "cacao", currency: str = "USD") -> PettyCashAccount:
    """Crea un fondo de caja chica en la moneda indicada."""
    sufijo = uuid4().hex[:6]
    _asegurar_moneda(currency)
    cuenta = Accounts(
        entity=company,
        code=f"PC{sufijo}",
        name=f"Caja chica {sufijo}",
        classification="asset",
        account_type="cash",
    )
    database.session.add(cuenta)
    database.session.flush()
    fondo = PettyCashAccount(
        company=company,
        account_id=cuenta.id,
        name=f"Fondo {currency} {sufijo}",
        currency=currency,
        float_amount=Decimal("100"),
    )
    database.session.add(fondo)
    database.session.flush()
    _FONDOS_CREADOS.append((fondo.id, cuenta.id))
    return fondo


def _asiento_en_libro(fondo: PettyCashAccount, amount: Decimal) -> None:
    """Registra el saldo del fondo en el libro primario NIO."""
    libro = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
    database.session.add(
        GLEntry(
            company=fondo.company,
            account_id=fondo.account_id,
            account_code=fondo.account_id,
            ledger_id=libro.id,
            posting_date=FECHA,
            debit=amount,
            credit=Decimal("0"),
            voucher_type="journal_entry",
            voucher_id=f"v-{uuid4().hex[:8]}",
        )
    )


def test_convierte_el_saldo_del_libro_a_la_moneda_del_fondo(app, entorno_contable):
    """365 NIO de GL y un vale de 10 USD dejan un esperado de 0 USD (tasa 36.5)."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd()
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.add(
            PettyCashVoucher(
                petty_cash_id=fondo.id,
                concept="Vale entregado",
                amount=Decimal("10"),
                voucher_status="entregado",
                posting_date=FECHA,
            )
        )
        database.session.commit()

        valores = _petty_cash_reconciliation_derived_values(fondo, FECHA)

        assert valores["ledger_balance"] == Decimal("10.0000")
        assert valores["open_vouchers"] == Decimal("10")
        assert valores["expected_cash"] == Decimal("0")


def test_bloquea_la_conciliacion_si_falta_la_tasa(app, entorno_contable):
    """Sin tasa entre el libro y el fondo no se restan monedas distintas."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd(currency="EUR")
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.commit()

        with pytest.raises(ValueError, match="tipo de cambio"):
            _petty_cash_reconciliation_derived_values(fondo, FECHA)
