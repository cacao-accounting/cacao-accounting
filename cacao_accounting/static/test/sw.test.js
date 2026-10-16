// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadServiceWorker(options) {
  const overrides = options || {};
  const listeners = {};
  const calls = {
    open: [],
    put: [],
    match: [],
    delete: [],
    skipWaiting: 0,
    claim: 0,
    fetch: [],
  };

  const cache = {
    addAll: overrides.addAll || (() => Promise.resolve()),
    put: (request, response) => {
      calls.put.push([request, response]);
      return Promise.resolve();
    },
  };

  const caches = {
    open: (name) => {
      calls.open.push(name);
      return Promise.resolve(cache);
    },
    keys: () => Promise.resolve(overrides.keys || ['cacao-accounting-v5', 'old-cache']),
    match: (request) => {
      calls.match.push(request);
      return Promise.resolve(overrides.matchedResponse ? overrides.matchedResponse(request) : undefined);
    },
    delete: (name) => {
      calls.delete.push(name);
      return Promise.resolve(true);
    },
  };

  const self = {
    location: { origin: 'http://localhost' },
    addEventListener: (type, handler) => {
      listeners[type] = handler;
    },
    skipWaiting: () => {
      calls.skipWaiting += 1;
    },
    clients: {
      claim: () => {
        calls.claim += 1;
      },
    },
  };

  const fetchImpl =
    overrides.fetch ||
    ((request) => {
      calls.fetch.push(request);
      return Promise.resolve({ ok: true, status: 200 });
    });

  const sandbox = { self, caches, fetch: fetchImpl, URL, Promise, console };
  vm.createContext(sandbox);

  const source = fs.readFileSync(path.join(__dirname, '..', 'js', 'sw.js'), 'utf8');
  vm.runInContext(source, sandbox);

  function trigger(type, event) {
    listeners[type](event);
  }

  return { listeners, calls, trigger };
}

describe('service worker', function () {
  it('precaches static assets on install and activates immediately', async function () {
    const sw = loadServiceWorker();
    let waited = null;
    sw.trigger('install', { waitUntil: (promise) => { waited = promise; } });

    assert.ok(waited && typeof waited.then === 'function');
    await waited;
    assert.deepStrictEqual(sw.calls.open, ['cacao-accounting-v5']);
    assert.strictEqual(sw.calls.skipWaiting, 1);
  });

  it('swallows precache failures during install', async function () {
    const sw = loadServiceWorker({ addAll: () => Promise.reject(new Error('boom')) });
    let waited = null;
    sw.trigger('install', { waitUntil: (promise) => { waited = promise; } });

    await waited;
  });

  it('removes outdated caches on activate', async function () {
    const sw = loadServiceWorker();
    let waited = null;
    sw.trigger('activate', { waitUntil: (promise) => { waited = promise; } });

    await waited;
    assert.deepStrictEqual(sw.calls.delete, ['old-cache']);
    assert.strictEqual(sw.calls.claim, 1);
  });

  it('serves cached static assets and refreshes them in the background', async function () {
    const cached = { body: 'cached' };
    const networkChecks = [];
    const sw = loadServiceWorker({
      matchedResponse: () => cached,
      fetch: (request) => {
        networkChecks.push(request);
        return Promise.resolve({ ok: true, status: 200 });
      },
    });

    let responded = null;
    const request = { method: 'GET', url: 'http://localhost/static/app.js' };
    sw.trigger('fetch', { request, respondWith: (promise) => { responded = promise; } });

    assert.strictEqual(await responded, cached);
    await new Promise((resolve) => setImmediate(resolve));
    assert.strictEqual(networkChecks.length, 1);
    assert.strictEqual(sw.calls.put.length, 1);
  });

  it('does not cache background refresh responses that are not OK', async function () {
    const cached = { body: 'cached' };
    const sw = loadServiceWorker({
      matchedResponse: () => cached,
      fetch: () => Promise.resolve({ ok: false, status: 404 }),
    });

    let responded = null;
    sw.trigger('fetch', {
      request: { method: 'GET', url: 'http://localhost/static/app.js' },
      respondWith: (promise) => { responded = promise; },
    });

    await responded;
    await new Promise((resolve) => setImmediate(resolve));
    assert.strictEqual(sw.calls.put.length, 0);
  });

  it('falls back to the network when a static asset is not cached', async function () {
    const network = { body: 'network' };
    const sw = loadServiceWorker({
      matchedResponse: () => undefined,
      fetch: () => Promise.resolve(network),
    });

    let responded = null;
    sw.trigger('fetch', {
      request: { method: 'GET', url: 'http://localhost/static/missing.js' },
      respondWith: (promise) => { responded = promise; },
    });

    assert.strictEqual(await responded, network);
  });

  it('uses network-first with cache fallback for dynamic requests', async function () {
    const cached = { body: 'cached-html' };
    const sw = loadServiceWorker({
      matchedResponse: () => cached,
      fetch: () => Promise.reject(new Error('offline')),
    });

    let responded = null;
    sw.trigger('fetch', {
      request: { method: 'GET', url: 'http://localhost/dashboard' },
      respondWith: (promise) => { responded = promise; },
    });

    assert.strictEqual(await responded, cached);
  });

  it('ignores non-GET requests', function () {
    const sw = loadServiceWorker();
    let respondCalled = false;
    sw.trigger('fetch', {
      request: { method: 'POST', url: 'http://localhost/static/app.js' },
      respondWith: () => { respondCalled = true; },
    });

    assert.strictEqual(respondCalled, false);
  });
});
