// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

'use strict';

const { expect } = require('chai');
const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function createComponent(fetchOptions) {
  const dom = new JSDOM('<!doctype html><select></select>', { url: 'http://localhost/' });
  const { window } = dom;
  let factory;
  window.fetch = fetchOptions;
  window.Alpine = {
    data(name, callback) {
      if (name === 'hierarchyParentSelect') factory = callback;
    },
  };

  const source = fs.readFileSync(path.join(__dirname, '..', 'js', 'hierarchy-parent-select.js'), 'utf8');
  vm.runInContext(source, vm.createContext(window));
  window.document.dispatchEvent(new window.Event('alpine:init'));

  const select = window.document.querySelector('select');
  select.add(new window.Option('Old parent', 'old-parent'));
  select.value = 'old-parent';
  const component = factory({
    endpoint: '/accounting/hierarchy/unit/parents',
    action: 'crear',
    excludeId: '',
    placeholder: '— Ninguna —',
  });
  component.$refs = { parent: select };
  return { component, select, window };
}

describe('hierarchyParentSelect', function () {
  it('loads only server supplied parents for the selected company', async function () {
    let requestedUrl;
    const { component, select } = createComponent(async (url) => {
      requestedUrl = new URL(url, 'http://localhost');
      return {
        ok: true,
        json: async () => [{ value: 'cacao-parent', label: 'CACAO - Parent' }],
      };
    });

    await component.refresh('cacao');

    expect(requestedUrl.searchParams.get('entity')).to.equal('cacao');
    expect(requestedUrl.searchParams.get('action')).to.equal('crear');
    expect([...select.options].map((option) => option.value)).to.deep.equal(['', 'cacao-parent']);
    expect(select.value).to.equal('');
  });

  it('clears parent options when the company changes and the request fails', async function () {
    const { component, select } = createComponent(async () => ({ ok: false }));

    await component.refresh('secret');

    expect([...select.options].map((option) => option.value)).to.deep.equal(['']);
    expect(select.value).to.equal('');
  });
});
