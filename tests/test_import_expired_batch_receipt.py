# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1674: la importación rechaza lotes vencidos para la fecha del documento."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import Batch, Item, database
from cacao_accounting.imports.adapters.transaction_documents import PurchaseReceiptAdapter


def test_lote_vencido_se_rechaza_al_validar_la_fila(app, entorno_contable):
    """El prechequeo replica la regla de posting: expiry <= fecha es vencido."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    codigo = f"VENC-{sufijo}"
    with app.app_context():
        database.session.add(
            Item(
                code=codigo,
                name=f"Item vencimiento {sufijo}",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                has_expiry_date=True,
            )
        )
        database.session.flush()
        lote = Batch(item_code=codigo, batch_no=f"LOTE-{sufijo}", expiry_date=date(2026, 10, 31), is_active=True)
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id

    try:
        adapter = PurchaseReceiptAdapter()
        with app.app_context():
            errores_vencido = adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 11, 1))
            assert errores_vencido == [
                f"El lote 'LOTE-{sufijo}' del item '{codigo}' está vencido para la fecha de contabilización."
            ]

            assert adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 10, 31)) == errores_vencido
            assert adapter._validate_row_batch(codigo, f"LOTE-{sufijo}", date(2026, 10, 30)) == []
    finally:
        with app.app_context():
            database.session.execute(database.delete(Batch).where(Batch.id == lote_id))
            database.session.execute(database.delete(Item).where(Item.code == codigo))
            database.session.commit()
