# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1820: cancelar orden cerrada no altera reservas de otras órdenes."""

from decimal import Decimal

import pytest
from flask_login import login_user
from werkzeug.exceptions import HTTPException

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    SalesOrder,
    StockBin,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.ventas.routes import ventas_orden_venta_cancel
from cacao_accounting.ventas.services import _restore_reservation_for_delivery_note


def test_cancel_orden_cerrada_es_rechazada(app):
    """La ruta de cancelación exige orden abierta, no solo docstatus=1 (#1820)."""
    with app.app_context():
        order = SalesOrder(company="cacao", docstatus=1, status="closed", document_no="SO-1820", customer_name="Cliente 1820")
        database.session.add(order)
        database.session.commit()
        order_id = order.id
        with app.test_request_context(f"/sales/sales-order/{order_id}/cancel", method="POST"):
            login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
            with pytest.raises(HTTPException) as exc_info:
                ventas_orden_venta_cancel(order_id)
        assert exc_info.value.code == 400


def test_restaurar_reserva_no_restaura_de_orden_cerrada(app):
    """Restaurar reserva conserva el bin sin cambios si la orden está cerrada (#1820)."""
    with app.app_context():
        database.session.add(UOM(code="UND", name="Unidad"))
        database.session.flush()
        database.session.add_all(
            [
                Item(code="ART-1820", name="Articulo 1820", item_type="goods", is_stock_item=True, default_uom="UND"),
                Warehouse(code="BOD-1820", name="Bodega 1820", company="cacao"),
            ]
        )
        database.session.flush()
        order = SalesOrder(company="cacao", docstatus=1, status="closed", document_no="SO-1820B", customer_name="Cliente 1820")
        database.session.add(order)
        database.session.flush()
        dn = DeliveryNote(
            company="cacao", docstatus=0, sales_order_id=order.id, document_no="DN-1820", customer_name="Cliente 1820"
        )
        database.session.add(dn)
        database.session.flush()
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=dn.id,
                item_code="ART-1820",
                item_name="Articulo 1820",
                qty=Decimal("5"),
                uom="UND",
            )
        )
        database.session.add(StockBin(company="cacao", item_code="ART-1820", warehouse="BOD-1820", reserved_qty=Decimal("5")))
        database.session.commit()

        _restore_reservation_for_delivery_note(dn)

        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ART-1820", warehouse="BOD-1820")
        ).scalar_one()
        assert bin_row.reserved_qty == Decimal("5")
