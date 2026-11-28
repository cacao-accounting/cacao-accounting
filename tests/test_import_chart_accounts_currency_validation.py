# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresiones de integridad monetaria y clasificación del catálogo (#1676, #1668)."""

import csv
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Book, Currency, GLEntry, database
from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    get_balance_sheet_report,
    get_income_statement_report,
)


@pytest.mark.parametrize("currency", ["", "  ", "NIO", " NIO "])
def test_moneda_opcional_o_activa_es_valida(app, entorno_contable, currency):
    """La moneda opcional admite blanco y un código activo sin espacios."""
    with app.app_context():
        assert (
            ChartOfAccountsAdapter().validate_document(
                [{"codigo": "T", "nombre": "Cuenta", "clasificacion": "activo", "moneda": currency}],
                {"company_id": "cacao"},
            )
            == []
        )


@pytest.mark.parametrize("active", [None, False])
def test_moneda_inexistente_o_inactiva_bloquea_lote(app, entorno_contable, tmp_path, active):
    """La validación real impide que el lote quede listo para ejecución."""
    suffix = uuid4().hex[:6].upper()
    code, account_code = f"X{suffix}", f"9{suffix}"
    source = tmp_path / f"{suffix}.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(ChartOfAccountsAdapter.columns)
        writer.writerow([account_code, "Cuenta", "", "false", code, "activo", ""])
    with app.app_context():
        currency = None
        if active is False:
            currency = Currency(code=code, name="Inactiva", active=False)
            database.session.add(currency)
        batch = ImportBatch(
            company_id="cacao",
            record_type="chart_of_accounts",
            source_format="csv",
            source_filename=source.name,
            source_path=str(source),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        try:
            assert ImportService().validate(batch.id)
            assert batch.import_status == 2
            errors = database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch.id)).scalars().all()
            assert any("moneda" in error.message.lower() for error in errors)
            assert (
                database.session.execute(
                    database.select(Accounts).filter_by(entity="cacao", code=account_code)
                ).scalar_one_or_none()
                is None
            )
        finally:
            database.session.delete(batch)
            if currency is not None:
                database.session.delete(currency)
            database.session.commit()


def test_moneda_desactivada_despues_de_validar_no_se_persiste(app, entorno_contable):
    """Un cambio de moneda entre validación y ejecución se rechaza de nuevo."""
    suffix = uuid4().hex[:6].upper()
    code = f"X{suffix}"
    row = {"codigo": f"9{suffix}", "nombre": "Cuenta", "clasificacion": "activo", "moneda": code}
    adapter = ChartOfAccountsAdapter()
    with app.app_context():
        currency = Currency(code=code, name="Temporal", active=True)
        database.session.add(currency)
        database.session.commit()
        try:
            assert adapter.validate_document([row], {"company_id": "cacao"}) == []
            currency.active = False
            database.session.commit()
            with pytest.raises(ValueError, match="moneda"):
                adapter.persist_document(adapter.build_document([row], {"company_id": "cacao"}))
            database.session.rollback()
            assert (
                database.session.execute(
                    database.select(Accounts).filter_by(entity="cacao", code=row["codigo"])
                ).scalar_one_or_none()
                is None
            )
        finally:
            database.session.delete(currency)
            database.session.commit()


@pytest.mark.parametrize(("value", "expected"), [(" ACTiVOS ", "activo"), ("Assets", "asset"), ("gasto", "gasto")])
def test_clasificacion_se_persiste_normalizada(value, expected):
    """Las formas reconocidas se almacenan usando el normalizador compartido."""
    account = ChartOfAccountsAdapter().build_document(
        [{"codigo": "T", "nombre": "Cuenta", "clasificacion": value}], {"company_id": "cacao"}
    )
    assert account.classification == expected


def test_reportes_incluyen_alias_historicos_de_clasificacion(app, entorno_contable):
    """Un alias persistido no pierde la cuenta en balance ni en resultados."""
    suffix = uuid4().hex[:6].upper()
    asset_code, income_code = f"A{suffix}", f"I{suffix}"
    with app.app_context():
        asset = Accounts(
            entity="cacao",
            code=asset_code,
            name="Caja legada",
            classification=" ACTIVOS ",
            account_type="cash",
            group=False,
            active=True,
            enabled=True,
        )
        income = Accounts(
            entity="cacao",
            code=income_code,
            name="Ventas legadas",
            classification="INGRESOS ",
            account_type="income",
            group=False,
            active=True,
            enabled=True,
        )
        database.session.add_all([asset, income])
        database.session.flush()
        book_id = database.session.execute(database.select(Book.id).filter_by(code="DEFAULT_BOOK")).scalar_one()
        for account, debit, credit in ((asset, "10", "0"), (income, "0", "10")):
            database.session.add(
                GLEntry(
                    company="cacao",
                    ledger_id=book_id,
                    account_id=account.id,
                    account_code=account.code,
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    posting_date=date(2026, 5, 15),
                    debit=Decimal(debit),
                    credit=Decimal(credit),
                    voucher_type="journal_entry",
                    voucher_id=f"ALIAS-{suffix}-{account.code}",
                    fiscal_year_id="FY2026",
                    accounting_period_id="P2026-05",
                )
            )
        database.session.commit()
        try:
            filters = FinancialReportFilters(company="cacao", ledger="DEFAULT_BOOK", accounting_period="P2026-05")
            balance = get_balance_sheet_report(filters)
            income_statement = get_income_statement_report(filters)
            assert asset_code in {row.values["account_code"] for row in balance.rows}
            assert income_code in {row.values["account_code"] for row in income_statement.rows}
        finally:
            database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id.like(f"ALIAS-{suffix}%")))
            database.session.delete(income)
            database.session.delete(asset)
            database.session.commit()


def test_consulta_encuentra_alias_historicos_y_canonicos(app, entorno_contable):
    """El filtro devuelve cuentas equivalentes sin cruzar categorías."""
    from cacao_accounting.query_tools.context import QueryContext
    from cacao_accounting.query_tools.handlers.accounting import search_accounts

    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        accounts = [
            Accounts(entity="cacao", code=f"A{suffix}", name="Alias", classification=" ACTIVOS "),
            Accounts(entity="cacao", code=f"B{suffix}", name="Canónica", classification="asset"),
            Accounts(entity="cacao", code=f"C{suffix}", name="Pasivo", classification="pasivo"),
        ]
        database.session.add_all(accounts)
        database.session.commit()
        try:
            context = QueryContext(
                user_id="test", company_ids=["cacao"], permissions={"accounting.reports.read"}, is_service_principal=True
            )
            result = search_accounts.handler(context=context, company_id="cacao", query=suffix, classification="Activo")
            assert {row["code"] for row in result["items"]} == {f"A{suffix}", f"B{suffix}"}
        finally:
            for account in accounts:
                database.session.delete(account)
            database.session.commit()
