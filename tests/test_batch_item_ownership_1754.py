# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1754: un lote debe pertenecer al artículo de la línea.

El validador solo comprobaba el lote cuando el artículo exigía control de lote;
un lote opcional de otro artículo se aceptaba y el writer lo copiaba al
StockLedgerEntry/StockValuationLayer. La devolución de compra además omitía la
validación de lote al calcular el costo con la recepción origen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.posting_service import PostingError, _create_stock_ledger_for_document
from cacao_accounting.database import Batch, Item, Party, PurchaseReceipt, PurchaseReceiptItem, database
from cacao_accounting.inventario.service import InventoryServiceError, validate_batch_serial

MENSAJE_LOTE_AJENO = "no pertenece al item"


def _articulo(code: str, *, batch: bool = False) -> Item:
    """Artículo inventariable con o sin control de lote."""
    return Item(
        code=code,
        name=f"Artículo {code}",
        item_type="goods",
        is_stock_item=True,
        has_batch=batch,
        default_uom="UND",
    )


def _sembrar(app) -> dict[str, str]:
    """Crea dos artículos y un lote de cada uno."""
    sufijo = uuid4().hex[:6].upper()
    codigo_a = f"SKU-A-{sufijo}"
    codigo_b = f"SKU-B-{sufijo}"
    with app.app_context():
        database.session.add_all([_articulo(codigo_a), _articulo(codigo_b)])
        database.session.flush()
        lote_a = Batch(batch_no=f"LOTE-A-{sufijo}", item_code=codigo_a, is_active=True)
        lote_b = Batch(batch_no=f"LOTE-B-{sufijo}", item_code=codigo_b, is_active=True)
        database.session.add_all([lote_a, lote_b])
        database.session.commit()
        return {"item_a": codigo_a, "item_b": codigo_b, "lote_a": lote_a.id, "lote_b": lote_b.id}


def _linea(datos: dict[str, str], lote: str) -> SimpleNamespace:
    """Línea mínima que consume el validador de lote/serial."""
    return SimpleNamespace(
        item_code=datos["item_a"],
        batch_id=lote,
        qty=Decimal("1"),
        uom="UND",
        qty_in_base_uom=Decimal("1"),
    )


def test_el_validador_rechaza_el_lote_de_otro_articulo_sin_control(app, entorno_contable):
    """El lote opcional también debe pertenecer al artículo (#1754)."""
    del entorno_contable
    datos = _sembrar(app)

    with app.app_context():
        with pytest.raises(InventoryServiceError, match=MENSAJE_LOTE_AJENO):
            validate_batch_serial(_linea(datos, datos["lote_b"]), outgoing=False)

        validate_batch_serial(_linea(datos, datos["lote_a"]), outgoing=False)


def test_la_devolucion_de_compra_rechaza_un_lote_de_otro_articulo(app, entorno_contable):
    """El writer de la devolución no copia un batch_id ajeno al SLE/SVL."""
    del entorno_contable
    datos = _sembrar(app)

    with app.app_context():
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 20),
            docstatus=1,
            is_return=True,
            reversal_of="PR-ORIGEN-1754",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(receipt)
        database.session.flush()
        linea = PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code=datos["item_a"],
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("10"),
            warehouse="BOD01",
            batch_id=datos["lote_b"],
        )
        database.session.add(linea)
        database.session.flush()

        with pytest.raises(PostingError, match=MENSAJE_LOTE_AJENO):
            _create_stock_ledger_for_document(receipt, Decimal("-1"), Decimal("-10"), "BOD01", linea)

        database.session.rollback()
