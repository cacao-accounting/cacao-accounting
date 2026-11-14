// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

'use strict';

const assert = require('assert');
const { JSDOM } = require('jsdom');
const initializeFinancialReportTree = require('../js/financial-report-tree.js');

function createReportTree(sections = ['balance'], duplicateParentRows = false) {
  const rows = sections
    .map(
      (section) => `
        <tr data-tree-section="${section}">
          <td data-code="1" data-parent=""><span class="ca-tree-label"><a href="/account/1">1</a></span></td>
        </tr>
        ${
          duplicateParentRows
            ? `<tr data-tree-section="${section}"><td data-code="1" data-parent=""><span class="ca-tree-label"><a href="/account/1">1</a></span></td></tr>`
            : ''
        }
        <tr data-tree-section="${section}">
          <td data-code="1.1" data-parent="1"><span class="ca-tree-label"><a href="/account/1.1">1.1</a></span></td>
        </tr>
        <tr data-tree-section="${section}">
          <td data-code="1.1.1" data-parent="1.1"><span class="ca-tree-label">1.1.1</span></td>
        </tr>
      `
    )
    .join('');
  const dom = new JSDOM(`
    <table class="ca-report-table" data-expand-label="Expandir" data-collapse-label="Colapsar">
      <tbody>${rows}</tbody>
    </table>
  `);
  initializeFinancialReportTree(dom.window.document);
  return dom.window.document;
}

function toggleFor(document, section, code) {
  return document.querySelector(
    `tr[data-tree-section="${section}"] td[data-code="${code}"] .ca-tree-toggle`
  );
}

function rowFor(document, section, code) {
  return document.querySelector(`tr[data-tree-section="${section}"] td[data-code="${code}"]`).parentElement;
}

describe('financial report tree', function () {
  it('preserves account drilldown links when adding and using the collapse control', function () {
    const document = createReportTree();
    const parent = rowFor(document, 'balance', '1');
    const link = parent.querySelector('a[href="/account/1"]');
    const toggle = toggleFor(document, 'balance', '1');

    assert.ok(link);
    assert.strictEqual(link.textContent, '1');
    assert.ok(toggle);
    assert.strictEqual(toggle.getAttribute('aria-expanded'), 'true');

    toggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1').hidden, true);
    assert.strictEqual(rowFor(document, 'balance', '1.1.1').hidden, true);
    assert.strictEqual(parent.querySelector('a[href="/account/1"]'), link);

    toggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1').hidden, false);
    assert.strictEqual(link.getAttribute('href'), '/account/1');
  });

  it('restores expanded descendants and retains a collapsed child state', function () {
    const document = createReportTree();
    const parentToggle = toggleFor(document, 'balance', '1');
    const childToggle = toggleFor(document, 'balance', '1.1');

    childToggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1.1').hidden, true);

    parentToggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1').hidden, true);
    assert.strictEqual(rowFor(document, 'balance', '1.1.1').hidden, true);

    parentToggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1').hidden, false);
    assert.strictEqual(rowFor(document, 'balance', '1.1.1').hidden, true);
    assert.strictEqual(childToggle.getAttribute('aria-expanded'), 'false');

    childToggle.click();
    assert.strictEqual(rowFor(document, 'balance', '1.1.1').hidden, false);
    assert.strictEqual(childToggle.getAttribute('aria-expanded'), 'true');
  });

  it('keeps equal account codes in different grouped report sections independent', function () {
    const document = createReportTree(['group-0', 'group-1'], true);

    toggleFor(document, 'group-0', '1').click();

    assert.strictEqual(rowFor(document, 'group-0', '1.1').hidden, true);
    assert.strictEqual(toggleFor(document, 'group-0', '1').getAttribute('aria-expanded'), 'false');
    assert.strictEqual(rowFor(document, 'group-1', '1.1').hidden, false);
    assert.strictEqual(rowFor(document, 'group-1', '1.1.1').hidden, false);
    assert.strictEqual(toggleFor(document, 'group-1', '1').getAttribute('aria-expanded'), 'true');
  });

  it('synchronizes controls for duplicate accounts inside the same report section', function () {
    const document = createReportTree(['group-0'], true);
    const toggles = document.querySelectorAll('tr[data-tree-section="group-0"] td[data-code="1"] button');

    assert.strictEqual(toggles.length, 2);
    toggles[0].click();
    assert.strictEqual(toggles[0].getAttribute('aria-expanded'), 'false');
    assert.strictEqual(toggles[1].getAttribute('aria-expanded'), 'false');
    assert.strictEqual(rowFor(document, 'group-0', '1.1').hidden, true);

    toggles[1].click();
    assert.strictEqual(toggles[0].getAttribute('aria-expanded'), 'true');
    assert.strictEqual(toggles[1].getAttribute('aria-expanded'), 'true');
    assert.strictEqual(rowFor(document, 'group-0', '1.1').hidden, false);
  });
});
