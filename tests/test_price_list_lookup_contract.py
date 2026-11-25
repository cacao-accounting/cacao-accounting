# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2009: la resolución de precios respeta venta, actividad y vigencia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    CompanyParty,
    Item,
    Party,
    PriceList,
    ItemPrice,
    database,
)
from cacao_accounting.tax_pricing_service import resolve_item_price_record
from cacao_accounting.ventas.services import resolve_sales_catalog_price

DENTRO = date(2026, 5, 15)
ANTES = date(2026, 4, 30)
DESPUES = date(2026, 6, 1)


def test_vigencia_y_lista_de_venta(entorno_contable_aislado):
    """Solo la lista de venta activa y el precio vigente se aplican."""
    app = entorno_contable_aislado.app
    with app.app_context():
        sufijo = uuid4().hex[:6]
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        venta = PriceList(
            name=f"Venta {sufijo}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_buying=False,
            is_default=True,
            is_active=True,
        )
        compra = PriceList(
            name=f"Compra {sufijo}",
            company="cacao",
            currency="NIO",
            is_selling=False,
            is_buying=True,
            is_default=True,
            is_active=True,
        )
        database.session.add_all([venta, compra])
        database.session.flush()
        database.session.add(
            ItemPrice(
                item_code=item.code,
                price_list_id=venta.id,
                uom="UND",
                price=Decimal("10"),
                valid_from=DENTRO,
                valid_upto=DENTRO,
            )
        )
        database.session.commit()

        assert resolve_item_price_record(item.code, venta.id, Decimal("1"), "UND", DENTRO) is not None
        assert resolve_item_price_record(item.code, venta.id, Decimal("1"), "UND", ANTES) is None
        assert resolve_item_price_record(item.code, venta.id, Decimal("1"), "UND", DESPUES) is None

        resuelto = resolve_sales_catalog_price("cacao", cliente.id, item.code, Decimal("1"), "UND", DENTRO)
        assert resuelto is not None
        assert resuelto[0] == Decimal("10.0000")
        assert resuelto[1].id == venta.id

        company_party = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=cliente.id)
        ).scalar_one()
        company_party.default_price_list_id = compra.id
        database.session.commit()

        resuelto = resolve_sales_catalog_price("cacao", cliente.id, item.code, Decimal("1"), "UND", DENTRO)
        assert resuelto is not None
        assert resuelto[1].id == venta.id


def test_listas_inactivas_configurada_y_predeterminada_no_se_resuelven(entorno_contable_aislado):
    """Una lista inactiva no desplaza a la predeterminada activa de venta."""
    app = entorno_contable_aislado.app
    with app.app_context():
        sufijo = uuid4().hex[:6]
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        activa = PriceList(
            name=f"Venta activa {sufijo}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_buying=False,
            is_default=True,
            is_active=True,
        )
        inactiva = PriceList(
            name=f"Venta inactiva {sufijo}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_buying=False,
            is_default=True,
            is_active=False,
        )
        database.session.add_all([activa, inactiva])
        database.session.flush()
        for lista, precio in ((activa, Decimal("10")), (inactiva, Decimal("99"))):
            database.session.add(
                ItemPrice(
                    item_code=item.code,
                    price_list_id=lista.id,
                    uom="UND",
                    price=precio,
                    valid_from=DENTRO,
                    valid_upto=DENTRO,
                )
            )
        company_party = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=cliente.id)
        ).scalar_one()
        company_party.default_price_list_id = inactiva.id
        database.session.commit()

        resuelto = resolve_sales_catalog_price("cacao", cliente.id, item.code, Decimal("1"), "UND", DENTRO)
        assert resuelto is not None
        assert resuelto[0] == Decimal("10.0000")
        assert resuelto[1].id == activa.id
