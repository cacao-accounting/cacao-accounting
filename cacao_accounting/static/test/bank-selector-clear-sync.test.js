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

function extractSmartSelectConfig(source, marker) {
  const matches = [...source.matchAll(/x-data='smartSelect\((\{[\s\S]*?\})\)'/g)];
  const match = matches.find((candidate) => candidate[1].includes(marker));
  assert.ok(match, `No se encontró smartSelect con ${marker}`);
  // eslint-disable-next-line no-eval
  return (0, eval)(`(${match[1]})`);
}

function loadSmartSelect(dom) {
  let factory = null;
  globalThis.document = dom.window.document;
  globalThis.Alpine = {
    data: (name, create) => {
      if (name === 'smartSelect') factory = create;
    },
  };
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ results: [] }) });
  const modulePath = require.resolve('../js/smart-select.js');
  delete require.cache[modulePath];
  require(modulePath);
  dom.window.document.dispatchEvent(new dom.window.Event('alpine:init'));
  return factory;
}

function dispatchFilterChange(dom, element, value) {
  element.value = value;
  element.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  element.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
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
    delete globalThis.Alpine;
    delete globalThis.fetch;
    delete globalThis.header;
    delete globalThis.alert;
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

  it('clears the dependent bank note selector when the company changes', function () {
    const dom = new JSDOM('<!doctype html><html><body><input id="company" value="OLD"></body></html>');
    const factory = loadSmartSelect(dom);
    const header = { bank_account_id: 'BANK-OLD', currency: 'NIO' };
    globalThis.header = header;
    const config = extractSmartSelectConfig(readTemplate('nota_nueva.html'), 'name: "bank_account_id"');
    const component = factory(config);
    component.selectedValue = 'BANK-OLD';
    component.selectedLabel = 'Cuenta anterior';
    component.search = 'Cuenta anterior';
    component.options = [{ value: 'BANK-OLD', display_name: 'Cuenta anterior' }];
    component.init();

    dispatchFilterChange(dom, document.getElementById('company'), 'NEW');

    assert.strictEqual(component.selectedValue, '');
    assert.strictEqual(component.search, '');
    assert.deepStrictEqual(component.options, []);
    assert.strictEqual(header.bank_account_id, '');
    assert.strictEqual(header.currency, '');
  });

  it('clears the bank note header when the selected account is edited', function () {
    const dom = new JSDOM('<!doctype html><html><body><input id="company" value="OLD"></body></html>');
    const factory = loadSmartSelect(dom);
    const header = { bank_account_id: 'BANK-OLD', currency: 'NIO' };
    globalThis.header = header;
    const config = extractSmartSelectConfig(readTemplate('nota_nueva.html'), 'name: "bank_account_id"');
    const component = factory(config);
    component.selectedValue = 'BANK-OLD';
    component.selectedLabel = 'Cuenta anterior';
    component.search = 'Cuenta anterior';
    component.options = [{ value: 'BANK-OLD', display_name: 'Cuenta anterior' }];
    component.init();

    component.onInput({ target: { value: 'Otra cuenta' } });

    assert.strictEqual(component.selectedValue, '');
    assert.strictEqual(header.bank_account_id, '');
    assert.strictEqual(header.currency, '');
  });

  it('blocks the bank note submit without a bank account and sends the selected one', function () {
    const source = readTemplate('nota_nueva.html');
    const noteScript = extractScript(source, 'bankNoteForm');
    const dom = new JSDOM('<!doctype html><html><body></body></html>');
    globalThis.document = dom.window.document;
    globalThis.Event = dom.window.Event;
    globalThis.cacaoLocalIsoDate = () => '2026-01-01';
    globalThis.alert = () => {};
    // eslint-disable-next-line no-eval
    (0, eval)(noteScript);

    const component = globalThis.bankNoteForm({ paymentType: 'debit_note' });
    component.header.company = 'COMP';
    component.header.paid_amount = 10;
    const blocked = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(blocked);
    assert.strictEqual(blocked.prevented, true);

    component.header.bank_account_id = 'BANK-NEW';
    const accepted = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(accepted);
    assert.strictEqual(accepted.prevented, false);
    const payload = JSON.parse(component.payload);
    assert.strictEqual(payload.company, 'COMP');
    assert.strictEqual(payload.bank_account_id, 'BANK-NEW');
  });

  it('clears the transfer currencies and resets the exchange rate', function () {
    const source = readTemplate('transferencia_nueva.html');
    const originClearSource = extractFunction(source, 'on_clear', 'header.currency');
    const targetClearSource = extractFunction(source, 'on_clear', 'header.target_currency');
    globalThis.header = { currency: 'NIO', target_currency: 'USD', exchange_rate: 36 };
    // eslint-disable-next-line no-eval
    const originClear = (0, eval)(`(${originClearSource})`);
    // eslint-disable-next-line no-eval
    const targetClear = (0, eval)(`(${targetClearSource})`);

    originClear();
    assert.strictEqual(globalThis.header.currency, '');
    assert.strictEqual(globalThis.header.exchange_rate, 1);

    globalThis.header.currency = 'NIO';
    globalThis.header.exchange_rate = 36;
    targetClear();
    assert.strictEqual(globalThis.header.target_currency, '');
    assert.strictEqual(globalThis.header.exchange_rate, 1);
  });

  it('clears both transfer selectors when the company changes', function () {
    const source = readTemplate('transferencia_nueva.html');
    const dom = new JSDOM('<!doctype html><html><body><input id="company" value="OLD"></body></html>');
    const factory = loadSmartSelect(dom);
    const header = {
      bank_account_id: 'ORIGIN-OLD',
      currency: 'NIO',
      target_bank_account_id: 'TARGET-OLD',
      target_currency: 'USD',
      exchange_rate: 36,
    };
    globalThis.header = header;
    // eslint-disable-next-line no-eval
    const originClear = (0, eval)(`(${extractFunction(source, 'on_clear', 'header.currency')})`);
    // eslint-disable-next-line no-eval
    const targetClear = (0, eval)(`(${extractFunction(source, 'on_clear', 'header.target_currency')})`);
    const origin = factory({
      doctype: 'bank_account',
      name: 'bank_account_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      onClear: originClear,
    });
    const target = factory({
      doctype: 'bank_account',
      name: 'target_bank_account_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      onClear: targetClear,
    });
    for (const component of [origin, target]) {
      component.selectedValue = 'SEL-OLD';
      component.selectedLabel = 'Cuenta anterior';
      component.search = 'Cuenta anterior';
      component.options = [{ value: 'SEL-OLD', display_name: 'Cuenta anterior' }];
      component.init();
    }

    dispatchFilterChange(dom, document.getElementById('company'), 'NEW');

    assert.strictEqual(origin.selectedValue, '');
    assert.strictEqual(target.selectedValue, '');
    assert.strictEqual(header.currency, '');
    assert.strictEqual(header.target_currency, '');
    assert.strictEqual(header.exchange_rate, 1);
  });

  it('clears the transfer header when either bank account text is edited', function () {
    const source = readTemplate('transferencia_nueva.html');
    const dom = new JSDOM('<!doctype html><html><body><input id="company" value="OLD"></body></html>');
    const factory = loadSmartSelect(dom);
    const header = { currency: 'NIO', target_currency: 'USD', exchange_rate: 36 };
    globalThis.header = header;
    // eslint-disable-next-line no-eval
    const originClear = (0, eval)(`(${extractFunction(source, 'on_clear', 'header.currency')})`);
    // eslint-disable-next-line no-eval
    const targetClear = (0, eval)(`(${extractFunction(source, 'on_clear', 'header.target_currency')})`);
    const origin = factory({
      doctype: 'bank_account',
      name: 'bank_account_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      onClear: originClear,
    });
    const target = factory({
      doctype: 'bank_account',
      name: 'target_bank_account_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      onClear: targetClear,
    });
    for (const component of [origin, target]) {
      component.selectedValue = 'SEL-OLD';
      component.selectedLabel = 'Cuenta anterior';
      component.search = 'Cuenta anterior';
      component.options = [{ value: 'SEL-OLD', display_name: 'Cuenta anterior' }];
      component.init();
    }

    origin.onInput({ target: { value: 'Otra cuenta' } });
    assert.strictEqual(header.currency, '');
    assert.strictEqual(header.exchange_rate, 1);

    header.currency = 'NIO';
    header.exchange_rate = 36;
    target.onInput({ target: { value: 'Otra cuenta destino' } });
    assert.strictEqual(header.target_currency, '');
    assert.strictEqual(header.exchange_rate, 1);
  });

  it('blocks the transfer submit after clearing either bank account', function () {
    const source = readTemplate('transferencia_nueva.html');
    const dom = new JSDOM('<!doctype html><html><body></body></html>');
    globalThis.document = dom.window.document;
    globalThis.cacaoLocalIsoDate = () => '2026-01-01';
    globalThis.alert = () => {};
    // eslint-disable-next-line no-eval
    (0, eval)(extractScript(source, 'bankTransferForm'));

    const component = globalThis.bankTransferForm({ paymentType: 'internal_transfer' });
    component.header.company = 'COMP';
    component.header.paid_amount = 10;
    component.header.bank_account_id = 'ORIGIN';
    const blocked = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(blocked);
    assert.strictEqual(blocked.prevented, true);

    component.header.target_bank_account_id = 'TARGET';
    component.header.exchange_rate = 2;
    const accepted = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(accepted);
    assert.strictEqual(accepted.prevented, false);
    const payload = JSON.parse(component.payload);
    assert.strictEqual(payload.bank_account_id, 'ORIGIN');
    assert.strictEqual(payload.target_bank_account_id, 'TARGET');
    assert.strictEqual(payload.exchange_rate, 2);

    component.header.bank_account_id = '';
    const cleared = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(cleared);
    assert.strictEqual(cleared.prevented, true);
  });
});
