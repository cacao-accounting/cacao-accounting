"""Regression coverage for serialized sales returns."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Item, SerialNumber, UOM, database
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
