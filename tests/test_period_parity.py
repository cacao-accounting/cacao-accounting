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


def test_account_movement_filters_by_period_dimension(parity_app) -> None:
    """La dimensión ``accounting_period_id`` gobierna sobre la fecha de publicación.

    Un asiento que pertenece al período 02-2026 pero cuya ``posting_date`` cae
    dentro de la ventana de 01-2026 (fecha mal asignada) NO debe aparecer al
    filtrar por 01-2026: el período es la identidad, no un rango de fechas.
    """
    from cacao_accounting.database import Accounts, AccountingPeriod, Book, GLEntry, database
    from cacao_accounting.reportes.services import FinancialReportFilters, get_account_movement_detail

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
    period_jan = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.name == "01-2026")
    ).scalar_one()
    period_feb = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.name == "02-2026")
    ).scalar_one()
    base = {
        "company": "cacao",
        "ledger_id": book_id,
        "voucher_type": "journal_entry",
        "is_cancelled": False,
        "is_reversal": False,
    }
    entries = [
        # Pertenece a 01-2026 y su fecha está dentro de la ventana.
        ("IN-FUERA-VENTANA-PERIODO", period_jan.id, date(2026, 1, 15), Decimal("10")),
        # Fecha dentro de la ventana de 01-2026, pero PERÍODO 02-2026 (fecha mal asignada).
        ("DENTRO-VENTANA-SESI", period_feb.id, date(2026, 1, 20), Decimal("20")),
        # Pertenece a 02-2026 y su fecha está dentro de 02-2026.
        ("EN-PERIODO-SESI", period_feb.id, date(2026, 2, 5), Decimal("30")),
    ]
    database.session.add_all(
        [
            GLEntry(
                account_id=ids["1.01"],
                account_code="1.01",
                debit=debit,
                credit=Decimal("0"),
                posting_date=posting_date,
                accounting_period_id=period_id,
                voucher_id=voucher_id,
                **base,
            )
            for voucher_id, period_id, posting_date, debit in entries
        ]
    )
    database.session.commit()
    jan_id = str(period_jan.id)
    report = get_account_movement_detail(
        FinancialReportFilters(company="cacao", ledger="FISC", period_from=jan_id, period_to=jan_id, page_size=500)
    )
    seen: set[str] = set()
    for row in report.rows:
        seen.add(str(row.values.get("document_no")))
    # Solo el asiento del período 01-2026; los otros 2 quedan fuera por dimensión.
    assert seen == {"IN-FUERA-VENTANA-PERIODO"}


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
