// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

const assert = require('assert');

function loadTransactionForm() {
  const listeners = {};
  let transactionFormFactory = null;

  global.window = {
    crypto: {
      randomUUID: () => 'uuid-test',
    },
  };

  global.document = {
    addEventListener: (event, callback) => {
      listeners[event] = callback;
    },
    querySelector: () => null,
    getElementById: () => null,
  };

  global.bootstrap = {
    Modal: {
      getOrCreateInstance: () => ({
        show() {},
        hide() {},
      }),
    },
  };

  global.Alpine = {
    data: (name, factory) => {
      if (name === 'transactionForm') transactionFormFactory = factory;
    },
  };

  const modulePath = require.resolve('../js/transaction-form.js');
  delete require.cache[modulePath];
  require(modulePath);
  listeners['alpine:init']();

  return function create(config) {
    return transactionFormFactory(config);
  };
}

describe('transaction-form', function () {
  afterEach(function () {
    delete global.window;
    delete global.document;
    delete global.bootstrap;
    delete global.Alpine;
  });

  it('uses required default columns when preferences are empty', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [],
      uoms: [],
      columns: [],
      defaultRows: 1,
    });

    component.init();

    assert.deepStrictEqual(
      component.visibleColumns.map((column) => column.field),
      ['item_code', 'item_name', 'uom', 'qty', 'rate', 'amount']
    );
    assert.strictEqual(component.lines.length, 1);
  });

  it('keeps required columns visible even when legacy preferences hide them', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [],
      uoms: [],
      columns: [
        { field: 'item_code', label: 'Código', visible: false, width: 2 },
        { field: 'item_name', label: 'Descripción', visible: true, width: 2 },
      ],
      defaultRows: 1,
    });

    component.init();

    assert.strictEqual(component.preferences.columns.find((column) => column.field === 'item_code').visible, true);
    assert.strictEqual(component.preferences.columns.find((column) => column.field === 'item_code').required, true);
  });

  it('filters unit options based on the selected item and keeps the selected unit valid', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [
        { code: 'ITEM-001', name: 'Caja de cacao', uom: 'UND', allowed_uoms: ['UND', 'CAJA'] },
        { code: 'ITEM-002', name: 'Servicio logístico', uom: 'SERV' },
      ],
      uoms: [
        { code: 'UND', name: 'Unidad' },
        { code: 'CAJA', name: 'Caja' },
        { code: 'SERV', name: 'Servicio' },
      ],
      defaultRows: 1,
    });

    component.init();
    const line = component.lines[0];
    line.item_code = 'ITEM-001';

    component.onItemChange(line);

    assert.strictEqual(line.item_name, 'Caja de cacao');
    assert.strictEqual(line.uom, 'UND');
    assert.deepStrictEqual(component.getLineUoms(line).map((uom) => uom.code), ['UND', 'CAJA']);

    line.uom = 'CAJA';
    line.item_code = 'ITEM-002';
    component.onItemChange(line);

    assert.strictEqual(line.item_name, 'Servicio logístico');
    assert.strictEqual(line.uom, 'SERV');
    assert.deepStrictEqual(component.getLineUoms(line).map((uom) => uom.code), ['SERV']);
  });

  it('preserves edited source quantities when importing lines', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [{ code: 'ITEM-001', name: 'Caja de cacao', uom: 'UND' }],
      uoms: [{ code: 'UND', name: 'Unidad' }],
      defaultRows: 1,
    });

    component.init();
    component.sourceItems = [
      {
        selected: true,
        item_code: 'ITEM-001',
        item_name: 'Caja de cacao',
        qty: 2.5,
        pending_qty: 10,
        uom: 'UND',
        rate: 4,
        source_type: 'purchase_order',
        source_id: 'PO-001',
        source_item_id: 'PO-ROW-001',
      },
    ];

    component.applySource();

    assert.strictEqual(component.lines.length, 1);
    assert.strictEqual(component.lines[0].qty, 2.5);
    assert.strictEqual(component.lines[0].amount, 10);
  });

  it('opens line detail with existing analytical values and saves edits back to the row', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [],
      uoms: [],
      defaultRows: 1,
      initialLines: [
        {
          item_code: 'ITEM-001',
          item_name: 'Caja de cacao',
          qty: 1,
          rate: 10,
          account: 'expense-cacao',
          cost_center: 'main-cc',
          unit: 'north',
          project: 'launch',
          remarks: 'Original',
        },
      ],
    });

    component.init();
    component.openDetails(0);

    assert.strictEqual(component.modalLine.account, 'expense-cacao');
    assert.strictEqual(component.modalLine.cost_center, 'main-cc');
    assert.strictEqual(component.modalLine.unit, 'north');
    assert.strictEqual(component.modalLine.project, 'launch');

    component.modalLine.account = 'inventory-cacao';
    component.modalLine.remarks = 'Updated';
    component.saveModalLine();

    assert.strictEqual(component.lines[0].account, 'inventory-cacao');
    assert.strictEqual(component.lines[0].remarks, 'Updated');
    assert.strictEqual(component.lines[0].amount, 10);
  });
});
