# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2184: una adjudicación de cotización impide borrar el artículo.

`PurchaseQuotationAwardItem.item_code` guarda una referencia al artículo. La
eliminación debe detectarla incluso en SQLite Desktop, donde las FK están
desactivadas por defecto.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Item, PurchaseQuotationAwardItem, UOM, database
from cacao_accounting.exceptions import IntegrityError as CacaoIntegrityError


def test_item_with_award_usage_cannot_be_deleted(app, entorno_contable):
    """La adjudicación cuenta como uso y bloquea el borrado físico."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        # SQLite Desktop puede operar sin FK activas; el guard debe cubrir
        # igualmente la referencia.
        if database.engine.dialect.name == "sqlite":
            database.session.execute(database.text("PRAGMA foreign_keys=OFF"))
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none()
        if uom is None:
            database.session.add(UOM(code="UND", name="Unidad", is_active=True))
            database.session.flush()
        item = Item(
            code=f"AWD-{suffix}",
            name="Artículo adjudicado",
            item_type="goods",
            is_stock_item=False,
            default_uom="UND",
        )
        database.session.add(item)
        database.session.flush()
        database.session.add(
            PurchaseQuotationAwardItem(
                award_id=f"AWARD-{suffix}",
                purchase_quotation_item_id=f"PQI-{suffix}",
                supplier_quotation_id=f"SQ-{suffix}",
                supplier_quotation_item_id=f"SQI-{suffix}",
                item_code=item.code,
                qty=Decimal("1"),
                rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.commit()
        item_id = item.id

        with pytest.raises(CacaoIntegrityError):
            database.session.delete(database.session.get(Item, item_id))
            database.session.flush()
        database.session.rollback()
        assert database.session.get(Item, item_id) is not None


def test_all_item_and_warehouse_references_are_restrict():
    """Toda referencia nominal usada por los guards declara FK RESTRICT."""
    for table in database.metadata.sorted_tables:
        for column in table.c:
            if column.name not in {"item_code", "warehouse", "warehouse_code"}:
                continue
            assert any(
                (fk.ondelete or "RESTRICT").upper() in {"RESTRICT", "NO ACTION"} for fk in column.foreign_keys
            ), f"{table.name}.{column.name} debe declarar una FK RESTRICT"
