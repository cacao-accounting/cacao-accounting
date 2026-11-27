# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

"""#1452: la importacion de orden de venta conserva bodega por linea."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_sales_order_import_preserves_line_warehouse_1452():
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    script = r"""
const fs=require('fs');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit,factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({formKey:'sales.order',items:[{code:'ITEM-1',name:'Item',default_uom:'EA'}],uoms:[]});
form.importModal.doctype='sales_order';
form.importModal.parsedRows=[{item_code:'ITEM-1',quantity:'2',uom:'EA',rate:'10',warehouse:'WH-B'}];
form.importModal.isValidated=true;
form.lines=[];
form.insertImportedLines();
process.stdout.write(JSON.stringify({warehouse:form.lines[0].warehouse}));
"""
    result = subprocess.run(["node", "-e", script, str(js_path)], check=True, capture_output=True, text=True)
    out = json.loads(result.stdout)
    assert out["warehouse"] == "WH-B"
