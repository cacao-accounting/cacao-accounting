# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""#1687: evita tarifas contradictorias con criterios identicos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Item, ItemPrice, PriceList, UOM, database
from cacao_accounting.tax_pricing_service import resolve_item_price_record


def _ensure_uom(code: str = "UND1687") -> None:
    if database.session.get(UOM, code) is None:
        database.session.add(UOM(code=code, name=code, is_active=True))
        database.session.flush()


def _ensure_item(code: str, uom: str = "UND1687") -> None:
    if database.session.get(Item, code) is None:
        database.session.add(Item(code=code, name=code, item_type="product", default_uom=uom, is_active=True))
        database.session.flush()


def test_resolve_item_price_record_es_determinista_en_empate(app):
    with app.app_context():
        uom = "U" + uuid4().hex[:8].upper()
        item_code = "I" + uuid4().hex[:8].upper()
        _ensure_uom(uom)
        _ensure_item(item_code, uom)
        pl = PriceList(name=f"Lista-{uuid4().hex[:6]}", is_active=True)
        database.session.add(pl)
        database.session.flush()

        database.session.add(
            ItemPrice(
                id="01AAAAAAAAAAAAAAAAAAAAAAA1",
                item_code=item_code,
                price_list_id=pl.id,
                uom=uom,
                price=Decimal("5.0000"),
                min_qty=Decimal("1"),
                valid_from=date(2026, 1, 1),
                valid_upto=date(2026, 12, 31),
            )
        )
        database.session.add(
            ItemPrice(
                id="01AAAAAAAAAAAAAAAAAAAAAAA2",
                item_code=item_code,
                price_list_id=pl.id,
                uom=uom,
                price=Decimal("9.0000"),
                min_qty=Decimal("1"),
                valid_from=date(2026, 1, 1),
                valid_upto=date(2026, 12, 31),
            )
        )
        database.session.commit()

        resolved = resolve_item_price_record(item_code, pl.id, Decimal("2"), uom, date(2026, 5, 1))
        assert resolved is not None
        assert resolved.id == "01AAAAAAAAAAAAAAAAAAAAAAA1"


def test_admin_duplicate_item_price_rejected(app):
    """La ruta rechaza duplicado con criterios identicos."""
    from cacao_accounting.admin import routes as admin_routes

    with app.app_context():
        uom = "U" + uuid4().hex[:8].upper()
        item_code = "I" + uuid4().hex[:8].upper()
        _ensure_uom(uom)
        _ensure_item(item_code, uom)
        pl = PriceList(name=f"Lista-{uuid4().hex[:6]}", is_active=True)
        database.session.add(pl)
        database.session.flush()
        pl_id = pl.id
        database.session.add(
            ItemPrice(
                item_code=item_code,
                price_list_id=pl_id,
                uom=uom,
                price=Decimal("10.0000"),
                min_qty=Decimal("1"),
                valid_from=date(2026, 1, 1),
                valid_upto=date(2026, 12, 31),
            )
        )
        database.session.commit()

        err = admin_routes._duplicate_item_price_error(
            pl_id, item_code, uom, Decimal("1"), date(2026, 1, 1), date(2026, 12, 31)
        )
        assert err is not None

        ok = admin_routes._duplicate_item_price_error(
            pl_id, item_code, uom, Decimal("2"), date(2026, 1, 1), date(2026, 12, 31)
        )
        assert ok is None
