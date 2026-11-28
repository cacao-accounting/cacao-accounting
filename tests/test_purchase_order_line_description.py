# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1670: la descripción importada llega a la línea persistida."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.services import _save_purchase_order_items
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, PurchaseOrder, PurchaseOrderItem, UOM, database


@pytest.fixture
def purchase_order_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1670",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1670",
                name="Artículo de compra",
                item_type="goods",
                is_stock_item=False,
                is_purchase_item=True,
                default_uom="UND",
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_orden_de_compra_persiste_la_descripcion_de_la_importacion(purchase_order_scene):
    """La descripción que envía el formulario no se descarta al crear la línea."""
    application = purchase_order_scene
    with application.app_context():
        orden = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 15), transaction_currency="NIO", docstatus=0)
        database.session.add(orden)
        database.session.commit()
        order_id = orden.id

        formulario = {
            "item_code_0": "ART-1670",
            "item_name_0": "Artículo de compra",
            "description_0": "Detalle importado desde la plantilla",
            "qty_0": "2",
            "rate_0": "10",
            "uom_0": "UND",
        }
        with application.test_request_context("/", method="POST", data=formulario):
            _save_purchase_order_items(order_id)
            database.session.commit()

        linea = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=order_id)).scalar_one()
        assert linea.description == "Detalle importado desde la plantilla"
        assert linea.amount == Decimal("20.0000")
