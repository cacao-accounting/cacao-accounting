# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del Estado de Flujo de Efectivo (NIC 7 indirecto) y su configuración."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def efe_app():
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
        user = User(user="efe-user", name="EFE User", classification="admin", active=True)
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
                    name="2026-01",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


ACCOUNTS: tuple[tuple[str, str, str, str | None], ...] = (
    ("1.01", "Caja", "Activo", "cash"),
    ("1.02", "Banco", "Activo", "bank"),
    ("1.03", "Clientes", "Activo", "receivable"),
    ("1.04", "Propiedad Planta y Equipo", "Activo", None),
    ("1.05", "Depreciación acumulada", "Activo", None),
    ("2.01", "Proveedores", "Pasivo", "payable"),
    ("2.02", "Préstamo Bancario", "Pasivo", None),
    ("3.01", "Capital Social", "Patrimonio", None),
    ("4.01", "Ventas", "Ingresos", None),
    ("5.01", "Gastos Operativos", "Gastos", None),
    ("5.02", "Depreciación del período", "Gastos", None),
)

ENTRIES: tuple[tuple[str, str, str, str, str], ...] = (
    # (fecha, voucher, cuenta_debe, cuenta_haber, importe)
    ("2025-12-20", "OPENING", "1.02", "3.01", "500"),
    ("2026-01-05", "V-1", "1.03", "4.01", "300"),
    ("2026-01-10", "V-2", "1.01", "1.03", "200"),
    ("2026-01-12", "P-1", "5.01", "2.01", "120"),
    ("2026-01-15", "PP-1", "2.01", "1.02", "80"),
    ("2026-01-20", "DEP-1", "5.02", "1.05", "30"),
    ("2026-01-21", "CAPEX-1", "1.04", "1.02", "100"),
    ("2026-01-25", "LOAN-1", "1.02", "2.02", "250"),
)

FULL_MAPPING: dict[str, str] = {
    "1.01": "cash",
    "1.02": "cash",
    "1.03": "operating",
    "1.04": "investing",
    "1.05": "operating",
    "2.01": "operating",
    "2.02": "financing",
    "3.01": "financing",
}


def _seed_chart(app) -> dict[str, str]:
    """Crea el catálogo de pruebas y devuelve código→account_id."""
    from cacao_accounting.database import Accounts, database

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
    database.session.commit()
    return ids


def _post_entries(app, account_ids: dict[str, str]) -> None:
    """Publica los comprobantes del escenario integral."""
    from cacao_accounting.database import Book, GLEntry, database

    book_id = database.session.execute(database.select(Book.id).filter_by(code="FISC")).scalar_one()
    rows = []
    for iso_date, voucher, debit_code, credit_code, amount in ENTRIES:
        common = {
            "posting_date": date.fromisoformat(iso_date),
            "company": "cacao",
            "ledger_id": book_id,
            "voucher_type": "journal_entry",
            "voucher_id": voucher,
        }
        rows.append(
            GLEntry(
                account_id=account_ids[debit_code],
                account_code=debit_code,
                debit=Decimal(amount),
                credit=Decimal("0"),
                **common,
            )
        )
        rows.append(
            GLEntry(
                account_id=account_ids[credit_code],
                account_code=credit_code,
                debit=Decimal("0"),
                credit=Decimal(amount),
                **common,
            )
        )
    database.session.add_all(rows)
    database.session.commit()


def _apply_mapping(mapping: dict[str, str], account_ids: dict[str, str]) -> None:
    from cacao_accounting.reportes.cash_flow import save_cash_flow_mappings

    save_cash_flow_mappings("cacao", {account_ids[code]: section for code, section in mapping.items()})
    from cacao_accounting.database import database

    database.session.commit()


def test_configuration_is_incomplete_without_mappings(efe_app) -> None:
    """El EFE se bloquea mientras existan cuentas de balance con movimiento sin clasificar."""
    from cacao_accounting.database import database
    from cacao_accounting.reportes.cash_flow import (
        get_cash_flow_configuration_status,
        get_cash_flow_statement,
    )
    from cacao_accounting.reportes.services import FinancialReportFilters

    account_ids = _seed_chart(efe_app)
    _post_entries(efe_app, account_ids)
    filters = FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-01")

    status = get_cash_flow_configuration_status(filters.company, filters.ledger, filters.accounting_period)

    assert not status.complete
    assert not status.has_cash_accounts
    pending_codes = {item["code"] for item in status.pending_accounts}
    # Solo exigen clasificación las cuentas de balance con movimiento dentro
    # de la ventana seleccionada; el capital solo movió antes del período.
    assert {"1.01", "1.03", "1.04", "2.01", "2.02"} <= pending_codes
    assert not {"4.01", "5.01", "3.01"} & pending_codes

    with pytest.raises(ValueError):
        get_cash_flow_statement(filters)
    database.session.rollback()


