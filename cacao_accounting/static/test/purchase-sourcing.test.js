// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

'use strict';

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { JSDOM } = require('jsdom');

const SCRIPT = fs.readFileSync(path.join(__dirname, '..', 'js', 'purchase-sourcing.js'), 'utf8');

function loadForm({ offersInsufficient = 'false', radios = [], selected = null } = {}) {
  const radiosHtml = radios
    .map(
      (radio, index) =>
        `<input type="radio" name="${radio.name}" value="${radio.value}" ` +
        `data-rate="${radio.rate}"` +
        (radio.baseRate === undefined ? '' : ` data-base-rate="${radio.baseRate}"`) +
        `${radio.value === selected ? ' checked' : ''}>`,
    )
    .join('');
  const dom = new JSDOM(
    `<!DOCTYPE html><html><body>
      <form action="/buying/request-for-quotation/RFQ-1/award" data-offers-insufficient="${offersInsufficient}">
        ${radiosHtml}
        <textarea id="authorization_reason"></textarea>
      </form>
    </body></html>`,
    { url: 'http://localhost/', runScripts: 'outside-only' },
  );
  vm.runInContext(SCRIPT, dom.getInternalVMContext());
  return dom.window.document;
}

function select(document, name, value) {
  const input = document.querySelector(`input[name="${name}"][value="${value}"]`);
  input.checked = true;
  document.querySelector('form').dispatchEvent(new document.defaultView.Event('change'));
  return document.getElementById('authorization_reason').required;
}

describe('purchase sourcing authorization reason', function () {
  it('requires a reason when the selected offer is costlier in base currency', function () {
    const document = loadForm({
      radios: [
        { name: 'award_item_ITEM1', value: 'USD-OFFER', rate: '10', baseRate: '365' },
        { name: 'award_item_ITEM1', value: 'NIO-OFFER', rate: '300', baseRate: '300' },
      ],
    });

    assert.strictEqual(select(document, 'award_item_ITEM1', 'USD-OFFER'), true);
    assert.strictEqual(select(document, 'award_item_ITEM1', 'NIO-OFFER'), false);
  });

  it('keeps the reason optional when the recommended offer is selected', function () {
    const document = loadForm({
      radios: [
        { name: 'award_item_ITEM1', value: 'CHEAP', rate: '10', baseRate: '10' },
        { name: 'award_item_ITEM1', value: 'COSTLY', rate: '15', baseRate: '15' },
      ],
      selected: 'CHEAP',
    });

    assert.strictEqual(document.getElementById('authorization_reason').required, false);
  });

  it('falls back to the nominal rate when the server omits the base rate', function () {
    const document = loadForm({
      radios: [
        { name: 'award_item_ITEM1', value: 'CHEAP', rate: '10' },
        { name: 'award_item_ITEM1', value: 'COSTLY', rate: '15' },
      ],
      selected: 'CHEAP',
    });

    assert.strictEqual(document.getElementById('authorization_reason').required, false);
  });

  it('requires a reason for insufficient offers even with the recommended selection', function () {
    const document = loadForm({
      offersInsufficient: 'true',
      radios: [{ name: 'award_item_ITEM1', value: 'ONLY', rate: '10', baseRate: '10' }],
      selected: 'ONLY',
    });

    assert.strictEqual(document.getElementById('authorization_reason').required, true);
  });
});
