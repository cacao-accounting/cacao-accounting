// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

function loadListener() {
  const templatePath = path.join(
    __dirname,
    '..',
    '..',
    'bancos',
    'templates',
    'bancos',
    'caja_chica_vale_nuevo.html',
  );
  const source = fs.readFileSync(templatePath, 'utf8');
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes('company-selected'));
  assert.ok(script, 'No se encontró el listener de company-selected');
  return script.replace(/<script>|<\/script>/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
}

describe('caja chica voucher currency', function () {
  afterEach(function () {
    delete globalThis.document;
  });

  it('clears the stale fund currency when the company changes', function () {
    const dom = new JSDOM('<!doctype html><html><body><input id="pc_currency" value="NIO"></body></html>');
    globalThis.document = dom.window.document;
    // eslint-disable-next-line no-eval
    (0, eval)(loadListener());

    document.dispatchEvent(new dom.window.Event('company-selected'));

    assert.strictEqual(document.getElementById('pc_currency').value, '');
  });

  it('is safe when the currency field is absent', function () {
    const dom = new JSDOM('<!doctype html><html><body></body></html>');
    globalThis.document = dom.window.document;
    // eslint-disable-next-line no-eval
    (0, eval)(loadListener());

    document.dispatchEvent(new dom.window.Event('company-selected'));

    assert.strictEqual(document.getElementById('pc_currency'), null);
  });
});
