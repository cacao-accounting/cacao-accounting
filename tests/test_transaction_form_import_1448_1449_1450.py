# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresiones de importación JS para #1448, #1449 y #1450."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_js(script: str) -> dict:
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    result = subprocess.run(
        ["node", "-e", script, str(js_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_map_imported_rows_rejects_duplicate_headers_1449():
    script = r"""
const fs=require('fs'),vm=require('vm');
const code=fs.readFileSync(process.argv[1],'utf8');
function grab(n){const m=code.match(new RegExp('function '+n+'[\\s\\S]*?\\n  }'));return m?m[0]:'';}
const src=['normalizeImportHeader','findImportColumnIndex','mapImportedRows'].map(grab).join('\n');
const sb={console}; vm.createContext(sb); vm.runInContext(src,sb);
const schema={columns:[
  {key:'item_code',label:'Artículo',aliases:[]},
  {key:'quantity',label:'Cantidad',aliases:['qty']},
  {key:'uom',label:'Unidad',aliases:[]},
  {key:'rate',label:'Precio',aliases:[]}
]};
const mapped=sb.mapImportedRows([['Artículo','Cantidad','Cantidad','Unidad','Precio'],['ITEM-1','2','200','EA','50']], schema);
process.stdout.write(JSON.stringify(mapped));
"""
    mapped = _run_js(script)
    assert mapped["rows"] == []
    assert mapped["errors"]
    assert mapped["errors"][0]["field"] == "quantity"


def test_sales_quotation_import_applies_discount_1448():
    script = r"""
const fs=require('fs'),vm=require('vm');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit, factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({formKey:'sales.quotation', items:[], uoms:[]});
form.importModal.doctype='sales_quotation';
form.importModal.schema={columns:[{key:'item_code'},{key:'quantity'},{key:'uom'},{key:'rate'},{key:'discount_percentage'}]};
form.importModal.parsedRows=[{item_code:'ITEM-1',quantity:'2',uom:'EA',rate:'50',discount_percentage:'10'}];
form.importModal.isValidated=true;
form.lines=[];
form.insertImportedLines();
const line=form.lines[0];
process.stdout.write(JSON.stringify({discount_percentage:line.discount_percentage, amount:line.amount}));
"""
    out = _run_js(script)
    assert float(out["discount_percentage"]) == 10.0
    assert float(out["amount"]) == 90.0


def test_stock_entry_import_preserves_line_warehouses_1450():
    script = r"""
const fs=require('fs'),vm=require('vm');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit, factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({formKey:'inventory.stock_entry', items:[], uoms:[]});
form.importModal.doctype='stock_entry';
form.importModal.schema={columns:[{key:'item_code'},{key:'quantity'},{key:'uom'},{key:'rate'},{key:'source_warehouse'},{key:'target_warehouse'}]};
form.importModal.parsedRows=[{item_code:'ITEM-1',quantity:'2',uom:'EA',rate:'10',source_warehouse:'WH-A',target_warehouse:'WH-B'}];
form.importModal.isValidated=true;
form.lines=[];
form.insertImportedLines();
const line=form.lines[0];
process.stdout.write(JSON.stringify({source_warehouse:line.source_warehouse,target_warehouse:line.target_warehouse}));
"""
    out = _run_js(script)
    assert out["source_warehouse"] == "WH-A"
    assert out["target_warehouse"] == "WH-B"
