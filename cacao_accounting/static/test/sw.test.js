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
    keys: 0,
    match: [],
    delete: [],
    skipWaiting: 0,
    claim: 0,
    fetch: [],
  };

  const caches = {
    keys: () => {
      calls.keys += 1;
      return Promise.resolve(overrides.keys || ['cacao-accounting-v5', 'old-cache']);
    },
    match: (request) => {
      calls.match.push(request);
      return Promise.resolve(undefined);
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
      return Promise.resolve();
    },
    clients: {
      claim: () => {
        calls.claim += 1;
        return Promise.resolve();
      },
    },
  };

  const fetchImpl = (request) => {
    calls.fetch.push(request);
    return overrides.fetch ? overrides.fetch(request) : Promise.resolve({ ok: true, status: 200 });
  };

  const sandbox = { self, caches, fetch: fetchImpl, URL, Promise, console };
  vm.createContext(sandbox);

  const source = fs.readFileSync(path.join(__dirname, '..', 'js', 'sw.js'), 'utf8');
  vm.runInContext(source, sandbox);

  function trigger(type, event) {
    if (listeners[type]) listeners[type](event);
  }

  return { listeners, calls, trigger };
}

describe('service worker', function () {
  it('activates immediately without precaching resources', async function () {
    const sw = loadServiceWorker();
    let waited = null;
    sw.trigger('install', { waitUntil: (promise) => { waited = promise; } });

    assert.ok(waited && typeof waited.then === 'function');
    await waited;
    assert.strictEqual(sw.calls.skipWaiting, 1);
    assert.deepStrictEqual(sw.calls.fetch, []);
    assert.strictEqual(typeof sw.listeners.fetch, 'function');
    assert.strictEqual(sw.calls.keys, 0);
    assert.strictEqual(sw.calls.match.length, 0);
    assert.strictEqual(sw.calls.delete.length, 0);
  });

  it('removes only Cacao Accounting caches on activate', async function () {
    const sw = loadServiceWorker({ keys: ['cacao-accounting-v5', 'cacao-accounting-v4', 'other-app-cache'] });
    let waited = null;
    sw.trigger('activate', { waitUntil: (promise) => { waited = promise; } });

    await waited;
    assert.strictEqual(sw.calls.keys, 1);
    assert.deepStrictEqual(sw.calls.delete, ['cacao-accounting-v5', 'cacao-accounting-v4']);
    assert.strictEqual(sw.calls.claim, 1);
  });

  it('sends static and dynamic GET requests to network without CacheStorage', async function () {
    const staticResponse = { body: 'network-static' };
    const dynamicResponse = { body: 'network-page' };
    const networkResponses = [staticResponse, dynamicResponse];
    const sw = loadServiceWorker({ fetch: () => Promise.resolve(networkResponses.shift()) });

    const requests = [
      { method: 'GET', url: 'http://localhost/static/app.js' },
      { method: 'GET', url: 'http://localhost/dashboard' },
    ];
    const responses = [];
    for (const request of requests) {
      let responded = null;
      sw.trigger('fetch', { request, respondWith: (promise) => { responded = promise; } });
      responses.push(await responded);
    }

    assert.deepStrictEqual(responses, [staticResponse, dynamicResponse]);
    assert.strictEqual(sw.calls.fetch.length, 2);
    assert.strictEqual(sw.calls.keys, 0);
    assert.strictEqual(sw.calls.match.length, 0);
    assert.strictEqual(sw.calls.delete.length, 0);
  });

  it('lets network errors surface without returning a cached response', async function () {
    const sw = loadServiceWorker({ fetch: () => Promise.reject(new Error('offline')) });
    let responded = null;
    sw.trigger('fetch', {
      request: { method: 'GET', url: 'http://localhost/dashboard' },
      respondWith: (promise) => { responded = promise; },
    });

    await assert.rejects(responded, /offline/);
    assert.strictEqual(sw.calls.match.length, 0);
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
