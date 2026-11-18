# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1590: el reporte de lotes solo lista lotes con evidencia de la compañía.

Un lote sin movimientos de inventario en la compañía consultada no debe
aparecer con saldo cero. Un lote cuya única evidencia está anulada sí debe
aparecer en cero, porque la compañía tuvo actividad registrada en él.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Currency,
    Entity,
    Item,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.reportes.services import OperationalReportFilters, get_batch_report


@pytest.fixture
def batch_report_scenario():
    """Create batches with alpha evidence, beta-only evidence and no evidence."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    item_code = f"ITEM-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(code=item_code, name="Artículo con lotes", item_type="goods", is_stock_item=True, default_uom="EA"),
                Warehouse(code=f"WA-{suffix}", name="Bodega Alfa", company=company_alpha),
                Warehouse(code=f"WB-{suffix}", name="Bodega Beta", company=company_beta),
            ]
        )
        database.session.flush()
        alpha_batch = Batch(item_code=item_code, batch_no=f"ALPHA-{suffix}")
        beta_batch = Batch(item_code=item_code, batch_no=f"BETA-{suffix}")
        cancelled_batch = Batch(item_code=item_code, batch_no=f"CANCELLED-{suffix}")
        empty_batch = Batch(item_code=item_code, batch_no=f"EMPTY-{suffix}")
        database.session.add_all([alpha_batch, beta_batch, cancelled_batch, empty_batch])
        database.session.flush()
        database.session.add_all(
            [
                StockLedgerEntry(
                    posting_date=date(2026, 11, 2),
                    item_code=item_code,
                    warehouse=f"WA-{suffix}",
                    company=company_alpha,
                    qty_change=5,
                    qty_after_transaction=5,
                    valuation_rate=10,
                    stock_value_difference=50,
                    stock_value=50,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-ALPHA-{suffix}",
                    batch_id=alpha_batch.id,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 11, 3),
                    item_code=item_code,
                    warehouse=f"WB-{suffix}",
                    company=company_beta,
                    qty_change=7,
                    qty_after_transaction=7,
                    valuation_rate=10,
                    stock_value_difference=70,
                    stock_value=70,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-BETA-{suffix}",
                    batch_id=beta_batch.id,
                ),
                StockLedgerEntry(
                    posting_date=date(2026, 11, 4),
                    item_code=item_code,
                    warehouse=f"WA-{suffix}",
                    company=company_alpha,
                    qty_change=3,
                    qty_after_transaction=3,
                    valuation_rate=10,
                    stock_value_difference=30,
                    stock_value=30,
                    voucher_type="stock_entry",
                    voucher_id=f"VOUCHER-CANCELLED-{suffix}",
                    batch_id=cancelled_batch.id,
                    is_cancelled=True,
                ),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "alpha_batch_no": alpha_batch.batch_no,
            "beta_batch_no": beta_batch.batch_no,
            "cancelled_batch_no": cancelled_batch.batch_no,
            "empty_batch_no": empty_batch.batch_no,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_batch_report_excludes_batches_without_company_evidence(batch_report_scenario):
    """Only lots with ledger evidence in the requested company are listed."""
    app, ids = batch_report_scenario

    with app.app_context():
        report = get_batch_report(OperationalReportFilters(company=ids["company_alpha"]))

    batch_numbers = {row.values["batch_no"] for row in report.rows}
    assert batch_numbers == {ids["alpha_batch_no"], ids["cancelled_batch_no"]}
    assert ids["beta_batch_no"] not in batch_numbers
    assert ids["empty_batch_no"] not in batch_numbers


def test_batch_report_keeps_cancelled_evidence_with_zero_balance(batch_report_scenario):
    """A lot whose only evidence is cancelled remains listed at zero."""
    app, ids = batch_report_scenario

    with app.app_context():
        report = get_batch_report(OperationalReportFilters(company=ids["company_alpha"]))

    rows_by_batch = {row.values["batch_no"]: row.values for row in report.rows}
    cancelled_row = rows_by_batch[ids["cancelled_batch_no"]]
    assert cancelled_row["balance_qty"] == Decimal("0")
    assert cancelled_row["stock_value"] == Decimal("0")
    assert rows_by_batch[ids["alpha_batch_no"]]["balance_qty"] == Decimal("5")
    assert report.totals["count"] == Decimal("2")
    assert report.totals["stock_value"] == Decimal("50")


def test_batch_report_for_beta_excludes_alpha_evidence(batch_report_scenario):
    """The isolation is symmetric: Beta's report excludes Alpha-only batches (#1120)."""
    app, ids = batch_report_scenario

    with app.app_context():
        report = get_batch_report(OperationalReportFilters(company=ids["company_beta"]))

    batch_numbers = {row.values["batch_no"] for row in report.rows}
    assert batch_numbers == {ids["beta_batch_no"]}
    assert ids["alpha_batch_no"] not in batch_numbers
    assert ids["cancelled_batch_no"] not in batch_numbers
    assert ids["empty_batch_no"] not in batch_numbers
