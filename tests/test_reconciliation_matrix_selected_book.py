"""Regresiones de conciliación AR/AP desde valoraciones históricas por libro."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    Accounts,
    Book,
    CompanyDefaultAccount,
    Entity,
    ExchangeRate,
    GLEntry,
    Item,
    Party,
    StockLedgerBookEntry,
    StockLedgerEntry,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.reportes.services import (
    ReconciliationFilters,
    _ReconciliationContext,
    _reconcile_ar_ap_rows,
    _reconcile_inventory_row,
    get_reconciliation_matrix,
)


def test_ar_reconciliation_uses_selected_book_posting_values_and_cutoff():
    """Different book valuations and later rates cannot change historical AR."""
    # La conciliación agrega todo el subledger de la compañía. Se usa una
    # compañía propia para que el resultado no dependa de movimientos que
    # otras pruebas hayan confirmado en el worker compartido.
    suffix = uuid4().hex[:8].upper()
    company = f"R{suffix}"
    company_entity = Entity(
        code=company,
        name=f"Conciliación {suffix}",
        company_name=f"Conciliación {suffix} SA",
        tax_id=f"T{suffix}",
        currency="NIO",
        enabled=True,
        status="default",
    )
    selected_book = Book(
        entity=company, code=f"N{suffix}", name="Libro NIO", currency="NIO", status="activo", is_primary=True, default=True
    )
    secondary_book = Book(
        entity=company, code=f"U{suffix}", name="Libro USD", currency="USD", status="activo", is_primary=False
    )
    receivable = Accounts(
        entity=company,
        code=f"AR-{suffix}",
        name="Cuentas por cobrar de prueba",
        classification="asset",
        account_type="receivable",
        group=False,
        active=True,
        enabled=True,
    )
    payable = Accounts(
        entity=company,
        code=f"AP-{suffix}",
        name="Cuentas por pagar de prueba",
        classification="liability",
        account_type="payable",
        group=False,
        active=True,
        enabled=True,
    )
    party = Party(code=f"AR-{suffix}", name="Cliente de conciliación", is_customer=True)
    supplier = Party(code=f"AP-{suffix}", name="Proveedor de conciliación", is_supplier=True)
    database.session.add(company_entity)
    database.session.flush()
    database.session.add_all([selected_book, secondary_book, receivable, payable, party, supplier])
    database.session.flush()
    defaults = CompanyDefaultAccount(company=company, default_receivable=receivable.id, default_payable=payable.id)
    database.session.add(defaults)

    cutoff = date(2026, 10, 31)
    movements = [
        ("invoice", date(2026, 10, 1), Decimal("100")),
        ("application", date(2026, 10, 20), Decimal("-50")),
        ("application_reversal", date(2026, 11, 1), Decimal("50")),
    ]
    for index, (event_type, posting_date, document_amount) in enumerate(movements):
        movement = ARAPLedgerEntry(
            company=company,
            ledger_type="AR",
            party_type="customer",
            party_id=party.id,
            document_type="sales_invoice",
            document_id=f"RECON-DOC-{index}",
            posting_date=posting_date,
            event_type=event_type,
            currency="USD",
            document_amount=document_amount,
            is_reversal=event_type == "application_reversal",
        )
        database.session.add(movement)
        database.session.flush()
        nio_amount = {
            "invoice": Decimal("3600"),
            "application": Decimal("-1850"),
            "application_reversal": Decimal("1850"),
        }[event_type]
        usd_amount = {
            "invoice": Decimal("100"),
            "application": Decimal("-50"),
            "application_reversal": Decimal("50"),
        }[event_type]
        for book, amount in ((selected_book, nio_amount), (secondary_book, usd_amount)):
            database.session.add(
                ARAPLedgerBookEntry(
                    ledger_entry_id=movement.id,
                    ledger_id=book.id,
                    posting_date=posting_date,
                    document_currency="USD",
                    book_currency=book.currency,
                    document_amount=document_amount,
                    book_amount=amount,
                    exchange_rate=abs(amount / document_amount),
                    debit=amount if amount > 0 else Decimal("0"),
                    credit=-amount if amount < 0 else Decimal("0"),
                    account_id=receivable.id,
                )
            )

    for index, (event_type, posting_date, document_amount, nio_amount, usd_amount) in enumerate(
        (
            ("invoice", date(2026, 10, 2), Decimal("20"), Decimal("500"), Decimal("14")),
            ("application", date(2026, 10, 21), Decimal("-8"), Decimal("-200"), Decimal("-6")),
        )
    ):
        movement = ARAPLedgerEntry(
            company=company,
            ledger_type="AP",
            party_type="supplier",
            party_id=supplier.id,
            document_type="purchase_invoice",
            document_id=f"RECON-AP-{index}",
            posting_date=posting_date,
            event_type=event_type,
            currency="USD",
            document_amount=document_amount,
        )
        database.session.add(movement)
        database.session.flush()
        for book, amount in ((selected_book, nio_amount), (secondary_book, usd_amount)):
            database.session.add(
                ARAPLedgerBookEntry(
                    ledger_entry_id=movement.id,
                    ledger_id=book.id,
                    posting_date=posting_date,
                    document_currency="USD",
                    book_currency=book.currency,
                    document_amount=document_amount,
                    book_amount=amount,
                    exchange_rate=abs(amount / document_amount),
                    debit=-amount if amount < 0 else Decimal("0"),
                    credit=amount if amount > 0 else Decimal("0"),
                    account_id=payable.id,
                )
            )

    database.session.add_all(
        [
            GLEntry(
                company=company,
                ledger_id=selected_book.id,
                account_id=receivable.id,
                account_code=receivable.code,
                posting_date=date(2026, 10, 1),
                debit=Decimal("3600"),
                credit=Decimal("0"),
                voucher_type="sales_invoice",
                voucher_id="RECON-INVOICE",
            ),
            GLEntry(
                company=company,
                ledger_id=selected_book.id,
                account_id=receivable.id,
                account_code=receivable.code,
                posting_date=date(2026, 10, 20),
                debit=Decimal("0"),
                credit=Decimal("1850"),
                voucher_type="payment_entry",
                voucher_id="RECON-PAYMENT",
            ),
            GLEntry(
                company=company,
                ledger_id=selected_book.id,
                account_id=payable.id,
                account_code=payable.code,
                posting_date=date(2026, 10, 2),
                debit=Decimal("0"),
                credit=Decimal("500"),
                voucher_type="purchase_invoice",
                voucher_id="RECON-AP-INVOICE",
            ),
            GLEntry(
                company=company,
                ledger_id=selected_book.id,
                account_id=payable.id,
                account_code=payable.code,
                posting_date=date(2026, 10, 21),
                debit=Decimal("200"),
                credit=Decimal("0"),
                voucher_type="payment_entry",
                voucher_id="RECON-AP-PAYMENT",
            ),
        ]
    )
    database.session.flush()
    context = _ReconciliationContext(
        filters=ReconciliationFilters(company=company, ledger=selected_book.id, as_of_date=cutoff),
        ledger=selected_book,
        comparison_currency="NIO",
        as_of_date=cutoff,
        company_currency="NIO",
        defaults=defaults,
        ledger_needs_conversion=False,
    )

    rows = {row.values["area"]: row for row in _reconcile_ar_ap_rows(context)}

    assert rows["AR"].values["subledger_amount"] == Decimal("1750.0000")
    assert rows["AR"].values["gl_control_amount"] == Decimal("1750.0000")
    assert rows["AR"].values["difference"] == Decimal("0.0000")
    assert rows["AP"].values["subledger_amount"] == Decimal("-300.0000")
    assert rows["AP"].values["gl_control_amount"] == Decimal("-300.0000")
    assert rows["AP"].values["difference"] == Decimal("0.0000")
    database.session.add(
        ARAPLedgerEntry(
            company=company,
            ledger_type="AR",
            party_type="customer",
            party_id=party.id,
            document_type="sales_invoice",
            document_id="RECON-MISSING-BOOK-VALUATION",
            posting_date=cutoff,
            event_type="invoice",
            currency="USD",
            document_amount=Decimal("1"),
        )
    )
    database.session.flush()
    with pytest.raises(ValueError, match="valoración AR/AP del libro"):
        _reconcile_ar_ap_rows(context)


def test_inventory_reconciliation_uses_posting_snapshots_not_later_rates():
    """A later FX rate cannot revalue the selected book's historical stock."""
    suffix = uuid4().hex[:8].upper()
    selected_book = Book(
        entity="cacao", code=f"U{suffix}", name="Libro USD", currency="USD", status="activo", is_primary=False
    )
    inventory_account = Accounts(
        entity="cacao",
        code=f"INV-{suffix}",
        name="Inventario de prueba",
        classification="asset",
        account_type="inventory",
        group=False,
        active=True,
        enabled=True,
    )
    uom = UOM(code=f"U{suffix}", name="Unidad de prueba", is_active=True)
    database.session.add_all([selected_book, inventory_account, uom])
    database.session.flush()
    warehouse = Warehouse(code=f"W{suffix}", name="Bodega de prueba", company="cacao")
    item = Item(code=f"I{suffix}", name="Artículo de prueba", item_type="goods", is_stock_item=True, default_uom=uom.code)
    database.session.add_all([warehouse, item])
    database.session.flush()
    database.session.add(
        WarehouseCompanyAccount(
            warehouse_code=warehouse.code,
            company="cacao",
            inventory_account_id=inventory_account.id,
            is_active=True,
        )
    )
    dates = (date(2026, 10, 1), date(2026, 10, 20), date(2026, 11, 1))
    rates = (Decimal("0.01"), Decimal("0.02"), Decimal("0.05"))
    database.session.add_all(
        ExchangeRate(origin="NIO", destination="USD", date=rate_date, rate=rate) for rate_date, rate in zip(dates, rates)
    )
    receipt = StockLedgerEntry(
        company="cacao",
        item_code=item.code,
        warehouse=warehouse.code,
        posting_date=dates[0],
        qty_change=Decimal("1"),
        stock_value_difference=Decimal("10000"),
        voucher_type="purchase_receipt",
        voucher_id="INVENTORY-RECEIPT",
    )
    issue = StockLedgerEntry(
        company="cacao",
        item_code=item.code,
        warehouse=warehouse.code,
        posting_date=dates[1],
        qty_change=Decimal("-0.25"),
        stock_value_difference=Decimal("-2500"),
        voucher_type="delivery_note",
        voucher_id="INVENTORY-ISSUE",
    )
    database.session.add_all([receipt, issue])
    database.session.flush()
    database.session.add_all(
        [
            StockLedgerBookEntry(
                stock_ledger_entry_id=receipt.id,
                ledger_id=selected_book.id,
                posting_date=dates[0],
                book_currency="USD",
                book_amount=Decimal("100"),
                exchange_rate=Decimal("0.01"),
            ),
            StockLedgerBookEntry(
                stock_ledger_entry_id=issue.id,
                ledger_id=selected_book.id,
                posting_date=dates[1],
                book_currency="USD",
                book_amount=Decimal("-50"),
                exchange_rate=Decimal("0.02"),
            ),
            GLEntry(
                company="cacao",
                ledger_id=selected_book.id,
                account_id=inventory_account.id,
                account_code=inventory_account.code,
                posting_date=dates[0],
                debit=Decimal("100"),
                credit=Decimal("0"),
                voucher_type="purchase_receipt",
                voucher_id="INVENTORY-RECEIPT",
            ),
            GLEntry(
                company="cacao",
                ledger_id=selected_book.id,
                account_id=inventory_account.id,
                account_code=inventory_account.code,
                posting_date=dates[1],
                debit=Decimal("0"),
                credit=Decimal("50"),
                voucher_type="delivery_note",
                voucher_id="INVENTORY-ISSUE",
            ),
        ]
    )
    database.session.flush()
    context = _ReconciliationContext(
        filters=ReconciliationFilters(company="cacao", ledger=selected_book.id, as_of_date=date(2026, 11, 30)),
        ledger=selected_book,
        comparison_currency="USD",
        as_of_date=date(2026, 11, 30),
        company_currency="NIO",
        defaults=None,
        ledger_needs_conversion=True,
    )

    row = _reconcile_inventory_row(context)

    assert row.values["subledger_amount"] == Decimal("50.0000")
    assert row.values["gl_control_amount"] == Decimal("50.0000")
    assert row.values["difference"] == Decimal("0.0000")
    database.session.add(
        StockLedgerEntry(
            company="cacao",
            item_code=item.code,
            warehouse=warehouse.code,
            posting_date=dates[1],
            qty_change=Decimal("0.1"),
            stock_value_difference=Decimal("1"),
            voucher_type="purchase_receipt",
            voucher_id="INVENTORY-MISSING-BOOK-VALUATION",
        )
    )
    database.session.flush()
    with pytest.raises(ValueError, match="Falta la valoración del libro"):
        _reconcile_inventory_row(context)


def test_reconciliation_matrix_rejects_currency_different_from_selected_book(entorno_contable_aislado):
    """La matriz rechaza otra moneda y normaliza la moneda del libro (#1235)."""
    app = entorno_contable_aislado.app
    with app.app_context():
        selected_book = database.session.execute(
            database.select(Book).filter_by(entity="cacao", code="DEFAULT_BOOK")
        ).scalar_one()
        ledger_currency = selected_book.currency
        requested_currency = "USD" if selected_book.currency == "NIO" else "NIO"
        filters = ReconciliationFilters(
            company="cacao",
            ledger=selected_book.id,
            currency=f" {requested_currency.lower()} ",
        )

        with pytest.raises(ValueError, match="coincidir con la moneda del libro seleccionado"):
            get_reconciliation_matrix(filters)

        matching_currency_report = get_reconciliation_matrix(
            ReconciliationFilters(company="cacao", ledger=selected_book.id, currency=f" {ledger_currency.lower()} ")
        )

    assert matching_currency_report.ledger_currency == ledger_currency
    assert all(row.values["currency"] == ledger_currency for row in matching_currency_report.rows)
