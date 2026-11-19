# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2127: la reclasificación 2-way se atribuye por artículo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.accounting_engine.document_builders import _subtract_late_receipt_reclassifications
from cacao_accounting.database import Item, PurchaseReceipt, PurchaseReceiptItem, database

FECHA = date(2026, 5, 15)


def test_la_reclasificacion_previa_no_se_resta_dos_veces(app, entorno_contable):
    """Cada crédito de recepción descuenta solo su artículo, no toda la cuenta."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.session.add_all(
            [
                Item(
                    code=f"ART-A-{suffix}",
                    name="Artículo A",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="UND",
                ),
                Item(
                    code=f"ART-B-{suffix}",
                    name="Artículo B",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="UND",
                ),
            ]
        )
        database.session.flush()
        receipts = []
        for index, (item_code, amount) in enumerate(((f"ART-A-{suffix}", "50"), (f"ART-B-{suffix}", "100"))):
            receipt = PurchaseReceipt(
                company="cacao",
                posting_date=FECHA,
                docstatus=1,
                document_no=f"PR-REC-{suffix}-{index}",
                transaction_currency="NIO",
                base_currency="NIO",
            )
            database.session.add(receipt)
            database.session.flush()
            database.session.add(
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code=item_code,
                    item_name=item_code,
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal(amount),
                    amount=Decimal(amount),
                )
            )
            receipts.append(receipt)
        database.session.commit()
        current = receipts[0]
        amounts = {f"ART-A-{suffix}": Decimal("100"), f"ART-B-{suffix}": Decimal("200")}
        posting_dates = {f"ART-A-{suffix}": date(2026, 5, 1), f"ART-B-{suffix}": date(2026, 5, 1)}

        _subtract_late_receipt_reclassifications(current, amounts, posting_dates, receipts)

        assert amounts == {f"ART-A-{suffix}": Decimal("50"), f"ART-B-{suffix}": Decimal("100")}
