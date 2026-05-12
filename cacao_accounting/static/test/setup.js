// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

'use strict';

const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

/**
 * Creates a fresh jsdom environment with Alpine mocked, then loads smart-select.js.
 * Returns a factory function that instantiates the smartSelect Alpine component.
 *
 * @param {object} [domExtras] - Extra attributes/properties to add to the window
 * @returns {{ factory: Function, window: Window, document: Document }}
 */
function createEnvironment(domExtras) {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: 'http://localhost/',
    runScripts: 'dangerously',
  });

  const { window } = dom;
  const { document } = window;

  // Mock Alpine.data so the IIFE registers the factory with us
  let capturedFactory = null;
  window.Alpine = {
    data: function (name, factory) {
      if (name === 'smartSelect') {
        capturedFactory = factory;
      }
    },
  };

  // Apply any extra properties
  if (domExtras) {
    Object.assign(window, domExtras);
  }

  // Fire alpine:init manually after loading the script
  const scriptSource = fs.readFileSync(
    path.join(__dirname, '..', 'js', 'smart-select.js'),
    'utf8'
  );

  const context = vm.createContext(window);
  vm.runInContext(scriptSource, context);

  // Dispatch alpine:init to trigger Alpine.data registration
  const alpineInitEvent = document.createEvent('Event');
  alpineInitEvent.initEvent('alpine:init', true, true);
  document.dispatchEvent(alpineInitEvent);

  if (!capturedFactory) {
    throw new Error('smartSelect factory was not registered — check alpine:init dispatch');
  }

  /**
   * Builds a component instance from the factory.
   * @param {object} config - smartSelect config object
   * @param {object} [rootEl] - optional root DOM element (for $root support)
   */
  function factory(config, rootEl) {
    const component = capturedFactory(config);
    component.$root = rootEl || null;
    return component;
  }

  return { factory, window, document };
}

/**
 * Creates a minimal fake fetch that resolves with a JSON payload.
 * Returns { fakeFetch, calls } where calls[] is the list of URLs fetched.
 */
function makeFetch(results, status) {
  const calls = [];
  const resolvedStatus = status === undefined ? 200 : status;
  function fakeFetch(url) {
    calls.push(url);
    return Promise.resolve({
      ok: resolvedStatus >= 200 && resolvedStatus < 300,
      status: resolvedStatus,
      statusText: resolvedStatus === 200 ? 'OK' : 'Error',
      json: function () {
        return Promise.resolve({ results: results || [] });
      },
    });
  }
  return { fakeFetch, calls };
}

/**
 * Creates a fake fetch that rejects (network error).
 */
function makeFailingFetch() {
  const calls = [];
  function fakeFetch(url) {
    calls.push(url);
    return Promise.reject(new Error('Network error'));
  }
  return { fakeFetch, calls };
}

module.exports = { createEnvironment, makeFetch, makeFailingFetch };
