# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1970: los reportes incluyen la reversión interperíodo vigente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.cancellation_scope import effective_gl_scope, ordinary_gl_scope
from cacao_accounting.database import AccountingPeriod, Book, GLEntry, database


def _periodo(period_id: str, start: date, end: date) -> AccountingPeriod:
    return AccountingPeriod(
        id=period_id,
        entity="cacao",
        fiscal_year_id="FY2026",
        name=period_id,
        start=start,
        end=end,
        enabled=True,
        is_closed=False,
    )


def _libro() -> str:
    return database.session.execute(database.select(Book.id).filter_by(code="DEFAULT_BOOK")).scalar_one()


def _entrada(period: str, fecha: date, **extra) -> GLEntry:
    datos = {
        "company": "cacao",
        "account_code": "5201",
        "debit": Decimal("10"),
        "credit": Decimal("0"),
        "posting_date": fecha,
        "accounting_period_id": period,
        "ledger_id": _libro(),
        "voucher_type": "journal_entry",
        "voucher_id": f"V-{period}-{fecha.day}",
    }
    datos.update(extra)
    return GLEntry(**datos)


def test_incluye_reversion_interperiodo_y_excluye_la_del_mismo_periodo(app, entorno_contable):
    """El corte efectivo conserva la contrapartida vigente del período nuevo."""
    with app.app_context():
        database.session.add(_periodo("P2026-11", date(2026, 11, 1), date(2026, 11, 30)))
        database.session.flush()

        original_oct = _entrada("P2026-05", date(2026, 5, 10), is_cancelled=True)
        database.session.add(original_oct)
        database.session.flush()

        vigente = _entrada("P2026-05", date(2026, 5, 11))
        contra_nov = _entrada("P2026-11", date(2026, 11, 1), is_reversal=True, reversal_of=original_oct.id)
        anulada = _entrada("P2026-05", date(2026, 5, 12), is_cancelled=True)
        database.session.add_all([vigente, contra_nov, anulada])
        database.session.flush()

        mismo_periodo = _entrada("P2026-05", date(2026, 5, 13), is_reversal=True, reversal_of=vigente.id)
        database.session.add(mismo_periodo)
        database.session.commit()

        seleccionados = set(database.session.execute(database.select(GLEntry.id).where(*effective_gl_scope())).scalars().all())

        assert vigente.id in seleccionados
        assert contra_nov.id in seleccionados
        assert original_oct.id not in seleccionados
        assert anulada.id not in seleccionados
        assert mismo_periodo.id not in seleccionados

        # El alcance anterior (solo originales vivos) perdía la contrapartida
        # interperíodo: queda fijado como regresión del defecto.
        anteriores = set(database.session.execute(database.select(GLEntry.id).where(*ordinary_gl_scope())).scalars().all())
        assert contra_nov.id not in anteriores
