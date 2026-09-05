"""Regression coverage for serialized sales returns."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Item, ItemUOMConversion, SerialNumber, UOM, database
from cacao_accounting.inventario.service import InventoryServiceError, update_serial_state, validate_batch_serial


def test_delivered_serial_can_only_reenter_through_a_sales_return() -> None:
    """Allow a delivered serial back into stock while rejecting other existing states."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Entity(code="serial", name="Serial", company_name="Serial", tax_id="SERIAL", currency="NIO"),
                UOM(code="EA", name="Each"),
                Item(
                    code="SERIAL-ITEM",
                    name="Serial item",
                    item_type="goods",
                    is_stock_item=True,
                    has_serial_no=True,
                    default_uom="EA",
                ),
                SerialNumber(item_code="SERIAL-ITEM", serial_no="SN-001", serial_status="delivered"),
            ]
        )
        database.session.commit()
        line = SimpleNamespace(item_code="SERIAL-ITEM", serial_no="SN-001")

        validate_batch_serial(line, outgoing=False, warehouse="WH-RETURN", allow_return=True)
        update_serial_state(line, outgoing=False, warehouse="WH-RETURN")
        database.session.commit()

        serial = database.session.execute(
            database.select(SerialNumber).filter_by(item_code="SERIAL-ITEM", serial_no="SN-001")
        ).scalar_one()
        assert serial.serial_status == "available"
        assert serial.warehouse == "WH-RETURN"

        serial.serial_status = "available"
        database.session.commit()
        with pytest.raises(InventoryServiceError, match="serial entregado"):
            validate_batch_serial(line, outgoing=False, warehouse="WH-RETURN", allow_return=True)

        with pytest.raises(InventoryServiceError, match="exactamente una unidad"):
            validate_batch_serial(
                SimpleNamespace(item_code="SERIAL-ITEM", serial_no="SN-001", qty=Decimal("2"), uom="EA"),
                outgoing=False,
                warehouse="WH-RETURN",
            )


def test_incoming_serial_in_non_base_uom_passes_using_normalized_base_qty() -> None:
    """A normalized qty_in_base_uom of one must not be re-converted against the line UOM.

    Los productores ya almacenan qty_in_base_uom normalizado a la UOM base, por lo
    que el validador no debe convertirlo una segunda vez con la UOM de la linea.
    """
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Entity(code="serial", name="Serial", company_name="Serial", tax_id="SERIAL", currency="NIO"),
                UOM(code="EA", name="Each"),
                UOM(code="BOX", name="Box"),
                Item(
                    code="SERIAL-ITEM",
                    name="Serial item",
                    item_type="goods",
                    is_stock_item=True,
                    has_serial_no=True,
                    default_uom="EA",
                ),
                ItemUOMConversion(
                    item_code="SERIAL-ITEM",
                    from_uom="BOX",
                    to_uom="EA",
                    conversion_factor=Decimal("10"),
                ),
            ]
        )
        database.session.commit()
        line = SimpleNamespace(
            item_code="SERIAL-ITEM",
            serial_no="SN-NEW",
            qty=Decimal("0.1"),
            uom="BOX",
            qty_in_base_uom=Decimal("1"),
        )

        validate_batch_serial(line, outgoing=False, warehouse="WH-1")
