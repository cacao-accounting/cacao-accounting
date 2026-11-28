# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2340: el formulario de reuso solo precarga trazabilidad admitida.

El mapeo JavaScript debe conservar lote, serie y vencimiento de la línea
origen cuando el artículo los controla, y no introducirlos en artículos sin
esos controles ni fallar cuando el origen omite los campos.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_formulario_de_reuso_precarga_solo_la_trazabilidad_controlada():
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    script = r"""
const fs=require('fs');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit,factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({
  formKey:'stock.stock_entry',
  items:[
    {code:'IT-TRACE',name:'Trazable',default_uom:'EA',has_batch:true,has_serial_no:true,has_expiry_date:true},
    {code:'IT-PLAIN',name:'Sin control',default_uom:'EA',has_batch:false,has_serial_no:false,has_expiry_date:false}
  ],
  uoms:[]
});
const traced={item_code:'IT-TRACE',item_name:'Trazable',qty:'5',uom:'EA',rate:'2',
  source_type:'stock_entry',source_id:'se-1',source_item_id:'li-1',
  batch_id:'b-1',serial_no:'SN-1',expiry_date:'2027-01-31'};
const plain={item_code:'IT-PLAIN',item_name:'Sin control',qty:'3',uom:'EA',rate:'1',
  source_type:'stock_entry',source_id:'se-2',source_item_id:'li-2',
  batch_id:'b-2',serial_no:'SN-2',expiry_date:'2027-02-28'};
const missing={item_code:'IT-TRACE',item_name:'Trazable',qty:'1',uom:'EA',rate:'2',
  source_type:'stock_entry',source_id:'se-3',source_item_id:'li-3'};
const a=form.createLineFromSourceItem(traced);
const b=form.createLineFromSourceItem(plain);
const c=form.createLineFromSourceItem(missing);
process.stdout.write(JSON.stringify({
  traced:{batch_id:a.batch_id,serial_no:a.serial_no,expiry_date:a.expiry_date,has_batch:a.has_batch,has_serial_no:a.has_serial_no,has_expiry_date:a.has_expiry_date,qty:a.qty},
  plain:{batch_id:b.batch_id,serial_no:b.serial_no,expiry_date:b.expiry_date,has_batch:b.has_batch,has_serial_no:b.has_serial_no,has_expiry_date:b.has_expiry_date},
  missing:{batch_id:c.batch_id,serial_no:c.serial_no,expiry_date:c.expiry_date,qty:c.qty}
}));
"""
    result = subprocess.run(["node", "-e", script, str(js_path)], check=True, capture_output=True, text=True)
    out = json.loads(result.stdout)

    assert out["traced"] == {
        "batch_id": "b-1",
        "serial_no": "SN-1",
        "expiry_date": "2027-01-31",
        "has_batch": True,
        "has_serial_no": True,
        "has_expiry_date": True,
        "qty": 5,
    }
    assert out["plain"]["batch_id"] == ""
    assert out["plain"]["serial_no"] == ""
    assert out["plain"].get("expiry_date", "") == ""
    assert out["plain"]["has_batch"] is False
    assert out["missing"]["batch_id"] == ""
    assert out["missing"]["serial_no"] == ""
    assert out["missing"].get("expiry_date", "") == ""
    assert out["missing"]["qty"] == 1
