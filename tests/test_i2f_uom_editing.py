# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Stock entry editors preserve item-specific commercial units."""

from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Accounts,
    CostCenter,
    Entity,
    Item,
    ItemUOMConversion,
    Project,
    StockEntry,
    StockEntryItem,
    UOM,
    Unit,
    database,
)
from cacao_accounting.inventario import services as inventory_services
from cacao_accounting.inventario.routes import _stock_entry_item_choices
from cacao_accounting.inventario.services import (
    _delete_and_resave_stock_entry_items,
    _handle_stock_entry_edit_post,
    _render_stock_entry_edit_form,
    _render_stock_reconciliation_edit_form,
    _save_stock_entry_item,
    _update_stock_entry_from_form,
)


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
        assert saved_line.basic_rate == Decimal("5.0000")
        assert saved_line.amount == Decimal("10.0000")

        database.session.rollback()


def test_transaction_form_converts_uom_without_changing_stock_value(app, monkeypatch):
    """Changing UOM preserves physical quantity and the persisted line value."""
    suffix = uuid4().hex[:8].upper()
    base_uom = f"EA{suffix}"
    commercial_uom = f"BX{suffix}"
    item_code = f"ITEM-{suffix}"
    config = {
        "viewKey": "draft",
        "items": [
            {
                "code": item_code,
                "name": "Bolts",
                "default_uom": base_uom,
                "allowed_uoms": [base_uom, commercial_uom],
                "uom_factors": {base_uom: "1", commercial_uom: "12"},
            }
        ],
        "uoms": [{"code": base_uom, "name": "Each"}, {"code": commercial_uom, "name": "Box"}],
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
const config = JSON.parse(process.argv[2]);
const baseUom = config.items[0].default_uom;
const commercialUom = config.items[0].allowed_uoms[1];
const line = form.normalizeLine({item_code: config.items[0].code, item_name: 'Bolts', qty: 2, uom: commercialUom, rate: 5});
if (line.uom !== commercialUom || line.qty !== 2 || line.rate !== 5 || line.amount !== 10) {
  throw new Error('edit changed the stored commercial line before UOM conversion');
}
form.onUomChange(line, baseUom);
if (line.uom !== baseUom || line.qty !== 24) throw new Error('UOM change did not preserve base quantity');
if (Math.abs(line.rate - (5 / 12)) > 1e-9) throw new Error('UOM change did not convert the unit rate');
if (Math.abs(line.amount - 10) > 1e-9) throw new Error('UOM change did not preserve the line amount');
form.onUomChange(line, commercialUom);
if (line.uom !== commercialUom || Math.abs(line.qty - 2) > 1e-9) throw new Error('UOM roundtrip changed physical quantity');
if (Math.abs(line.rate - 5) > 1e-9 || Math.abs(line.amount - 10) > 1e-9) {
  throw new Error('UOM roundtrip changed unit rate or line amount');
}
form.onUomChange(line, baseUom);
process.stdout.write(JSON.stringify(line));
"""
    with app.app_context():
        database.session.add_all([UOM(code=base_uom, name="Each"), UOM(code=commercial_uom, name="Box")])
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
        entry = StockEntry(company="cacao", purpose="material_receipt", transaction_currency="NIO", base_currency="NIO")
        database.session.add(entry)
        database.session.flush()
        original_line = StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item_code,
            qty=Decimal("2"),
            uom=commercial_uom,
            qty_in_base_uom=Decimal("24"),
            basic_rate=Decimal("5"),
            amount=Decimal("10"),
        )
        database.session.add(original_line)
        database.session.flush()
        assert (original_line.qty, original_line.uom, original_line.basic_rate, original_line.amount) == (
            Decimal("2"),
            commercial_uom,
            Decimal("5"),
            Decimal("10"),
        )

        result = subprocess.run(
            ["node", "-e", script, str(js_path), json.dumps(config)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        converted_line = json.loads(result.stdout)
        assert converted_line["uom"] == base_uom
        assert converted_line["qty"] == 24
        assert converted_line["rate"] == pytest.approx(5 / 12)
        assert converted_line["amount"] == pytest.approx(10)

        monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
        monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)
        form_data = {
            "purpose": "material_receipt",
            "company": "cacao",
            "posting_date": "2026-11-14",
            "transaction_currency": "NIO",
            "item_code_0": item_code,
            "qty_0": str(converted_line["qty"]),
            "uom_0": converted_line["uom"],
            "rate_0": str(converted_line["rate"]),
            "amount_0": str(converted_line["amount"]),
        }
        with app.test_request_context("/stock-entry/test/edit", method="POST", data=form_data):
            inventory_services._update_stock_entry_from_form(entry)
            _delete_and_resave_stock_entry_items(entry)

        saved_line = database.session.execute(
            database.select(StockEntryItem).filter_by(stock_entry_id=entry.id, item_code=item_code)
        ).scalar_one()
        assert saved_line.qty == Decimal("24.000000000")
        assert saved_line.uom == base_uom
        assert saved_line.qty_in_base_uom == Decimal("24.000000000")
        assert saved_line.basic_rate == Decimal("0.4167")
        assert saved_line.amount == Decimal("10.0000")
        database.session.rollback()


def test_stock_entry_edit_renderer_reuses_rejected_post_lines(app):
    """A rejected edit renders posted line data instead of the persisted snapshot."""

    class TransactionFormParser(HTMLParser):
        """Read the transaction configuration attached to the real edit form."""

        config = None

        def handle_starttag(self, tag, attrs):
            config_value = dict(attrs).get("x-data")
            if tag == "form" and config_value:
                self.config = config_value

    with app.app_context():
        entry = StockEntry(company="cacao", purpose="material_receipt", remarks="Persisted")
        database.session.add(entry)
        database.session.flush()
        form_data = {
            "purpose": "material_receipt",
            "company": "cacao",
            "naming_series": "SERIES-2",
            "currency": "NIO",
            "posting_date": "2026-11-14",
            "from_warehouse": "FROM-WH",
            "to_warehouse": "TO-WH",
            "remarks": "Rejected draft",
            "item_code_0": "ART01",
            "item_name_0": "Edited name",
            "qty_0": "3",
            "uom_0": "BOX",
            "rate_0": "7.5",
            "amount_0": "22.5",
            "batch_id_0": "",
            "serial_no_0": "",
            "account_0": "ACCOUNT-LINE",
            "cost_center_0": "COST-LINE",
            "unit_0": "UNIT-LINE",
            "project_0": "PROJECT-LINE",
            "remarks_0": "Line note",
        }
        with app.test_request_context("/stock-entry/test/edit", method="POST", data=form_data):
            response = _render_stock_entry_edit_form(entry, [], [], formulario=None)

        parser = TransactionFormParser()
        parser.feed(response)
        rendered_config = json.loads(parser.config[parser.config.index("(") + 1 : -1])
        assert rendered_config["initialHeader"]["remarks"] == "Rejected draft"
        assert rendered_config["initialHeader"]["naming_series"] == "SERIES-2"
        assert rendered_config["initialHeader"]["currency"] == "NIO"
        assert rendered_config["initialHeader"]["from_warehouse"] == "FROM-WH"
        assert rendered_config["initialHeader"]["to_warehouse"] == "TO-WH"
        assert rendered_config["initialLines"] == [
            {
                "item_code": "ART01",
                "item_name": "Edited name",
                "qty": "3",
                "uom": "BOX",
                "rate": "7.5",
                "amount": "22.5",
                "batch_id": "",
                "serial_no": "",
                "source_type": "",
                "source_id": "",
                "source_item_id": "",
                "account": "ACCOUNT-LINE",
                "cost_center": "COST-LINE",
                "unit": "UNIT-LINE",
                "project": "PROJECT-LINE",
                "remarks": "Line note",
            }
        ]
        database.session.rollback()


def test_stock_reconciliation_edit_renderer_reuses_rejected_post(app):
    """A rejected reconciliation retains its dimensions, warehouse, and counts."""

    class ReconciliationFormParser(HTMLParser):
        """Read the reconciliation configuration attached to the real edit form."""

        config = None

        def handle_starttag(self, tag, attrs):
            config_value = dict(attrs).get("x-data")
            if tag == "form" and config_value:
                self.config = config_value

    with app.app_context():
        entry = StockEntry(company="cacao", purpose="stock_reconciliation", remarks="Persisted")
        database.session.add(entry)
        database.session.flush()
        form_data = {
            "purpose": "stock_reconciliation",
            "company": "cacao",
            "posting_date": "2026-11-14",
            "naming_series": "SERIES-3",
            "from_warehouse": "FROM-WH",
            "to_warehouse": "TO-WH",
            "adjustment_account_id": "ACCOUNT-1",
            "cost_center_code": "CC-1",
            "unit_code": "UNIT-1",
            "project_code": "PROJECT-1",
            "remarks": "Rejected reconciliation",
            "item_code_0": "ART01",
            "uom_0": "EA",
            "warehouse_0": "COUNT-WH",
            "current_qty_0": "10",
            "counted_qty_0": "8",
            "current_valuation_rate_0": "2",
            "target_valuation_rate_0": "2",
            "current_stock_value_0": "20",
            "target_stock_value_0": "16",
        }
        with app.test_request_context("/stock-entry/test/edit", method="POST", data=form_data):
            response = _render_stock_reconciliation_edit_form(entry, [], [], formulario=None)

        parser = ReconciliationFormParser()
        parser.feed(response)
        rendered_config = json.loads(parser.config[parser.config.index("(") + 1 : -1])
        assert rendered_config["header"]["remarks"] == "Rejected reconciliation"
        assert rendered_config["header"]["cost_center_code"] == "CC-1"
        assert rendered_config["header"]["naming_series"] == "SERIES-3"
        assert rendered_config["header"]["to_warehouse"] == "TO-WH"
        assert rendered_config["lines"][0]["counted_qty"] == "8"
        assert rendered_config["lines"][0]["warehouse"] == "COUNT-WH"
        database.session.rollback()


def test_stock_entry_domain_error_rolls_back_and_keeps_editable_response(app, monkeypatch):
    """A domain failure rolls back mutations and signals the route to re-render."""
    with app.app_context():
        entry = StockEntry(company="cacao", purpose="material_receipt", remarks="Persisted")
        database.session.add(entry)
        database.session.commit()
        entry_id = entry.id

        def fail_after_header_update(registro):
            registro.remarks = "Must roll back"
            raise ValueError("invalid stock line")

        monkeypatch.setattr(inventory_services, "_update_stock_entry_from_form", fail_after_header_update)
        with app.test_request_context("/stock-entry/test/edit", method="POST", data={"remarks": "Rejected"}):
            response = _handle_stock_entry_edit_post(entry)

        persisted = database.session.get(StockEntry, entry_id)
        assert response is None
        assert persisted is not None and persisted.remarks == "Persisted"
        database.session.rollback()


def test_stock_entry_update_preserves_uncontrolled_header_values(app, monkeypatch):
    """Normal stock-entry edits keep legacy account and dimensions absent from the form."""
    entry = StockEntry(
        company="cacao",
        purpose="material_receipt",
        posting_date=None,
        transaction_currency="USD",
        base_currency="NIO",
        from_warehouse="BOD01",
        to_warehouse="BOD01",
        adjustment_account_id="existing-adjustment-account",
        cost_center_code="EXISTING-CC",
        unit_code="EXISTING-UNIT",
        project_code="EXISTING-PROJECT",
        remarks="Existing note",
        naming_series_id="EXISTING-SERIES",
    )
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)

    with app.test_request_context(
        "/stock-entry/test/edit",
        method="POST",
        data={
            "purpose": "material_receipt",
            "company": "cacao",
            "posting_date": "2026-11-14",
            "currency": "USD",
        },
    ):
        _update_stock_entry_from_form(entry)

    assert entry.transaction_currency == "USD"
    assert entry.from_warehouse == "BOD01"
    assert entry.to_warehouse == "BOD01"
    assert entry.adjustment_account_id == "existing-adjustment-account"
    assert entry.cost_center_code == "EXISTING-CC"
    assert entry.unit_code == "EXISTING-UNIT"
    assert entry.project_code == "EXISTING-PROJECT"
    assert entry.remarks == "Existing note"

    class EditFormParser(HTMLParser):
        """Read initial header values from the rendered edit form."""

        config = None

        def handle_starttag(self, tag, attrs):
            config_value = dict(attrs).get("x-data")
            if tag == "form" and config_value:
                self.config = config_value

    with app.app_context(), app.test_request_context("/stock-entry/test/edit"):
        response = _render_stock_entry_edit_form(entry, [], [])
    parser = EditFormParser()
    parser.feed(response)
    rendered_config = json.loads(parser.config[parser.config.index("(") + 1 : -1])
    assert rendered_config["initialHeader"] == {
        "company": "cacao",
        "naming_series": "EXISTING-SERIES",
        "currency": "USD",
        "posting_date": "2026-11-14",
        "from_warehouse": "BOD01",
        "to_warehouse": "BOD01",
        "remarks": "Existing note",
    }


def test_reconciliation_edit_accepts_only_company_owned_explicit_dimensions(app, monkeypatch):
    """Reconciliation header controls update dimensions after company validation."""
    suffix = uuid4().hex[:6].upper()
    account = Accounts(
        entity="cacao",
        code=f"ADJ-{suffix}",
        name="Inventory adjustment",
        active=True,
        enabled=True,
        group=False,
    )
    cost_center = CostCenter(
        entity="cacao",
        code=f"CC{suffix}",
        name="Inventory center",
        active=True,
        enabled=True,
        default=False,
        group=False,
    )
    unit = Unit(entity="cacao", code=f"U{suffix}", name="Inventory unit", enabled=True)
    project = Project(entity="cacao", code=f"P{suffix}", name="Inventory project", enabled=True)

    with app.app_context():
        database.session.add_all([account, cost_center, unit, project])
        database.session.flush()
        entry = StockEntry(
            company="cacao",
            purpose="stock_reconciliation",
            transaction_currency="NIO",
            base_currency="NIO",
            adjustment_account_id=None,
        )
        monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
        with app.test_request_context(
            "/stock-entry/test/edit",
            method="POST",
            data={
                "purpose": "stock_reconciliation",
                "company": "cacao",
                "posting_date": "2026-11-14",
                "currency": "NIO",
                "adjustment_account_id": account.id,
                "cost_center_code": cost_center.code,
                "unit_code": unit.code,
                "project_code": project.code,
            },
        ):
            _update_stock_entry_from_form(entry)

        assert entry.adjustment_account_id == account.id
        assert entry.cost_center_code == cost_center.code
        assert entry.unit_code == unit.code
        assert entry.project_code == project.code

        other_company = Entity(
            code=f"O{suffix}",
            name="Other test company",
            company_name=f"Other test company {suffix}",
            tax_id=f"OT{suffix}",
            currency="NIO",
            enabled=True,
            status="default",
        )
        foreign_account = Accounts(
            entity=other_company.code,
            code=f"F-{suffix}",
            name="Foreign adjustment",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(other_company)
        database.session.flush()
        database.session.add(foreign_account)
        database.session.flush()
        with app.test_request_context(
            "/stock-entry/test/edit",
            method="POST",
            data={
                "purpose": "stock_reconciliation",
                "company": "cacao",
                "posting_date": "2026-11-14",
                "currency": "NIO",
                "adjustment_account_id": foreign_account.id,
                "cost_center_code": cost_center.code,
                "unit_code": unit.code,
                "project_code": project.code,
            },
        ):
            with pytest.raises(ValueError, match="pertenecer a la compañía"):
                _update_stock_entry_from_form(entry)
        assert entry.adjustment_account_id == account.id
        database.session.rollback()
