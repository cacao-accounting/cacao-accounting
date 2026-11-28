# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

"""#1452: la importacion de orden de venta conserva bodega por linea."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import Party, SalesOrder, SalesOrderItem, User, Warehouse, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company


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


def test_grid_publica_warehouse_por_linea_1452():
    """El grid emite el campo que el guardado de orden de venta consume."""
    template = Path(__file__).parents[1] / "cacao_accounting/templates/transaction_form_macros.html"
    content = template.read_text(encoding="utf-8")
    assert ":name=\"'warehouse_' + index\"" in content
    assert 'x-model="line.warehouse"' in content


def _cliente(app):
    """Cliente autenticado sobre la base aislada del escenario."""
    client = app.test_client()
    with app.app_context():
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def _payload(customer_id: str, marker: str, warehouse: str) -> dict[str, str]:
    """Formulario de orden con bodega de cabecera distinta a la línea."""
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": date(2026, 5, 15).isoformat(),
        "customer_id": customer_id,
        "remarks": marker,
        "warehouse": "BOD01",
        "item_code_0": "ART01",
        "item_name_0": "Artículo comercial",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
        "warehouse_0": warehouse,
    }


def test_orden_guarda_bodega_de_linea_1452(entorno_contable_aislado):
    """La bodega importada prevalece sobre la cabecera y persiste en la línea."""
    app = entorno_contable_aislado.app
    marker = f"SO-WH-{uuid4().hex[:8]}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["sales_order"])
        if database.session.execute(select(Warehouse).filter_by(code="BOD1452")).scalar_one_or_none() is None:
            database.session.add(Warehouse(code="BOD1452", name="Bodega línea 1452", company="cacao", is_active=True))
        database.session.commit()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())

    response = _cliente(app).post("/sales/sales-order/new", data=_payload(customer_id, marker, "BOD1452"))

    assert response.status_code == 302
    with app.app_context():
        order = database.session.execute(select(SalesOrder).filter_by(remarks=marker)).scalar_one()
        line = database.session.execute(select(SalesOrderItem).filter_by(sales_order_id=order.id)).scalar_one()
        assert line.warehouse == "BOD1452"


def test_orden_rechaza_bodega_inactiva_1452(entorno_contable_aislado):
    """Una bodega inválida no permite persistir la orden ni su línea."""
    app = entorno_contable_aislado.app
    marker = f"SO-WH-BAD-{uuid4().hex[:8]}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["sales_order"])
        database.session.add(Warehouse(code="BOD1452X", name="Bodega inactiva 1452", company="cacao", is_active=False))
        database.session.commit()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())

    response = _cliente(app).post("/sales/sales-order/new", data=_payload(customer_id, marker, "BOD1452X"))

    assert response.status_code == 200
    assert "La bodega BOD1452X está inactiva." in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(select(SalesOrder).filter_by(remarks=marker)).scalar_one_or_none() is None
