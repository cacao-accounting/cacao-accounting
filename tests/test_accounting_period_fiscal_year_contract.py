# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1287: el período contable exige un año fiscal válido de la compañía.

Un período sin año fiscal, con un año de otra compañía o con un año que no
cubre su rango dejaría evidencia GL con ``fiscal_year_id`` nulo y rompería la
anulación posterior. El posteo debe fallar de forma cerrada.
"""

from datetime import date

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft, submit_journal
from cacao_accounting.database import AccountingPeriod, Entity, FiscalYear, GLEntry, User, database
from cacao_accounting.document_identifiers import IdentifierConfigurationError, resolve_accounting_period


def _actor_id() -> str:
    """Devuelve el usuario administrador del escenario."""
    return str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one())


def _period(code: str, start: date, end: date, fiscal_year_id: str | None) -> AccountingPeriod:
    """Crea un período de prueba con o sin año fiscal enlazado."""
    period = AccountingPeriod(
        id=code,
        entity="cacao",
        fiscal_year_id=fiscal_year_id,
        name=code,
        start=start,
        end=end,
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    database.session.flush()
    return period


def _other_company() -> Entity:
    """Crea una compañía alterna para enlazar un año fiscal ajeno."""
    entity = Entity(
        code="OTRA",
        company_name="Compañía Ajena 1287",
        name="Compañía Ajena 1287",
        tax_id="TAX-1287-OTRA",
        currency="NIO",
        enabled=True,
    )
    database.session.add(entity)
    database.session.flush()
    return entity


def test_periodo_sin_anio_fiscal_no_resuelve(entorno_contable_aislado):
    """Un período sin año fiscal bloquea la resolución y el posteo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _period("P2026-09", date(2026, 9, 1), date(2026, 9, 30), None)
        database.session.commit()

        with pytest.raises(IdentifierConfigurationError, match="año fiscal válido"):
            resolve_accounting_period("cacao", date(2026, 9, 15))

        journal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-09-15",
                "books": ["DEFAULT_BOOK"],
                "transaction_currency": "NIO",
                "lines": [
                    {"order": 1, "account": "1101", "debit": "100", "credit": ""},
                    {"order": 2, "account": "1102", "debit": "", "credit": "100"},
                ],
            },
            user_id=_actor_id(),
            assign_identifier=False,
        )
        with pytest.raises(JournalValidationError, match="año fiscal válido"):
            submit_journal(journal.id, user_id=_actor_id())

        database.session.refresh(journal)
        assert journal.status == "draft"
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).scalar_one_or_none() is None
        )


def test_periodo_con_anio_fiscal_de_otra_compania_no_resuelve(entorno_contable_aislado):
    """El año fiscal enlazado debe pertenecer a la compañía del período."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _other_company()
        foreign_year = FiscalYear(
            entity="OTRA",
            name="AF-OTRA-2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(foreign_year)
        database.session.flush()
        _period("P2026-10", date(2026, 10, 1), date(2026, 10, 31), foreign_year.id)
        database.session.commit()

        with pytest.raises(IdentifierConfigurationError, match="año fiscal válido"):
            resolve_accounting_period("cacao", date(2026, 10, 15))


def test_anio_fiscal_debe_cubrir_el_rango_del_periodo(entorno_contable_aislado):
    """Un año fiscal que termina antes del período no lo respalda."""
    app = entorno_contable_aislado.app
    with app.app_context():
        short_year = FiscalYear(
            entity="cacao",
            name="AF-CACAO-CORTO",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 6, 30),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(short_year)
        database.session.flush()
        _period("P2026-11", date(2026, 11, 1), date(2026, 11, 30), short_year.id)
        database.session.commit()

        with pytest.raises(IdentifierConfigurationError, match="año fiscal válido"):
            resolve_accounting_period("cacao", date(2026, 11, 15))


def test_periodo_con_anio_fiscal_valido_resuelve(entorno_contable_aislado):
    """Con un año de la compañía que cubre el período, la resolución continúa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        fiscal_year_id = database.session.get(FiscalYear, "FY2026").id
        period = _period("P2026-12", date(2026, 12, 1), date(2026, 12, 31), fiscal_year_id)
        database.session.commit()

        resolved = resolve_accounting_period("cacao", date(2026, 12, 15))

        assert resolved.id == period.id
        assert resolved.fiscal_year_id == fiscal_year_id
