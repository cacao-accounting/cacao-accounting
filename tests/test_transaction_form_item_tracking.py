# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Transaction item changes clear stale batch and serial selections."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_transaction_form(js_path: Path, config: dict, script: str) -> str:
    """Run a behavior assertion against the production Alpine factory."""
    result = subprocess.run(
        ["node", "-e", script, str(js_path), json.dumps(config)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_transaction_form_item_tracking_is_scoped_to_the_selected_item():
    """Changing items clears old tracking while editing keeps valid selections."""
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    config = {
        "items": [
            {"code": "TRACKED-A", "name": "Tracked A", "has_batch": True, "has_serial_no": True},
            {"code": "TRACKED-B", "name": "Tracked B", "has_batch": True, "has_serial_no": True},
            {"code": "PLAIN", "name": "Plain"},
        ],
        "uoms": [],
    }
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
const edited = form.normalizeLine({
  item_code: 'TRACKED-A', batch_id: 'A-BATCH', serial_no: 'A-SERIAL',
  has_batch: false, has_serial_no: false
});
if (edited.batch_id !== 'A-BATCH' || edited.serial_no !== 'A-SERIAL') {
  throw new Error('editing discarded tracking values that belong to the selected item');
}
edited.item_code = 'PLAIN';
form.onItemChange(edited);
if (edited.has_batch || edited.has_serial_no || edited.batch_id || edited.batch_no || edited.serial_no) {
  throw new Error('changing to an untracked item retained previous tracking data');
}
const tracked = form.normalizeLine({ item_code: 'TRACKED-A', batch_id: 'OLD-BATCH', serial_no: 'OLD-SERIAL' });
tracked.item_code = 'TRACKED-B';
form.onItemChange(tracked);
if (!tracked.has_batch || !tracked.has_serial_no || tracked.batch_id || tracked.batch_no || tracked.serial_no) {
  throw new Error('changing between tracked items retained the previous item selections');
}
process.stdout.write(JSON.stringify({ edited, plain: edited, tracked }));
"""
    _run_transaction_form(js_path, config, script)


def test_clearing_item_does_not_restore_it_during_submission():
    """The cleared selection and serialized line stay empty through submit prep."""
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    template_path = Path(__file__).parents[1] / "cacao_accounting/templates/transaction_form_macros.html"
    config = {"items": [{"code": "ITEM-OLD", "name": "Old item", "default_uom": "EA"}], "uoms": []}
    script = r"""
const fs = require('fs');
let alpineInit;
let transactionFormFactory;
global.document = { addEventListener: (_name, callback) => { alpineInit = callback; } };
global.Alpine = { data: (_name, factory) => { transactionFormFactory = factory; } };
eval(fs.readFileSync(process.argv[1], 'utf8'));
alpineInit();
const form = transactionFormFactory(JSON.parse(process.argv[2]));
form.header.currency = 'NIO';
form.refreshCatalogPrice = async () => {};
const line = form.normalizeLine({ item_code: 'ITEM-OLD', item_name: 'Old item', uom: 'EA', qty: 2, rate: 4 });
form.onItemClear(line);
let hiddenValue = '';
form.$root = {
  querySelector(selector) {
    if (selector !== '[name="item_code_0"]') return null;
    return { set value(value) { hiddenValue = value; }, dispatchEvent() {} };
  }
};
form.lines = [line];
form.prepareSubmit({ preventDefault() {} });
const serialized = form.mapLinesToPayload()[0];
if (hiddenValue !== '' || serialized.item_code !== '' || line.item_code !== '') {
  throw new Error('submission restored an item after its selector was cleared');
}
process.stdout.write(JSON.stringify(serialized));
"""
    _run_transaction_form(js_path, config, script)
    template = template_path.read_text(encoding="utf-8")
    assert "onClear: function() { onItemClear(line); }" in template


def test_payment_party_and_external_counter_clear_callbacks_sync_form_state():
    """Invalidating either payment selector clears its serialized header field."""
    template_path = Path(__file__).parents[1] / "cacao_accounting/bancos/templates/bancos/pago_nuevo.html"
    template = template_path.read_text(encoding="utf-8")
    assert 'onClear: function() { header.party_id = ""; header.party_name = ""; }' in template
    assert 'header.external_counter_id = "";\n                header.external_number = "";' in template