def test_cash_flow_statement_matches_cash_variation(efe_app) -> None:
    """Con cobertura completa las secciones cuadran contra la variación de efectivo."""
    from cacao_accounting.reportes.cash_flow import get_cash_flow_configuration_status, get_cash_flow_statement
    from cacao_accounting.reportes.services import FinancialReportFilters

    account_ids = _seed_chart(efe_app)
    _post_entries(efe_app, account_ids)
    _apply_mapping(FULL_MAPPING, account_ids)
    filters = FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-01")

    assert get_cash_flow_configuration_status(filters.company, filters.ledger, filters.accounting_period).complete

    report = get_cash_flow_statement(filters)
    totals = report.totals

    assert totals["net_profit"] == Decimal("150")
    assert totals["operating_adjustments"] == Decimal("-30")
    assert totals["operating"] == Decimal("120")
    assert totals["investing"] == Decimal("-100")
    assert totals["financing"] == Decimal("250")
    assert totals["net_change_cash"] == Decimal("270")
    assert totals["cash_opening"] == Decimal("500")
    assert totals["cash_closing"] == Decimal("770")
    assert totals["difference"] == Decimal("0")

    receivable_row = next(row for row in report.rows if row.values.get("account_code") == "1.03")
    assert receivable_row.values["section"] == "operating"
    assert receivable_row.values["amount"] == Decimal("-100")


def test_explicit_override_moves_account_between_sections(efe_app) -> None:
    """Un mapeo explícito distinto mueve el importe de sección sin romper el cuadre."""
    from cacao_accounting.reportes.cash_flow import get_cash_flow_statement
    from cacao_accounting.reportes.services import FinancialReportFilters

    account_ids = _seed_chart(efe_app)
    _post_entries(efe_app, account_ids)
    override = dict(FULL_MAPPING)
    override["1.03"] = "investing"
    _apply_mapping(override, account_ids)
    filters = FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-01")

    report = get_cash_flow_statement(filters)

    assert report.totals["operating_adjustments"] == Decimal("70")
    assert report.totals["operating"] == Decimal("220")
    assert report.totals["investing"] == Decimal("-200")
    assert report.totals["difference"] == Decimal("0")


def test_save_cash_flow_mappings_validates_input(efe_app) -> None:
    """Secciones o cuentas desconocidas se rechazan sin guardar nada."""
    from cacao_accounting.database import database
    from cacao_accounting.reportes.cash_flow import load_cash_flow_mappings, save_cash_flow_mappings

    account_ids = _seed_chart(efe_app)
    with pytest.raises(ValueError):
        save_cash_flow_mappings("cacao", {account_ids["1.01"]: "other"})
    with pytest.raises(ValueError):
        save_cash_flow_mappings("cacao", {"no-existe": "cash"})

    save_cash_flow_mappings("cacao", {account_ids["1.01"]: "cash", account_ids["1.03"]: ""})
    database.session.commit()
    assert load_cash_flow_mappings("cacao") == {account_ids["1.01"]: "cash"}

    save_cash_flow_mappings("cacao", {account_ids["1.01"]: "", account_ids["1.03"]: "operating"})
    database.session.commit()
    assert load_cash_flow_mappings("cacao") == {account_ids["1.03"]: "operating"}


def test_suggestion_is_visual_only(efe_app) -> None:
    """La sugerencia por account_type no crea mapeo alguno."""
    from cacao_accounting.database import Accounts, database
    from cacao_accounting.reportes.cash_flow import load_cash_flow_mappings, suggest_section

    account_ids = _seed_chart(efe_app)
    receivable = database.session.get(Accounts, account_ids["1.03"])
    assert suggest_section(receivable) == "operating"
    equity = database.session.get(Accounts, account_ids["3.01"])
    assert suggest_section(equity) == "financing"
    income = database.session.get(Accounts, account_ids["4.01"])
    assert suggest_section(income) is None
    assert load_cash_flow_mappings("cacao") == {}


def test_config_view_saves_overrides_and_unblocks_report(efe_app) -> None:
    """Flujo HTTP completo: vista dedicada guarda mapeos y desbloquea el EFE."""
    from cacao_accounting.database import User, database

    account_ids = _seed_chart(efe_app)
    _post_entries(efe_app, account_ids)
    user = database.session.execute(database.select(User).filter_by(user="efe-user")).scalar_one()
    client = efe_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True

    blocked = client.get("/reports/cash-flow?company=cacao&ledger=FISC&accounting_period=2026-01")
    assert blocked.status_code == 200
    blocked_html = blocked.get_data(as_text=True)
    assert "Clasificar cuentas" in blocked_html
    assert "1.04" in blocked_html

    overview = client.get("/accounting/cash-flow-config/cacao")
    assert overview.status_code == 200
    overview_html = overview.get_data(as_text=True)
    assert "Clasificación para el Estado de Flujo de Efectivo" in overview_html
    assert "sugerido" in overview_html
    assert "Requerida" in overview_html

    form = {"company": "cacao"}
    for code, section in FULL_MAPPING.items():
        form.setdefault("account_ids", []).append(account_ids[code])
        form[f"section_{account_ids[code]}"] = section
    saved = client.post("/accounting/cash-flow-config/cacao", data=form, follow_redirects=True)
    assert saved.status_code == 200
    assert "Clasificación del flujo de efectivo guardada correctamente." in saved.get_data(as_text=True)

    report_page = client.get("/reports/cash-flow?company=cacao&ledger=FISC&accounting_period=2026-01&apply_filters=1")
    assert report_page.status_code == 200
    report_html = report_page.get_data(as_text=True)
    assert "Estado de Flujo de Efectivo" in report_html
    assert "270.00" in report_html

    report_url = "/reports/cash-flow?company=cacao&ledger=FISC&accounting_period=2026-01&apply_filters=1"
    csv_export = client.get(f"{report_url}&export=csv")
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["Content-Type"]
