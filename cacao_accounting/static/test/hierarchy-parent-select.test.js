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
    errorMessage: 'No se pudieron cargar las opciones jerárquicas. Intente de nuevo.',
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

  it('clears parent options and reports an HTTP failure', async function () {
    const { component, select } = createComponent(async () => ({ ok: false }));

    await component.refresh('secret');

    expect([...select.options].map((option) => option.value)).to.deep.equal(['']);
    expect(select.value).to.equal('');
    expect(component.error).to.equal('No se pudieron cargar las opciones jerárquicas. Intente de nuevo.');
  });

  it('reports network failures and clears the message after a later successful load', async function () {
    let fail = true;
    const { component } = createComponent(async () => {
      if (fail) throw new TypeError('network unavailable');
      return { ok: true, json: async () => [{ value: 'parent', label: 'Parent' }] };
    });

    await component.refresh('cacao');
    expect(component.error).to.equal('No se pudieron cargar las opciones jerárquicas. Intente de nuevo.');

    fail = false;
    await component.refresh('cacao');
    expect(component.error).to.equal('');
  });

  it('ignores a stale failed request after a newer company load succeeds', async function () {
    let rejectFirst;
    let calls = 0;
    const { component, select } = createComponent(() => {
      calls += 1;
      if (calls === 1) return new Promise((_, reject) => { rejectFirst = reject; });
      return Promise.resolve({
        ok: true,
        json: async () => [{ value: 'current-parent', label: 'Current parent' }],
      });
    });

    const stale = component.refresh('old-company');
    await component.refresh('current-company');
    rejectFirst(new TypeError('stale network failure'));
    await stale;

    expect(component.error).to.equal('');
    expect([...select.options].map((option) => option.value)).to.deep.equal(['', 'current-parent']);
  });
});
