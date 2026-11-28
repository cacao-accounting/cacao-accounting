# SPDX-License-Identifier: Apache-2.0
"""#1512: serializacion de montos en pago no pierde precision decimal."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def test_payment_to_currency_string_preserves_decimal_precision():
    html = Path("cacao_accounting/bancos/templates/bancos/pago_nuevo.html").read_text(encoding="utf-8")
    match = re.search(r"toCurrencyString:\s*function \(value\) \{.*?\n\s*\},", html, re.DOTALL)
    assert match, "toCurrencyString not found"
    fn = "const toCurrencyString = " + match.group(0).replace("toCurrencyString:", "").rstrip(",")

    node_script = (
        fn
        + "; console.log(toCurrencyString('9999999999999.9999'));"
        + " console.log(toCurrencyString('123456789012.3456'));"
        + " console.log(toCurrencyString('0012.3400'));"
        + " console.log(toCurrencyString('-0.0000'));"
    )
    result = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    assert lines == ["9999999999999.9999", "123456789012.3456", "12.34", "0"]


def test_payment_alpine_payload_preserves_high_precision_amounts():
    """El flujo completo normaliza y serializa la asignación sin pasar por Number."""
    html = Path("cacao_accounting/bancos/templates/bancos/pago_nuevo.html").read_text(encoding="utf-8")
    match = re.search(r"globalThis\.paymentEntryForm = function \(config\) \{.*?\n  \};", html, re.DOTALL)
    assert match, "paymentEntryForm not found"
    source = re.sub(r"\{\{.*?\}\}", "x", match.group(0), flags=re.DOTALL)
    script = (
        "globalThis.cacaoLocalIsoDate=()=> '2026-11-01';"
        "function cloneModalLine(line){return line ? {...line} : null;}" + source + """
const form = globalThis.paymentEntryForm({initial: {
  company: 'cacao', currency: 'NIO', posting_date: '2026-11-01',
  paid_amount: '9999999999999.9999',
  lines: [{allocated_amount: '9999999999999.9999', outstanding_amount: '9999999999999.9999',
    discount_amount: '0', gain_loss_amount: '0', payment_exchange_rate: '1', currency: 'NIO'}]
}});
form.header.bank_account_id = 'BA-1';
form.prepareSubmit({preventDefault(){throw new Error('unexpected validation');}});
const payload = JSON.parse(form.payload);
console.log(JSON.stringify({paid: payload.paid_amount, allocated: payload.lines[0].allocated_amount,
  payment: payload.lines[0].payment_amount, integerSum: form.decimalAdd('1000', '0')}));
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {
        "paid": "9999999999999.9999",
        "allocated": "9999999999999.9999",
        "payment": "9999999999999.9999",
        "integerSum": "1000",
    }


def test_transaction_form_serializes_line_amounts_without_binary_float():
    """El formulario compartido conserva tasa e importe decimales de alta precisión."""
    js_path = Path("cacao_accounting/static/js/transaction-form.js")
    script = r"""
const fs=require('fs');
const code=fs.readFileSync(process.argv[1],'utf8');
let alpineInit,factory;
global.document={getElementById:()=>null,addEventListener:(n,cb)=>{alpineInit=cb;}};
global.Alpine={data:(n,f)=>{factory=f;}};
global.bootstrap={Modal:{getOrCreateInstance:()=>({show(){},hide(){}})}};
eval(code); alpineInit();
const form=factory({formKey:'sales.order',items:[],uoms:[]});
const line={...form.newLine(), qty:'1', rate:'9999999999999.9999', amount:'9999999999999.9999'};
const serialized=form._serializeLine(line);
process.stdout.write(JSON.stringify({rate:serialized.rate,amount:serialized.amount}));
"""
    result = subprocess.run(["node", "-e", script, str(js_path)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"rate": "9999999999999.9999", "amount": "9999999999999.9999"}


def test_payment_tax_summary_recalculates_without_reference_error():
    """El resumen fiscal usa la variable separada y conserva todos los totales."""
    html = Path("cacao_accounting/bancos/templates/bancos/pago_nuevo.html").read_text(encoding="utf-8")
    match = re.search(r"globalThis\.paymentEntryForm = function \(config\) \{.*?\n  \};", html, re.DOTALL)
    assert match, "paymentEntryForm not found"
    source = re.sub(r"\{\{.*?\}\}", "x", match.group(0), flags=re.DOTALL)
    script = (
        "globalThis.cacaoLocalIsoDate=()=> '2026-11-01';"
        "function cloneModalLine(line){return line ? {...line} : null;}" + source + """
const form = globalThis.paymentEntryForm({initial: {
  company: 'cacao', currency: 'NIO', posting_date: '2026-11-01', paid_amount: '100',
  lines: [{allocated_amount: '100', payment_amount: '100', outstanding_amount: '100', discount_amount: '0',
    gain_loss_amount: '0', payment_exchange_rate: '1', currency: 'NIO'}]
}});
form.taxCharges.lines = [
  {type: 'tax', amount: '15', included_in_price: false, affects_document_total: true,
    accounting_treatment: 'expense'},
  {type: 'tax', amount: '5', included_in_price: false, affects_document_total: true,
    accounting_treatment: 'capitalizable_inventory_cost'},
  {type: 'tax', amount: '7', included_in_price: false, affects_document_total: true,
    accounting_treatment: 'separate_tax_account'},
  {type: 'withholding', amount: '3', included_in_price: false, affects_document_total: true,
    accounting_treatment: 'withholding'}
];
form.recalculateTaxSummary();
console.log(JSON.stringify(form.taxCharges.summary));
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {
        "subtotal": "100",
        "document_tax_total": "27",
        "capitalizable_tax_total": "5",
        "separate_tax_total": "7",
        "withholding_total": "3",
        "grand_total": "127",
    }
