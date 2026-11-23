// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');

function loadFactory() {
  const templatePath = path.join(__dirname, '..', '..', 'bancos', 'templates', 'bancos', 'nota_nueva.html');
  const source = fs.readFileSync(templatePath, 'utf8');
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes('bankNoteForm'));
  assert.ok(script, 'No se encontró el script de bankNoteForm');
  const executable = script.replace(/<script>|<\/script>/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
  globalThis.cacaoLocalIsoDate = () => '2026-05-15';
  // eslint-disable-next-line no-eval
  (0, eval)(executable);
  return globalThis.bankNoteForm;
}

function createForm(paymentType) {
  const target = new EventTarget();
  globalThis.document = target;
  const factory = loadFactory();
  const form = factory({ paymentType: paymentType });
  const watchers = {};
  form.$watch = (field, callback) => {
    watchers[field] = callback;
  };
  form.init();
  return { form: form, target: target, watchers: watchers };
}

describe('bank note currency', function () {
  afterEach(function () {
    delete globalThis.bankNoteForm;
    delete globalThis.cacaoLocalIsoDate;
    delete globalThis.document;
  });

  it('adopts the currency exposed by the bank account option', function () {
    const { form, target } = createForm('debit_note');

    target.dispatchEvent(new CustomEvent('bank-account-selected', { detail: { value: 'bank-1', currency: 'USD' } }));

    assert.strictEqual(form.header.bank_account_id, 'bank-1');
    assert.strictEqual(form.header.currency, 'USD');
  });

  it('clears the account and currency when the company changes', function () {
    const { form, target, watchers } = createForm('credit_note');
    target.dispatchEvent(new CustomEvent('bank-account-selected', { detail: { value: 'bank-1', currency: 'USD' } }));

    watchers['header.company']();

    assert.strictEqual(form.header.bank_account_id, '');
    assert.strictEqual(form.header.currency, '');
  });
});
