// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

const assert = require('assert');

function loadSmartSelect(overrides = {}) {
  const listeners = {};
  const elements = overrides.elements || {};
  const fetchImpl = overrides.fetch || (() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
  let smartSelectFactory = null;

  global.document = {
    addEventListener: (event, callback) => {
      listeners[event] = callback;
    },
    querySelector: (selector) => elements[selector] || null,
  };

  global.Alpine = {
    data: (name, factory) => {
      if (name === 'smartSelect') smartSelectFactory = factory;
    },
  };

  global.fetch = fetchImpl;

  const modulePath = require.resolve('../js/smart-select.js');
  delete require.cache[modulePath];
  require(modulePath);
  listeners['alpine:init']();

  return function create(config) {
    return smartSelectFactory(config);
  };
}

async function flushPromises() {
  await new Promise((resolve) => setImmediate(resolve));
}

describe('smart-select', function () {
  afterEach(function () {
    delete global.document;
    delete global.Alpine;
    delete global.fetch;
  });

  it('does not preload on focus when preloadOnFocus is disabled', async function () {
    let fetchCalls = 0;
    const create = loadSmartSelect({
      fetch: () => {
        fetchCalls += 1;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'naming_series',
      name: 'naming_series_id',
      preload: true,
      preloadOnFocus: false,
      initialValue: 'SER-001',
      minChars: 1,
    });

    component.init();
    component.onFocus();
    await flushPromises();

    assert.strictEqual(fetchCalls, 0);
    assert.strictEqual(component.open, false);
  });

  it('allows preload on focus when explicitly enabled', async function () {
    let fetchCalls = 0;
    const create = loadSmartSelect({
      fetch: () => {
        fetchCalls += 1;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [{ value: 'cafe' }] }) });
      },
    });
    const component = create({
      doctype: 'company',
      name: 'company',
      preload: true,
      preloadOnFocus: true,
      minChars: 1,
    });

    component.onFocus();
    await flushPromises();

    assert.strictEqual(fetchCalls, 1);
    assert.strictEqual(component.open, true);
    assert.strictEqual(component.options.length, 1);
  });

  it('opens menu on first focus while preload is still loading', async function () {
    let resolveRequest;
    const create = loadSmartSelect({
      fetch: () => new Promise((resolve) => { resolveRequest = resolve; }),
    });

    const component = create({
      doctype: 'company',
      name: 'company',
      preload: true,
      preloadOnFocus: true,
      minChars: 1,
    });

    component.init();
    assert.strictEqual(component.loading, true);
    assert.strictEqual(component.open, false);

    component.onFocus();
    assert.strictEqual(component.open, true);

    resolveRequest({ ok: true, json: () => Promise.resolve({ results: [{ value: 'cafe' }] }) });
    await flushPromises();
    assert.strictEqual(component.loading, false);
    assert.strictEqual(component.options.length, 1);
  });

  it('clears dependent state on filter change without fetching when preload is disabled', async function () {
    let fetchCalls = 0;
    const companyElement = {
      value: 'cafe',
      listeners: {},
      addEventListener: function (eventName, callback) {
        this.listeners[eventName] = callback;
      },
    };
    const create = loadSmartSelect({
      elements: { '#company': companyElement },
      fetch: () => {
        fetchCalls += 1;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'naming_series',
      name: 'naming_series_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      preload: false,
      minChars: 1,
    });

    component.init();
    component.selectedValue = 'SER-001';
    component.selectedLabel = 'Serie 001';
    component.search = 'Serie 001';
    component.options = [{ value: 'SER-001' }];
    companyElement.value = 'choco';

    component.handleFilterChange();
    await flushPromises();

    assert.strictEqual(component.selectedValue, '');
    assert.strictEqual(component.selectedLabel, '');
    assert.strictEqual(component.search, '');
    assert.deepStrictEqual(component.options, []);
    assert.strictEqual(fetchCalls, 0);
  });

  it('auto-selects default naming series when company changes and filter is present', async function () {
    let fetchCalls = 0;
    const companyElement = {
      value: 'cafe',
      listeners: {},
      addEventListener: function (eventName, callback) {
        this.listeners[eventName] = callback;
      },
    };
    const create = loadSmartSelect({
      elements: { '#company': companyElement },
      fetch: () => {
        fetchCalls += 1;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [{ value: 'SER-001', display_name: 'Serie 001', is_default: true }] }) });
      },
    });
    const component = create({
      doctype: 'naming_series',
      name: 'naming_series_id',
      filters: { company: { selector: '#company' } },
      filterSources: ['#company'],
      preload: false,
      loadOnFilterChange: true,
      requiredFilters: ['company'],
      autoSelectDefault: true,
      minChars: 1,
    });

    component.init();
    companyElement.value = 'choco';

    component.handleFilterChange();
    await flushPromises();

    assert.strictEqual(fetchCalls, 1);
    assert.strictEqual(component.selectedValue, 'SER-001');
    assert.strictEqual(component.selectedLabel, 'Serie 001');
    assert.strictEqual(component.options.length, 1);
  });

  it('selectOption updates hidden input and dispatches input/change events', function () {
    const create = loadSmartSelect();
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
    });

    const events = [];
    const hiddenInput = {
      value: '',
      dispatchEvent: function (event) {
        events.push(event.type);
      },
    };

    component.$root = {
      querySelector: function (selector) {
        if (selector === 'input[type="hidden"][name="company"]') return hiddenInput;
        return null;
      },
    };

    component.selectOption({ value: 'cacao', display_name: 'Cacao SA' });

    assert.strictEqual(hiddenInput.value, 'cacao');
    assert.ok(events.includes('input'));
    assert.ok(events.includes('change'));
  });

  it('selectOptionValue keeps scalar value and visible label', function () {
    const create = loadSmartSelect();
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
    });

    const hiddenInput = {
      value: '',
      dispatchEvent: function () {},
    };

    component.$root = {
      querySelector: function (selector) {
        if (selector === 'input[type="hidden"][name="company"]') return hiddenInput;
        return null;
      },
    };

    component.selectOptionValue('cacao', 'cacao - Choco Sonrisas Sociedad Anonima');

    assert.strictEqual(component.selectedValue, 'cacao');
    assert.strictEqual(component.selectedLabel, 'cacao - Choco Sonrisas Sociedad Anonima');
    assert.strictEqual(component.search, 'cacao - Choco Sonrisas Sociedad Anonima');
    assert.strictEqual(hiddenInput.value, 'cacao');
  });

  it('selectOptionFromValues keeps scalar value and passes option payload to callback', function () {
    const create = loadSmartSelect();
    let selectedOption = null;
    const component = create({
      doctype: 'item',
      name: 'item_code_0',
      minChars: 1,
      onSelect: function (option) {
        selectedOption = option;
      },
    });

    const hiddenInput = {
      value: '',
      dispatchEvent: function () {},
    };

    component.$root = {
      querySelector: function (selector) {
        if (selector === 'input[type="hidden"][name="item_code_0"]') return hiddenInput;
        return null;
      },
    };

    component.selectOptionFromValues('ART-001', 'ART-001 - Chocolate 100g', {
      value: 'ART-001',
      display_name: 'ART-001 - Chocolate 100g',
      name: 'Chocolate 100g',
    });

    assert.strictEqual(component.selectedValue, 'ART-001');
    assert.strictEqual(hiddenInput.value, 'ART-001');
    assert.strictEqual(selectedOption.name, 'Chocolate 100g');
  });

  it('uses the input event value when fetching options', async function () {
    let requestUrl = '';
    const create = loadSmartSelect({
      fetch: (url) => {
        requestUrl = url;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
    });

    component.onInput({ target: { value: 'cacao' } });
    await flushPromises();

    assert.strictEqual(component.search, 'cacao');
    assert.ok(decodeURIComponent(requestUrl).includes('q=cacao'));
  });

  it('company selection stores scalar value in hidden input when option value is object', function () {
    const create = loadSmartSelect();
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
    });

    const events = [];
    const hiddenInput = {
      value: '',
      dispatchEvent: function (event) {
        events.push(event.type);
      },
    };

    component.$root = {
      querySelector: function (selector) {
        if (selector === 'input[type="hidden"][name="company"]') return hiddenInput;
        return null;
      },
    };

    component.selectOption({ value: { id: 'cacao' }, display_name: 'Cacao SA' });

    assert.strictEqual(component.selectedValue, 'cacao');
    assert.strictEqual(hiddenInput.value, 'cacao');
    assert.ok(events.includes('input'));
    assert.ok(events.includes('change'));
  });

  it('normalizes object option values on selection', function () {
    const create = loadSmartSelect();
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
    });

    component.selectOption({ value: { id: 'cacao' }, display_name: 'Cacao SA' });

    assert.strictEqual(component.selectedValue, 'cacao');
  });

  it('normalizes object initialValue to scalar', function () {
    const create = loadSmartSelect();
    const component = create({
      doctype: 'company',
      name: 'company',
      minChars: 1,
      initialValue: { value: 'cacao' },
      initialLabel: 'Cacao SA',
    });

    component.init();

    assert.strictEqual(component.selectedValue, 'cacao');
  });

  it('normalizes object filters to scalar values for backend queries', async function () {
    let requestUrl = '';
    const create = loadSmartSelect({
      fetch: (url) => {
        requestUrl = url;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'naming_series',
      name: 'naming_series_id',
      minChars: 1,
      filters: {
        company: () => ({ value: 'cafe' }),
        entity_type: { id: 'journal_entry' },
        ignored_filter: { unexpected_key: 'x' },
      },
    });

    component.search = 'caf';
    component.fetchOptions();
    await flushPromises();

    const queryString = decodeURIComponent(requestUrl.split('?')[1] || '');
    assert.ok(queryString.includes('company=cafe'));
    assert.ok(queryString.includes('entity_type=journal_entry'));
    assert.strictEqual(queryString.includes('ignored_filter='), false);
    assert.strictEqual(queryString.includes('[object Object]'), false);
  });

  it('normalizes selector filter when DOM value is an object', async function () {
    let requestUrl = '';
    const create = loadSmartSelect({
      elements: {
        '#company': { value: { value: 'cafe' } },
      },
      fetch: (url) => {
        requestUrl = url;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'account',
      name: 'account',
      minChars: 1,
      filters: {
        company: { selector: '#company' },
      },
    });

    component.search = '11';
    component.fetchOptions();
    await flushPromises();

    const queryString = decodeURIComponent(requestUrl.split('?')[1] || '');
    assert.ok(queryString.includes('company=cafe'));
    assert.strictEqual(queryString.includes('[object Object]'), false);
  });

  it('skips object filters without supported scalar keys', async function () {
    let requestUrl = '';
    const create = loadSmartSelect({
      fetch: (url) => {
        requestUrl = url;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'naming_series',
      name: 'naming_series_id',
      minChars: 1,
      filters: {
        company: { code: 'cafe' },
        unsupported: { label: 'Not allowed as scalar' },
      },
    });

    component.search = 'caf';
    component.fetchOptions();
    await flushPromises();

    const queryString = decodeURIComponent(requestUrl.split('?')[1] || '');
    assert.ok(queryString.includes('company=cafe'));
    assert.strictEqual(queryString.includes('unsupported='), false);
  });

  it('preserves array filters and appends each value', async function () {
    let requestUrl = '';
    const create = loadSmartSelect({
      fetch: (url) => {
        requestUrl = url;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
      },
    });
    const component = create({
      doctype: 'account',
      name: 'account',
      minChars: 1,
      filters: {
        company: 'cafe',
        account_type: ['asset', 'expense'],
      },
    });

    component.search = 'ca';
    component.fetchOptions();
    await flushPromises();

    const queryString = decodeURIComponent(requestUrl.split('?')[1] || '');
    assert.ok(queryString.includes('account_type=asset'));
    assert.ok(queryString.includes('account_type=expense'));
  });
});
