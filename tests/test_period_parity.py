# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de paridad de filtros por período contable completo en reportes.

Cubre el criterio de aceptación del issue: el reporte de Contabilidad debe
resolver exactamente el mismo conjunto con ``accounting_period_id`` que la
ventana ``[AccountingPeriod.start, AccountingPeriod.end]`` inclusiva, y
neutralizar los documentos fuera de período (antes y después).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

ACCOUNTS: tuple[tuple[str, str, str, str | None], ...] = (
    ("1.01", "Caja", "Activo", "cash"),
    ("4.01", "Ventas", "Ingresos", None),
)

# (fecha, voucher, cuenta_debe, cuenta_haber, importe) alrededor de 01-2026
ENTRIES: tuple[tuple[str, str, str, str, str], ...] = (
    ("2025-12-31", "B-ANTES", "4.01", "1.01", "10"),
    ("2026-01-01", "P-INICIO", "1.01", "4.01", "20"),
    ("2026-01-15", "P-MEDIO", "1.01", "4.01", "30"),
    ("2026-01-31", "P-FIN", "1.01", "4.01", "40"),
    ("2026-02-01", "B-DESPUES", "4.01", "1.01", "50"),
)


@pytest.fixture()
def parity_app():
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
        user = User(user="parity-user", name="Parity User", classification="admin", active=True)
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
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="02-2026",
                    enabled=False,
                    is_closed=True,
                    start=date(2026, 2, 1),
                    end=date(2026, 2, 28),
                ),
            ]
        )
        database.session.commit()
        yield app


def _seed(parity_app) -> None:
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    ids: dict[str, str] = {}
    for code, name, classification, account_type in ACCOUNTS:
        account = Accounts(
            entity="cacao",
            code=code,
            name=name,
            active=True,
            enabled=True,
            classification=classification,
            account_type=account_type,
        )
        database.session.add(account)
        database.session.flush()
        ids[code] = account.id
    book_id = database.session.execute(database.select(Book.id).filter_by(code="FISC")).scalar_one()
    rows = []
    for iso_date, voucher, debit_code, credit_code, amount in ENTRIES:
        common = {
            "posting_date": date.fromisoformat(iso_date),
            "company": "cacao",
            "ledger_id": book_id,
            "voucher_type": "journal_entry",
            "voucher_id": voucher,
            "is_cancelled": False,
            "is_reversal": False,
        }
        rows.append(
            GLEntry(account_id=ids[debit_code], account_code=debit_code, debit=Decimal(amount), credit=Decimal("0"), **common)
        )
        rows.append(
            GLEntry(
                account_id=ids[credit_code], account_code=credit_code, debit=Decimal("0"), credit=Decimal(amount), **common
            )
        )
    database.session.add_all(rows)
    database.session.commit()


def _account_movement_post_dates(parity_app, period_from: str | None, period_to: str | None) -> set[date]:
    from cacao_accounting.database import AccountingPeriod, database
    from cacao_accounting.reportes.services import FinancialReportFilters, get_account_movement_detail

    period_from_id = None
    period_to_id = None
    if period_from:
        from_row = database.session.execute(
            database.select(AccountingPeriod).where(AccountingPeriod.name == period_from)
        ).scalar_one()
        period_from_id = str(from_row.id)
        period_to_id = period_from_id
        if period_to:
            to_row = database.session.execute(
                database.select(AccountingPeriod).where(AccountingPeriod.name == period_to)
            ).scalar_one()
            period_to_id = str(to_row.id)
    report = get_account_movement_detail(
        FinancialReportFilters(
            company="cacao", ledger="FISC", period_from=period_from_id, period_to=period_to_id, page_size=500
        )
    )
    dates: set[date] = set()
    for row in report.rows:
        value = row.values.get("posting_date")
        if isinstance(value, date):
            dates.add(value)
    return dates


def test_account_movement_period_is_uniform_inclusive(parity_app) -> None:
    """Un solo período incluye primer día, medio y último día; excluye antes y después."""
    _seed(parity_app)
    dates = _account_movement_post_dates(parity_app, "01-2026", "01-2026")
    assert date(2026, 1, 1) in dates
    assert date(2026, 1, 15) in dates
    assert date(2026, 1, 31) in dates
    assert date(2025, 12, 31) not in dates
    assert date(2026, 2, 1) not in dates


def test_account_movement_range_spans_periods(parity_app) -> None:
    """El rango 01-2026 → 02-2026 abarca el primer día del inicial y el último del final."""
    _seed(parity_app)
    dates = _account_movement_post_dates(parity_app, "01-2026", "02-2026")
    assert date(2026, 1, 1) in dates
    assert date(2026, 1, 31) in dates
    assert date(2026, 2, 1) in dates
    assert date(2025, 12, 31) not in dates


def test_account_movement_without_period_is_unfiltered(parity_app) -> None:
    """Sin filtro de período el reporte conserva su comportamiento (incluye todo)."""
    _seed(parity_app)
    dates = _account_movement_post_dates(parity_app, None, None)
    assert date(2025, 12, 31) in dates
    assert date(2026, 2, 1) in dates


def test_account_movement_export_csv_uses_same_period(parity_app) -> None:
    """La exportación CSV usa exactamente el mismo período que la vista."""
    from cacao_accounting.database import AccountingPeriod, User, database

    _seed(parity_app)
    user = User.query.filter_by(user="parity-user").first()
    period = database.session.execute(database.select(AccountingPeriod).where(AccountingPeriod.name == "01-2026")).scalar_one()
    client = parity_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True
    url = (
        "/reports/account-movement"
        f"?company=cacao&ledger=FISC&accounting_period_from={period.id}&accounting_period_to={period.id}&export=csv"
    )
    response = client.get(url)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "P-INICIO" in text
    assert "P-MEDIO" in text
    assert "P-FIN" in text
    assert "B-ANTES" not in text
    assert "B-DESPUES" not in text
