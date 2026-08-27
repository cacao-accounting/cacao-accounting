# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de la Sección 5 del issue: alcance de anulaciones por período.

Verifica que original y contrapartida de una anulación pertenezcan al mismo
período, se neutralicen en el saldo del período, se excluyan en la vista
ordinaria y sean reconstruibles en la vista de auditoría, sin borrar historia
con flags.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.reportes.services import FinancialReportFilters


@pytest.fixture()
def cancel_app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "testing",
        }
    )
    with app.app_context():
        from cacao_accounting.database import AccountingPeriod, Book, Entity, Modules, User, database

        database.create_all()
        user = User(user="cancel-user", name="Cancel User", classification="admin", active=True)
        user.password = b"x"
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                user,
                Book(
                    entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, default=True, currency="NIO"
                ),
                AccountingPeriod(
                    entity="cacao", name="01-2026", enabled=True, is_closed=True, start=date(2026, 1, 1), end=date(2026, 1, 31)
                ),
            ]
        )
        database.session.commit()
        yield app


def _seed_pair(cancel_app) -> dict[str, object]:
    """Crea un documento contabilizado y su par de reverso en el mismo período."""
    from sqlalchemy import select

    from cacao_accounting.database import Accounts, AccountingPeriod, GLEntry, database

    accounts: dict[str, str] = {}
    for code, name in (("1.01", "Caja"), ("4.01", "Ventas")):
        account = Accounts(
            entity="cacao", code=code, name=name, active=True, enabled=True, classification="Activo", account_type=None
        )
        database.session.add(account)
        database.session.flush()
        accounts[code] = account.id
    period = database.session.execute(select(AccountingPeriod).where(AccountingPeriod.name == "01-2026")).scalar_one()
    common: dict[str, object] = {
        "company": "cacao",
        "ledger_id": book_id(cancel_app),
        "voucher_type": "sales_invoice",
        "voucher_id": "DOC-1",
        "accounting_period_id": period.id,
        "fiscal_year_id": None,
        "posting_date": date(2026, 1, 15),
        "account_currency": "NIO",
        "company_currency": "NIO",
        "exchange_rate": Decimal("1"),
        "is_cancelled": False,
        "is_reversal": False,
    }
    original = [
        GLEntry(account_id=accounts["1.01"], account_code="1.01", debit=Decimal("100"), credit=Decimal("0"), **common),
        GLEntry(account_id=accounts["4.01"], account_code="4.01", debit=Decimal("0"), credit=Decimal("100"), **common),
    ]
    database.session.add_all(original)
    database.session.flush()
    reversal = []
    for entry in original:
        rev_common = {**common, "is_reversal": True, "reversal_of": entry.id, "remarks": "Reversion"}
        reversal.append(
            GLEntry(
                account_id=entry.account_id,
                account_code=entry.account_code,
                debit=entry.credit,
                credit=entry.debit,
                **rev_common,
            )
        )
    for entry in original:
        entry.is_cancelled = True
    database.session.add_all(reversal)
    database.session.commit()

    result: dict[str, object] = {
        "period_id": str(period.id),
        "original_ids": [str(e.id) for e in original],
        "reversal_ids": [str(e.id) for e in reversal],
    }
    return result


def book_id(cancel_app) -> str:
    from cacao_accounting.database import Book, database

    return database.session.execute(database.select(Book.id).filter_by(code="FISC")).scalar_one()


def _filters(status: str | None, include_cancellations: bool) -> FinancialReportFilters:
    return FinancialReportFilters(company="cacao", ledger="FISC", status=status, include_cancellations=include_cancellations)


def _query_entries(status: str | None, include_cancellations: bool) -> list:
    from sqlalchemy import select

    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.reportes.services import _apply_cancellation_scope, _apply_status_filter

    query = select(GLEntry).where(GLEntry.voucher_id == "DOC-1")
    query = _apply_status_filter(query, _filters(status, include_cancellations))
    query = _apply_cancellation_scope(query, _filters(status, include_cancellations))
    return list(database.session.execute(query).scalars().all())


def test_par_share_same_period(cancel_app) -> None:
    """Original y contrapartida comparten el mismo accounting_period_id."""
    result = _seed_pair(cancel_app)
    from sqlalchemy import select

    from cacao_accounting.database import GLEntry, database

    rows = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == "DOC-1")).scalars().all()
    assert rows
    assert {str(row.accounting_period_id) for row in rows} == {result["period_id"]}
    reverse_rows = [row for row in rows if row.is_reversal]
    assert all(str(row.accounting_period_id) == result["period_id"] for row in reverse_rows)


def test_ordinary_view_excludes_pair(cancel_app) -> None:
    """La vista ordinaria excluye el par anulado sin afectar el período."""
    _seed_pair(cancel_app)
    rows = _query_entries(status="submitted", include_cancellations=False)
    assert rows == []


def test_cancelled_scope_shows_originals(cancel_app) -> None:
    """El filtro 'cancelado' muestra los originales anulados pero no las contrapartidas."""
    _seed_pair(cancel_app)
    rows = _query_entries(status="cancelled", include_cancellations=False)
    assert rows
    assert all(row.is_cancelled and not row.is_reversal for row in rows)


def test_audit_view_includes_both_sides(cancel_app) -> None:
    """La vista de auditoría incluye ambos lados para reconstruir la anulación."""
    _seed_pair(cancel_app)
    rows = _query_entries(status=None, include_cancellations=True)
    assert rows
    assert len(rows) == 4
    assert any(row.is_reversal for row in rows)
    assert any(row.is_cancelled for row in rows)
    assert any(row.reversal_of for row in rows)


def test_append_only_net_is_zero(cancel_app) -> None:
    """El cálculo append-only del período es neutral (par se anula)."""
    from sqlalchemy import select

    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.ledger_queries import exclude_cancelled_gl_entries

    _seed_pair(cancel_app)
    query = exclude_cancelled_gl_entries(select(GLEntry).where(GLEntry.voucher_id == "DOC-1"))
    rows = list(database.session.execute(query).scalars().all())
    assert rows == []
