// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');

function loadFactory() {
  const templatePath = path.join(
    __dirname,
    '..',
    '..',
    'inventario',
    'templates',
    'inventario',
    'stock_reconciliation_nuevo.html',
  );
  const source = fs.readFileSync(templatePath, 'utf8');
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes('stockReconciliationForm'));
  assert.ok(script, 'No se encontró el script de stockReconciliationForm');
  const executable = script.replace(/<script>|<\/script>/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
  globalThis.cacaoLocalIsoDate = () => '2026-05-15';
  // eslint-disable-next-line no-eval
  (0, eval)(executable);
  return globalThis.stockReconciliationForm;
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function snapshot(actualQty, valuationRate, stockValue) {
  return {
    ok: true,
    json: async () => ({
      actual_qty: actualQty,
      valuation_rate: valuationRate,
      stock_value: stockValue,
    }),
  };
}

function createForm() {
  const factory = loadFactory();
  const form = factory({ header: { company: 'cacao' } });
  form.init();
  return form;
}

describe('stock reconciliation snapshot ordering', function () {
  afterEach(function () {
    delete globalThis.stockReconciliationForm;
    delete globalThis.cacaoLocalIsoDate;
    delete globalThis.fetch;
  });

  it('ignores a late snapshot from the previous item', async function () {
    const first = deferred();
    const second = deferred();
    globalThis.fetch = (url) => {
      const item = new URL(url, 'http://localhost').searchParams.get('item_code');
      return item === 'ITEM-A' ? first.promise : second.promise;
    };
    const form = createForm();
    const line = form.lines[0];

    line.item_code = 'ITEM-A';
    line.warehouse = 'BODEGA-1';
    const staleRequest = form.loadSnapshot(line);

    line.item_code = 'ITEM-B';
    const currentRequest = form.loadSnapshot(line);

    second.resolve(snapshot(50, 5, 250));
    await currentRequest;
    first.resolve(snapshot(100, 10, 1000));
    await staleRequest;

    assert.strictEqual(line.item_code, 'ITEM-B');
    assert.strictEqual(line.current_qty, 50);
    assert.strictEqual(line.counted_qty, 50);
    assert.strictEqual(line.current_stock_value, 250);
  });

  it('keeps the newest snapshot when the same line is requested twice', async function () {
    const first = deferred();
    const second = deferred();
    const responses = [first, second];
    globalThis.fetch = () => responses.shift().promise;
    const form = createForm();
    const line = form.lines[0];

    line.item_code = 'ITEM-A';
    line.warehouse = 'BODEGA-1';
    const olderRequest = form.loadSnapshot(line);
    const newerRequest = form.loadSnapshot(line);

    second.resolve(snapshot(60, 6, 360));
    await newerRequest;
    first.resolve(snapshot(100, 10, 1000));
    await olderRequest;

    assert.strictEqual(line.current_qty, 60);
    assert.strictEqual(line.counted_qty, 60);
  });
});
