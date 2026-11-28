# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1279: la UOM exacta prevalece sobre un umbral de cantidad genérico."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ItemPrice, PriceList, database
from cacao_accounting.tax_pricing_service import resolve_item_price_record


def _price_list(app) -> str:
    with app.app_context():
        price_list = PriceList(
            name=f"Lista UOM {uuid4().hex[:8]}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_active=True,
        )
        database.session.add(price_list)
        database.session.commit()
        return str(price_list.id)


def test_uom_especifica_prevalece_sobre_umbral_generico(app, entorno_contable):
    """Una tarifa EA sin mínimo gana a una genérica con umbral satisfecho."""
    price_list_id = _price_list(app)
    with app.app_context():
        database.session.add_all(
            [
                ItemPrice(
                    item_code="ART01",
                    price_list_id=price_list_id,
                    uom=None,
                    price=Decimal("90"),
                    min_qty=Decimal("10"),
                ),
                ItemPrice(
                    item_code="ART01",
                    price_list_id=price_list_id,
                    uom="UND",
                    price=Decimal("100"),
                    min_qty=None,
                ),
            ]
        )
        database.session.commit()

        resolved = resolve_item_price_record("ART01", price_list_id, Decimal("10"), "UND", date(2026, 5, 15))

        assert resolved is not None
        assert resolved.uom == "UND"
        assert resolved.price == Decimal("100")

        for price in database.session.execute(database.select(ItemPrice).filter_by(price_list_id=price_list_id)).scalars():
            database.session.delete(price)
        database.session.delete(database.session.get(PriceList, price_list_id))
        database.session.commit()


def test_umbral_de_cantidad_ordena_dentro_de_la_misma_uom(app, entorno_contable):
    """Con la misma UOM, el umbral de cantidad más alto aplicable gana."""
    price_list_id = _price_list(app)
    with app.app_context():
        database.session.add_all(
            [
                ItemPrice(
                    item_code="ART01", price_list_id=price_list_id, uom="UND", price=Decimal("100"), min_qty=Decimal("1")
                ),
                ItemPrice(
                    item_code="ART01", price_list_id=price_list_id, uom="UND", price=Decimal("80"), min_qty=Decimal("10")
                ),
            ]
        )
        database.session.commit()

        resolved = resolve_item_price_record("ART01", price_list_id, Decimal("10"), "UND", date(2026, 5, 15))

        assert resolved is not None
        assert resolved.price == Decimal("80")

        for price in database.session.execute(database.select(ItemPrice).filter_by(price_list_id=price_list_id)).scalars():
            database.session.delete(price)
        database.session.delete(database.session.get(PriceList, price_list_id))
        database.session.commit()
