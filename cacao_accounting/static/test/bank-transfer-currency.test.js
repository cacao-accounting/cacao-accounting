// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');

function loadFactory() {
  const templatePath = path.join(__dirname, '..', '..', 'bancos', 'templates', 'bancos', 'transferencia_nueva.html');
  const source = fs.readFileSync(templatePath, 'utf8');
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes('bankTransferForm'));
  assert.ok(script, 'No se encontró el script de bankTransferForm');
  const executable = script.replace(/<script>|<\/script>/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
  // eslint-disable-next-line no-eval
  (0, eval)(executable);
  return globalThis.bankTransferForm;
}

function createForm() {
  const target = new EventTarget();
  globalThis.document = target;
  globalThis.cacaoLocalIsoDate = () => '2026-05-15';
  const factory = loadFactory();
  const form = factory({ paymentType: 'internal_transfer' });
  const watchers = {};
  form.$watch = (field, callback) => {
    watchers[field] = callback;
  };
  form.init();
  return { form: form, target: target, watchers: watchers };
}

describe('bank transfer currency', function () {
  afterEach(function () {
    delete globalThis.bankTransferForm;
    delete globalThis.cacaoLocalIsoDate;
    delete globalThis.document;
  });

  it('adopts source and target currencies from the selected accounts', function () {
    const { form, target } = createForm();

    target.dispatchEvent(new CustomEvent('bank-account-selected', { detail: { value: 'bank-1', currency: 'USD' } }));
    target.dispatchEvent(
      new CustomEvent('target-bank-account-selected', { detail: { value: 'bank-2', currency: 'NIO' } }),
    );

    assert.strictEqual(form.header.bank_account_id, 'bank-1');
    assert.strictEqual(form.header.currency, 'USD');
    assert.strictEqual(form.header.target_bank_account_id, 'bank-2');
    assert.strictEqual(form.header.target_currency, 'NIO');
  });

  it('clears accounts and both currencies when the company changes', function () {
    const { form, target, watchers } = createForm();
    target.dispatchEvent(new CustomEvent('bank-account-selected', { detail: { value: 'bank-1', currency: 'USD' } }));
    target.dispatchEvent(
      new CustomEvent('target-bank-account-selected', { detail: { value: 'bank-2', currency: 'NIO' } }),
    );

    watchers['header.company']();

    assert.strictEqual(form.header.bank_account_id, '');
    assert.strictEqual(form.header.currency, '');
    assert.strictEqual(form.header.target_bank_account_id, '');
    assert.strictEqual(form.header.target_currency, '');
  });
});
