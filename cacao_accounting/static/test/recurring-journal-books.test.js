// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');

function loadFactory() {
  const templatePath = path.join(
    __dirname,
    '..',
    '..',
    'contabilidad',
    'templates',
    'contabilidad',
    'recurring_journal_nuevo.html'
  );
  const source = fs.readFileSync(templatePath, 'utf8');
  const scripts = source.match(/<script>([\s\S]*?)<\/script>/g) || [];
  const script = scripts.find((block) => block.includes('recurringJournalForm'));
  assert.ok(script, 'No se encontró el script de recurringJournalForm');
  const executable = script.replace(/<script>|<\/script>/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
  // eslint-disable-next-line no-eval
  (0, eval)(executable);
  return globalThis.recurringJournalForm;
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe('recurring journal books', function () {
  afterEach(function () {
    delete globalThis.recurringJournalForm;
    delete globalThis.fetch;
  });

  it('ignores books from a previous company response', async function () {
    const factory = loadFactory();
    const first = deferred();
    const second = deferred();
    const requests = [first, second];
    globalThis.fetch = () => requests.shift().promise;
    const form = factory({ initialJournal: {} });
    form.header.company = 'A';

    const firstLoad = form.loadBooks('A');
    form.header.company = 'B';
    const secondLoad = form.loadBooks('B');
    second.resolve({ json: () => Promise.resolve({ results: [{ value: 'BOOK-B' }] }) });
    await secondLoad;
    first.resolve({ json: () => Promise.resolve({ results: [{ value: 'BOOK-A' }] }) });
    await firstLoad;

    assert.deepStrictEqual(form.books, [{ value: 'BOOK-B' }]);
    assert.deepStrictEqual(form.selectedBooks, ['BOOK-B']);
  });
});
