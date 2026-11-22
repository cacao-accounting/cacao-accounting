# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Transaction item changes clear stale batch and serial selections."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


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
    subprocess.run(
        ["node", "-e", script, str(js_path), json.dumps(config)],
        check=True,
        capture_output=True,
        text=True,
    )
