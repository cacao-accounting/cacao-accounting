# SPDX-License-Identifier: Apache-2.0
"""#1519: comparacion de tarifas en adjudicacion no pierde precision JS Number."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_purchase_sourcing_js_compares_rates_as_decimal_strings():
    js = Path("cacao_accounting/static/js/purchase-sourcing.js").read_text(encoding="utf-8")
    assert "normalizeRate" in js
    assert "compareRates" in js
    assert "Number(input.dataset.baseRate)" not in js
    assert "Number(input.dataset.rate)" not in js

    node_script = (
        "const fs=require('fs');"
        "const vm=require('vm');"
        "const code=fs.readFileSync('cacao_accounting/static/js/purchase-sourcing.js','utf8');"
        "const form={dataset:{offersInsufficient:'false'},querySelectorAll:(sel)=>{"
        "if(sel.includes('award_item_')) return ["
        "{name:'award_item_1',dataset:{rate:'2000000000000.0001'},checked:true},"
        "{name:'award_item_1',dataset:{rate:'2000000000000.0000'},checked:false}"
        "]; return [];},addEventListener:()=>{}};"
        "const reason={required:false};"
        "global.document={querySelector:()=>form,getElementById:()=>reason};"
        "vm.runInThisContext(code);"
        "console.log(reason.required);"
    )
    result = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "true"
