// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

const assert = require('assert');
const { documentFlowTree, renderTree } = require('../js/document-flow-tree.js');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flushPromises() {
  await new Promise((resolve) => setImmediate(resolve));
}

const englishMessages = {
  total: 'Total:',
  relationship: 'Relationship:',
  applied: 'Applied:',
  unallocated: 'Unallocated:',
  voided: 'Voided',
  current: 'Current',
  cycleDetected: 'Cycle detected',
  maxDepthReached: 'Maximum depth reached',
  maxNodesReached: 'Node limit reached',
  document: 'document',
  documents: 'documents',
  relatedDocument: 'related document',
  relatedDocuments: 'related documents',
  relationTypes: {
    payment_reference: 'Payment reference',
  },
};

describe('document-flow-tree', function () {
  afterEach(function () {
    delete globalThis.fetch;
  });

  it('renders translated node, relation and expansion labels', function () {
    const current = {
      document_type: 'payment_entry',
      document_id: 'PAY-001',
      docstatus: 2,
      total: '120',
      currency: 'USD',
      relation_type: 'payment_reference',
      applied_amount: '50',
      children: [{ document_type: 'sales_invoice', document_id: 'INV-001', label: 'Invoice' }],
    };

    const html = renderTree([current], current, false, englishMessages);

    assert.ok(html.includes('Voided'));
    assert.ok(html.includes('Current'));
    assert.ok(html.includes('Total:'));
    assert.ok(html.includes('Relationship:'));
    assert.ok(html.includes('Payment reference'));
    assert.ok(!html.includes('payment_reference'));
    assert.ok(html.includes('Applied:'));
    assert.ok(html.includes('+1 related document'));
    assert.ok(!html.includes('Relación:'));
    assert.ok(!html.includes('documento(s)'));
  });

  it('translates count labels, payment summary and tree limits', function () {
    const tree = documentFlowTree({ messages: englishMessages });
    const current = {
      document_type: 'payment_entry',
      document_id: 'PAY-001',
      total: '120',
      unallocated_amount: '70',
      currency: 'USD',
    };
    tree.current = current;
    tree.meta = { node_count: 0 };
    tree.downstream = [{ applied_amount: '50' }];
    assert.strictEqual(tree.documentCountLabel, '1 document');

    tree.meta = { node_count: 2 };
    assert.strictEqual(tree.documentCountLabel, '3 documents');

    const summary = tree.renderCurrentNode();
    assert.ok(summary.includes('Total:'));
    assert.ok(summary.includes('Applied:'));
    assert.ok(summary.includes('Unallocated:'));

    const limits = renderTree(
      [{ cycle_detected: true }, { max_depth_reached: true }, { max_nodes_reached: true }],
      null,
      true,
      englishMessages
    );
    assert.ok(limits.includes('Cycle detected'));
    assert.ok(limits.includes('Maximum depth reached'));
    assert.ok(limits.includes('Node limit reached'));
  });

  it('uses the payment-currency balance instead of reference document amounts', function () {
    const tree = documentFlowTree({ docstatus: 1 });
    tree.current = {
      document_type: 'payment_entry',
      total: '500',
      unallocated_amount: '200',
      currency: 'USD',
    };
    tree.downstream = [
      {
        relation_type: 'payment_reference',
        relation_status: 'active',
        applied_amount: '450',
        children: [{ relation_type: 'payment', relation_status: 'active', applied_amount: '200', children: [] }],
      },
      { relation_type: 'payment_reference', relation_status: 'reverted', applied_amount: '100', children: [] },
    ];

    assert.strictEqual(tree.currentAppliedAmount, 300);
    assert.strictEqual(tree.currentUnallocatedAmount, 200);
  });

  it('uses the current API status when a payment was cancelled after page render', function () {
    const tree = documentFlowTree({ docstatus: 1 });
    tree.current = {
      document_type: 'payment_entry',
      docstatus: 2,
      total: '500',
      unallocated_amount: '500',
      currency: 'USD',
    };
    tree.downstream = [{ relation_type: 'payment_reference', relation_status: 'reverted', applied_amount: '125' }];

    assert.strictEqual(tree.isCancelled, true);
    assert.strictEqual(tree.currentAppliedAmount, 0);
    assert.strictEqual(tree.currentUnallocatedAmount, 0);
  });

  it('ignores stale responses and errors from earlier loads', async function () {
    const firstRequest = deferred();
    const secondRequest = deferred();
    const requests = [firstRequest, secondRequest];
    globalThis.fetch = () => requests.shift().promise;
    const tree = documentFlowTree({ apiUrl: '/document-flow' });

    tree.load();
    tree.load();
    secondRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ current: { document_id: 'new' }, upstream: [], downstream: [], meta: { node_count: 0 } }),
    });
    await flushPromises();
    firstRequest.reject(new Error('stale request failed'));
    await flushPromises();

    assert.strictEqual(tree.current.document_id, 'new');
    assert.strictEqual(tree.loaded, true);
    assert.strictEqual(tree.error, false);
    assert.strictEqual(tree.loading, false);
  });

  it('ignores a stale success after a newer load succeeds', async function () {
    const firstRequest = deferred();
    const secondRequest = deferred();
    const requests = [firstRequest, secondRequest];
    globalThis.fetch = () => requests.shift().promise;
    const tree = documentFlowTree({ apiUrl: '/document-flow' });

    tree.load();
    tree.load();
    secondRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ current: { document_id: 'new' }, upstream: [], downstream: [] }),
    });
    await flushPromises();
    firstRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ current: { document_id: 'old' }, upstream: [], downstream: [] }),
    });
    await flushPromises();

    assert.strictEqual(tree.current.document_id, 'new');
    assert.strictEqual(tree.loaded, true);
    assert.strictEqual(tree.error, false);
    assert.strictEqual(tree.loading, false);
  });
});
