"""Pruebas de regresión para filtros del mayor y catálogo de comprobantes."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Book, GLEntry, database
from cacao_accounting.reportes import _build_hierarchical_financial_rows
from cacao_accounting.reportes.services import FinancialReportFilters, get_account_movement_detail
from cacao_accounting.search_select import search_select


@pytest.fixture()
def app_ctx():
    """Proporciona una base aislada para probar los filtros del reporte."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity

        database.create_all()
        database.session.add(Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"))
        database.session.commit()
        yield app


def test_account_movement_filters_by_visible_naming_series_value(app_ctx):
    """El filtro usa el valor visible generado por la naming series."""
    book = Book(entity="cacao", code="FILTER-BOOK", name="Filter Book", currency="NIO", is_primary=True, default=True)
    database.session.add(book)
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 8, 11),
                company="cacao",
                ledger_id=book.id,
                debit=Decimal("10"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="target-voucher-id",
                document_no="TARGET-DOC-001",
            ),
            GLEntry(
                posting_date=date(2026, 8, 11),
                company="cacao",
                ledger_id=book.id,
                debit=Decimal("0"),
                credit=Decimal("10"),
                voucher_type="journal_entry",
                voucher_id="target-voucher-id",
                document_no="TARGET-DOC-001",
            ),
        ]
    )
    database.session.commit()

    report = get_account_movement_detail(
        FinancialReportFilters(company="cacao", ledger=book.code, voucher_number="TARGET-DOC-001", status="submitted")
    )
    by_type = get_account_movement_detail(
        FinancialReportFilters(company="cacao", ledger=book.code, voucher_type="JOURNAL_ENTRY", status="submitted")
    )

    assert report.total_rows == 2
    assert by_type.total_rows == 2


def test_voucher_type_catalog_includes_system_registry_and_accepts_book_code(app_ctx):
    """El catálogo publica tipos del registro aunque el libro no tenga movimientos previos."""
    book = Book(entity="cacao", code="CATALOG-BOOK", name="Catalog Book", currency="NIO", is_primary=True, default=True)
    database.session.add(book)
    database.session.commit()

    payload = search_select("voucher_type", "journal", {"company": ["cacao"], "ledger": [book.code]}, limit=50)

    assert any(option["value"] == "journal_entry" for option in payload["results"])
    full_catalog = search_select("voucher_type", "", {"company": ["cacao"], "ledger": [book.code]}, limit=50)
    values = {option["value"] for option in full_catalog["results"]}
    assert "sales_invoice" in values
    assert "sales_order" not in values
    assert "purchase_order" not in values


def test_batch_search_select_filters_by_item_and_serializes_expiry(app_ctx):
    """El selector de lotes devuelve solo lotes activos del artículo y su vencimiento."""
    from cacao_accounting.database import Batch, Item, UOM

    database.session.add(UOM(code="EA-BATCH-SELECT", name="Unidad lote"))
    database.session.add(
        Item(code="ITEM-BATCH-SELECT", name="Artículo lote", item_type="goods", default_uom="EA-BATCH-SELECT")
    )
    database.session.flush()
    database.session.add(
        Batch(
            item_code="ITEM-BATCH-SELECT",
            batch_no="LOT-SELECT-01",
            expiry_date=date(2027, 1, 15),
            is_active=True,
        )
    )
    database.session.commit()

    payload = search_select("batch", "LOT-SELECT", {"item_code": ["ITEM-BATCH-SELECT"]}, limit=10)

    assert payload["results"]
    result = payload["results"][0]
    assert result["batch_no"] == "LOT-SELECT-01"
    assert result["expiry_date"] == "2027-01-15"
    assert "2027-01-15" in result["display_name"]


def test_gl_entry_rejects_missing_voucher_type():
    """El motor no permite crear entradas GL sin origen documental."""
    from cacao_accounting.contabilidad.posting import GLEntryParams, LedgerContext, PostingError, _create_gl_entry

    context = LedgerContext(
        company="cacao",
        posting_date=date(2026, 8, 11),
        ledger_id=None,
        voucher_type="",
        voucher_id="voucher-without-type",
        document_no="DOC-001",
        naming_series_id=None,
        accounting_period_id=None,
        fiscal_year_id=None,
        transaction_currency=None,
        company_currency="NIO",
        document_base_currency="NIO",
        exchange_rate=None,
        document_remarks=None,
    )

    with pytest.raises(PostingError, match="tipo de comprobante"):
        _create_gl_entry(context=context, params=GLEntryParams(account_id="missing", debit=Decimal("1"), credit=Decimal("0")))


def test_balance_sheet_period_result_is_after_equity_accounts(app_ctx):
    """El resultado del período queda como última línea de la sección patrimonio."""
    rows = _build_hierarchical_financial_rows(
        "balance-sheet",
        [
            {"section": "equity", "account_code": "31", "account_name": "Capital", "amount": Decimal("2010")},
            {"section": "equity", "account_code": None, "account_name": "period_profit_summary", "amount": Decimal("0")},
        ],
        "cacao",
    )

    assert [row.get("account_name") for row in rows] == ["Capital", "period_profit_summary"]
