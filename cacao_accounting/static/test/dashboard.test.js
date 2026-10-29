// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

const assert = require("assert");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function response(data, ok = true) {
  return { ok, json: () => Promise.resolve(data) };
}

function loadDashboard(fetchImpl) {
  globalThis.document = { getElementById: () => null, querySelector: () => null };
  globalThis.fetch = fetchImpl;
  const modulePath = require.resolve("../js/dashboard.js");
  delete require.cache[modulePath];
  require(modulePath);
  const dashboard = globalThis.dashboard();
  dashboard.$nextTick = (callback) => callback();
  return dashboard;
}

async function flushPromises() {
  await new Promise((resolve) => setImmediate(resolve));
}

describe("dashboard", function () {
  afterEach(function () {
    delete globalThis.document;
    delete globalThis.fetch;
    delete globalThis.dashboard;
  });

  it("keeps loading while a newer filter request is pending", async function () {
    const firstRequest = deferred();
    const secondRequest = deferred();
    const requests = [firstRequest, secondRequest];
    const dashboard = loadDashboard(() => requests.shift().promise);
    dashboard.filters.company = "COMP";

    dashboard.fetchData();
    dashboard.filters.period = "PER-NEW";
    dashboard.fetchData();

    firstRequest.resolve(response({ sections: { version: "old" } }));
    await flushPromises();

    assert.strictEqual(dashboard.loading, true);
    assert.strictEqual(dashboard.payload.sections.version, undefined);

    secondRequest.resolve(response({ sections: { version: "new" } }));
    await flushPromises();

    assert.strictEqual(dashboard.loading, false);
    assert.strictEqual(dashboard.payload.sections.version, "new");
  });

  it("does not let a late response replace newer data or its error state", async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    const dashboard = loadDashboard(() => requests.shift().promise);
    dashboard.filters.company = "COMP";

    dashboard.fetchData();
    dashboard.filters.period = "PER-NEW";
    dashboard.fetchData();
    newRequest.resolve(response({ sections: { version: "new" } }));
    await flushPromises();

    oldRequest.resolve(response({ sections: { version: "old" } }));
    await flushPromises();

    assert.strictEqual(dashboard.payload.sections.version, "new");
    assert.strictEqual(dashboard.error, "");
    assert.strictEqual(dashboard.loading, false);
  });

  it("ignores errors from an obsolete request", async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    const dashboard = loadDashboard(() => requests.shift().promise);
    dashboard.filters.company = "COMP";

    dashboard.fetchData();
    dashboard.filters.period = "PER-NEW";
    dashboard.fetchData();
    newRequest.resolve(response({ sections: { version: "new" } }));
    await flushPromises();
    oldRequest.reject(new Error("stale network failure"));
    await flushPromises();

    assert.strictEqual(dashboard.payload.sections.version, "new");
    assert.strictEqual(dashboard.error, "");
    assert.strictEqual(dashboard.loading, false);
  });

  it("shows a load error when the current request fails", async function () {
    const currentRequest = deferred();
    const dashboard = loadDashboard(() => currentRequest.promise);
    dashboard.filters.company = "COMP";

    dashboard.fetchData();
    currentRequest.reject(new Error("network failure"));
    await flushPromises();

    assert.strictEqual(dashboard.error, "No se pudo cargar el dashboard.");
    assert.strictEqual(dashboard.loading, false);
  });

  it("invalidates pending requests when the company filter is cleared", async function () {
    const pendingRequest = deferred();
    const dashboard = loadDashboard(() => pendingRequest.promise);
    dashboard.filters.company = "COMP";
    dashboard.fetchData();

    dashboard.filters.company = "";
    dashboard.fetchData();
    pendingRequest.resolve(response({ sections: { version: "stale" } }));
    await flushPromises();

    assert.deepStrictEqual(dashboard.payload, { sections: {} });
    assert.strictEqual(dashboard.loading, false);
    assert.strictEqual(dashboard.error, "");
  });


});
