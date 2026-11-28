# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

"""#1451: la descripcion importada prevalece sobre el catalogo."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_imported_description_is_preserved_1451():
    js_path = Path(__file__).parents[1] / "cacao_accounting/static/js/transaction-form.js"
    script = r"""
const fs=require('fs');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit,factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({formKey:'sales.quotation',items:[{code:'ITEM-1',name:'Nombre catalogo',default_uom:'EA'}],uoms:[]});
form.importModal.doctype='sales_quotation';
form.importModal.parsedRows=[{item_code:'ITEM-1',description:'Desc linea importada',quantity:'2',uom:'EA',rate:'10'}];
form.importModal.isValidated=true;
form.lines=[];
form.insertImportedLines();
process.stdout.write(JSON.stringify({item_name:form.lines[0].item_name, description:form.lines[0].description}));
"""
    result = subprocess.run(["node", "-e", script, str(js_path)], check=True, capture_output=True, text=True)
    out = json.loads(result.stdout)
    assert out["item_name"] == "Desc linea importada"
    assert out["description"] == "Desc linea importada"
