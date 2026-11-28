# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Moreno Reyes

"""#1868: la reversa mantiene StockBin reconciliable con la suma de SLE."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.contabilidad.posting_service import _cancel_stock_movements_if_needed
from cacao_accounting.database import (
    Book,
    Item,
    StockBin,
    StockEntry,
    StockLedgerBookEntry,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.internal_control_service import _LEDGER_CANCELLATION_ACTIVE, authorized_posting


def test_reversa_mantiene_bin_igual_suma_sle(app):
    """Tras reversar, StockBin.actual_qty coincide con suma de SLE no cancelados (#1868)."""
    with app.app_context():
        database.session.add(UOM(code="UND1868I", name="Unidad 1868I"))
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1868I",
                name="Articulo 1868I",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND1868I",
            )
        )
        database.session.add(Warehouse(code="BOD-1868I", name="Bodega 1868I", company="cacao"))
        book = database.session.get(Book, "ledger-001")
        if book is None:
            book = Book(
                id="ledger-001",
                entity="cacao",
                code="LED001",
                name="Ledger 001",
                currency="NIO",
                status="activo",
                is_primary=True,
            )
            database.session.add(book)
        database.session.flush()
        se = StockEntry(company="cacao", purpose="material_issue", status="submitted", docstatus=1)
        database.session.add(se)
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ART-1868I",
                warehouse="BOD-1868I",
                actual_qty=Decimal("6"),
                stock_value=Decimal("60"),
                valuation_rate=Decimal("10"),
            )
        )
        sle = StockLedgerEntry(
            posting_date=date(2026, 5, 20),
            company="cacao",
            item_code="ART-1868I",
            warehouse="BOD-1868I",
            qty_change=Decimal("-4"),
            stock_value_difference=Decimal("-40"),
            valuation_rate=Decimal("10"),
            qty_after_transaction=Decimal("6"),
            stock_value=Decimal("60"),
            voucher_type="Stock Entry",
            voucher_id=se.id,
            is_cancelled=False,
        )
        database.session.add(sle)
        database.session.flush()
        database.session.add(
            StockLedgerBookEntry(
                stock_ledger_entry_id=sle.id,
                ledger_id="ledger-001",
                posting_date=sle.posting_date,
                book_currency="NIO",
                book_amount=Decimal("-40"),
                exchange_rate=Decimal("1"),
            )
        )
        database.session.commit()

        token = _LEDGER_CANCELLATION_ACTIVE.set(("Stock Entry", se.id))
        try:
            with authorized_posting():
                _cancel_stock_movements_if_needed(se, "cacao", "Stock Entry", se.id, sle.posting_date)
        finally:
            _LEDGER_CANCELLATION_ACTIVE.reset(token)
        database.session.commit()

        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART-1868I", warehouse="BOD-1868I")
        ).scalar_one()
        sle_sum = database.session.execute(
            database.select(database.func.coalesce(database.func.sum(StockLedgerEntry.qty_change), 0)).where(
                StockLedgerEntry.company == "cacao",
                StockLedgerEntry.item_code == "ART-1868I",
                StockLedgerEntry.warehouse == "BOD-1868I",
                StockLedgerEntry.is_cancelled.is_(False),
            )
        ).scalar_one()
        # Bin: 6 (post-salida) + 4 (reversa) = 10. El SLE original queda cancelado;
        # solo la reversa no cancelada permanece, con qty +4.
        assert Decimal(str(bin_row.actual_qty)) == Decimal("10")
        assert Decimal(str(sle_sum)) == Decimal("4")


def test_reversa_revalida_bin_refrescado_bajo_lock(app):
    """#1868: una reversa que deja negativo debe rechazarse con bin refrescado."""
    with app.app_context():
        database.session.add(UOM(code="UND1868R", name="Unidad 1868R"))
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1868R",
                name="Articulo 1868R",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND1868R",
                allow_negative_stock=False,
            )
        )
        database.session.add(Warehouse(code="BOD-1868R", name="Bodega 1868R", company="cacao"))
        database.session.flush()
        se = StockEntry(company="cacao", purpose="material_receipt", status="submitted", docstatus=1)
        database.session.add(se)
        database.session.flush()
        # Bin actual insuficiente para reversar entrada original de +10.
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ART-1868R",
                warehouse="BOD-1868R",
                actual_qty=Decimal("2"),
                stock_value=Decimal("20"),
                valuation_rate=Decimal("10"),
            )
        )
        sle = StockLedgerEntry(
            posting_date=date(2026, 5, 20),
            company="cacao",
            item_code="ART-1868R",
            warehouse="BOD-1868R",
            qty_change=Decimal("10"),
            stock_value_difference=Decimal("100"),
            valuation_rate=Decimal("10"),
            qty_after_transaction=Decimal("10"),
            stock_value=Decimal("100"),
            voucher_type="Stock Entry",
            voucher_id=se.id,
            is_cancelled=False,
        )
        database.session.add(sle)
        database.session.commit()

        import pytest
        from cacao_accounting.contabilidad.posting_service import PostingError

        token = _LEDGER_CANCELLATION_ACTIVE.set(("Stock Entry", se.id))
        try:
            with pytest.raises(PostingError, match="stock negativo"):
                with authorized_posting():
                    _cancel_stock_movements_if_needed(se, "cacao", "Stock Entry", se.id, sle.posting_date)
            database.session.rollback()
        finally:
            _LEDGER_CANCELLATION_ACTIVE.reset(token)

        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART-1868R", warehouse="BOD-1868R")
        ).scalar_one()
        assert Decimal(str(bin_row.actual_qty)) == Decimal("2")


def test_mensaje_de_reversa_tiene_traduccion_inglesa():
    """#1868: el mensaje de reversa conserva español correcto y traducción."""
    from pathlib import Path as FilePath

    catalogo = FilePath(__file__).parents[1] / "cacao_accounting/translations/en/LC_MESSAGES/messages.po"
    contenido = catalogo.read_text(encoding="utf-8")
    assert "La reversa de stock dejaría el bin con cantidad negativa" in contenido
    assert "Reversing the stock movement would leave the bin with a negative quantity" in contenido
