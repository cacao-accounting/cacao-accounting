# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1675: un lote opcional en blanco se trata como ausente al construir la línea."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Batch, database
from cacao_accounting.imports.adapters.transaction_documents import PurchaseReceiptAdapter


def test_lote_en_blanco_no_se_resuelve_como_numero(app, entorno_contable):
    """El constructor no busca un lote con cadena vacía tras el strip."""
    del entorno_contable
    adapter = PurchaseReceiptAdapter()
    with app.app_context():
        assert adapter._resolve_batch_id("ART01", "   ") is None
        assert adapter._resolve_batch_id("ART01", "") is None
        assert adapter._resolve_batch_id("ART01", None) is None


def test_lote_valido_se_resuelve_sin_espacios(app, entorno_contable):
    """Un número real de lote, con espacios accidentales, resuelve al registro."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    adapter = PurchaseReceiptAdapter()
    with app.app_context():
        lote = Batch(item_code="ART01", batch_no=f"LOTE-{sufijo}", is_active=True)
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id

    try:
        with app.app_context():
            assert adapter._resolve_batch_id("ART01", f"  LOTE-{sufijo}  ") == lote_id
    finally:
        with app.app_context():
            database.session.execute(database.delete(Batch).where(Batch.id == lote_id))
            database.session.commit()
