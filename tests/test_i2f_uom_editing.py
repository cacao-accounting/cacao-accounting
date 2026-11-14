# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Stock entry editors preserve item-specific commercial units."""

from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from cacao_accounting.database import Item, ItemUOMConversion, StockEntry, StockEntryItem, UOM, database
from cacao_accounting.inventario.routes import _stock_entry_item_choices
from cacao_accounting.inventario.services import _save_stock_entry_item


def test_stock_entry_item_catalog_exposes_configured_uoms_and_base_factors(app):
    """The editor can retain a commercial UOM and convert its quantity to base units."""
    suffix = uuid4().hex[:8].upper()
    base_uom = f"EA{suffix}"
    commercial_uom = f"BX{suffix}"
    item_code = f"ITEM-{suffix}"

    with app.app_context():
        database.session.add_all(
            [
                UOM(code=base_uom, name="Each"),
                UOM(code=commercial_uom, name="Box"),
            ]
        )
        database.session.flush()
        item = Item(
            code=item_code,
            name="Bolts",
            item_type="goods",
            is_stock_item=True,
            default_uom=base_uom,
        )
        database.session.add(item)
        database.session.flush()
        database.session.add(
            ItemUOMConversion(
                item_code=item_code,
                from_uom=commercial_uom,
                to_uom=base_uom,
                conversion_factor=Decimal("12"),
            )
        )
        database.session.flush()

        choice = next(choice for choice in _stock_entry_item_choices() if choice["code"] == item_code)

        assert choice["allowed_uoms"] == [base_uom, commercial_uom]
        assert choice["uom_factors"] == {base_uom: "1", commercial_uom: "12.000000000"}
        assert Decimal("2") * Decimal(str(choice["uom_factors"][commercial_uom])) == Decimal("24")

        entry = StockEntry(company="cacao", purpose="receipt")
        database.session.add(entry)
        database.session.flush()
        with app.test_request_context(
            "/stock-entry/new",
            method="POST",
            data={"qty_0": "2", "uom_0": commercial_uom, "rate_0": "5", "item_code_0": item_code},
        ):
            _save_stock_entry_item(entry, 0, item_code)
        database.session.flush()
        saved_line = database.session.execute(
            database.select(StockEntryItem).filter_by(stock_entry_id=entry.id, item_code=item_code)
        ).scalar_one()
        assert saved_line.qty == Decimal("2")
        assert saved_line.uom == commercial_uom
        assert saved_line.qty_in_base_uom == Decimal("24.000000000")

        database.session.rollback()


def test_transaction_form_preserves_and_converts_commercial_uom(app):
    """The production Alpine form keeps the edit quantity and converts it on UOM change."""
    config = {
        "viewKey": "draft",
        "items": [
            {
                "code": "BOLT",
                "name": "Bolts",
                "default_uom": "EA",
                "allowed_uoms": ["EA", "BX"],
                "uom_factors": {"EA": "1", "BX": "12"},
            }
        ],
        "uoms": [{"code": "EA", "name": "Each"}, {"code": "BX", "name": "Box"}],
    }
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    script = r"""
const fs = require('fs');
let alpineInit;
let transactionFormFactory;
global.document = { addEventListener: (_name, callback) => { alpineInit = callback; } };
global.Alpine = { data: (_name, factory) => { transactionFormFactory = factory; } };
eval(fs.readFileSync(process.argv[1], 'utf8'));
alpineInit();
const form = transactionFormFactory(JSON.parse(process.argv[2]));
form.refreshCatalogPrice = async () => {};
const line = form.normalizeLine({item_code: 'BOLT', item_name: 'Bolts', qty: 2, uom: 'BX', rate: 5});
if (line.uom !== 'BX' || line.qty !== 2) throw new Error('edit changed the stored commercial quantity');
form.onUomChange(line, 'EA');
if (line.uom !== 'EA' || line.qty !== 24) throw new Error('UOM change did not preserve base quantity');
"""
    result = subprocess.run(
        ["node", "-e", script, str(js_path), json.dumps(config)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
