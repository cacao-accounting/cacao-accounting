// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

const assert = require('assert');
const { documentFlowTree } = require('../js/document-flow-tree.js');

describe('document-flow-tree', function () {
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
});
