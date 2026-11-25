// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose MORENO Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const nativeEvent = globalThis.Event;
const nativeCustomEvent = globalThis.CustomEvent;
const TEMPLATES = path.join(__dirname, '..', '..', 'bancos', 'templates', 'bancos');

function readTemplate(name) {
  return fs.readFileSync(path.join(TEMPLATES, name), 'utf8');
}

function extractFunction(source, attribute, marker) {
  const matches = [...source.matchAll(new RegExp(`${attribute}="(function\\([^)]*\\)\\{[\\s\\S]*?\\})"`, 'g'))];
  const match = matches.find((candidate) => candidate[1].includes(marker));
  assert.ok(match, `No se encontró ${attribute} con ${marker}`);
  return match[1];
}

function extractScript(source, marker) {
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes(marker));
  assert.ok(script, `No se encontró el script con ${marker}`);
  return script.replace(/<script>|<\/script>/g, '');
}

describe('bank selector clear synchronization', function () {
  afterEach(function () {
    delete globalThis.document;
    if (nativeEvent === undefined) delete globalThis.Event;
    else globalThis.Event = nativeEvent;
    if (nativeCustomEvent === undefined) delete globalThis.CustomEvent;
    else globalThis.CustomEvent = nativeCustomEvent;
    delete globalThis.pettyCashFundSteps;
    delete globalThis.bankNoteForm;
    delete globalThis.cacaoLocalIsoDate;
  });

  it('clears and restores the petty cash currency and amount step', function () {
    const source = readTemplate('caja_chica_gasto_nuevo.html');
    const onSelectSource = extractFunction(source, 'on_select', 'opt.currency');
    const onClearSource = extractFunction(source, 'on_clear', 'pc_currency');
    const fundScript = extractScript(source, 'fund-selected').replace(
      '{{ fund_amount_steps|tojson }}',
      '{"F-USD":"0.0001"}'
    );
    const dom = new JSDOM('<!doctype html><html><body><input id="pc_currency"><input id="amount" step="0.01"></body></html>');
    globalThis.document = dom.window.document;
    globalThis.CustomEvent = dom.window.CustomEvent;
    // eslint-disable-next-line no-eval
    (0, eval)(fundScript);
    // eslint-disable-next-line no-eval
    const onSelect = (0, eval)(`(${onSelectSource})`);
    // eslint-disable-next-line no-eval
    const onClear = (0, eval)(`(${onClearSource})`);

    const currency = document.getElementById('pc_currency');
    const amount = document.getElementById('amount');
    currency.value = 'NIO';
    amount.step = '0.0001';

    onClear();
    assert.strictEqual(currency.value, '');
    assert.strictEqual(amount.step, '0.01');

    onSelect({ currency: 'USD', value: 'F-USD' });
    assert.strictEqual(currency.value, 'USD');
    assert.strictEqual(amount.step, '0.0001');
  });

  it('dispatches the company filter event when the bank note company changes', function () {
    const source = readTemplate('nota_nueva.html');
    const noteScript = extractScript(source, 'bankNoteForm');
    const dom = new JSDOM('<!doctype html><html><body><input id="company_val" value="OLD"></body></html>');
    globalThis.document = dom.window.document;
    globalThis.Event = dom.window.Event;
    globalThis.cacaoLocalIsoDate = () => '2026-01-01';
    // eslint-disable-next-line no-eval
    (0, eval)(noteScript);

    const component = globalThis.bankNoteForm({ paymentType: 'debit_note' });
    const watchers = {};
    component.$watch = (expression, callback) => {
      watchers[expression] = callback;
    };
    component.$nextTick = (callback) => callback();
    const events = [];
    const companyValue = document.getElementById('company_val');
    companyValue.addEventListener('input', () => events.push('input'));
    companyValue.addEventListener('change', () => events.push('change'));
    component.init();

    component.header.bank_account_id = 'BANK-OLD';
    component.header.currency = 'NIO';
    companyValue.value = 'NEW';
    component.header.company = 'NEW';
    watchers['header.company']();

    assert.strictEqual(component.header.bank_account_id, '');
    assert.strictEqual(component.header.currency, '');
    assert.deepStrictEqual(events, ['input', 'change']);
  });
});
