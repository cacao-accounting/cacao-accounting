// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

const assert = require('assert');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function loadTransactionForm() {
  const listeners = {};
  let transactionFormFactory = null;
  const scheduledTimeouts = new Map();
  let nextTimeoutId = 1;

  globalThis.window = {
    crypto: {
      randomUUID: () => 'uuid-test',
    },
  };

  globalThis.document = {
    addEventListener: (event, callback) => {
      listeners[event] = callback;
    },
    querySelector: () => null,
    getElementById: () => null,
  };

  globalThis.bootstrap = {
    Modal: {
      getOrCreateInstance: () => ({
        show() {},
        hide() {},
      }),
    },
  };

  globalThis.Alpine = {
    data: (name, factory) => {
      if (name === 'transactionForm') transactionFormFactory = factory;
    },
  };

  globalThis.setTimeout = (callback) => {
    const timeoutId = nextTimeoutId;
    nextTimeoutId += 1;
    scheduledTimeouts.set(timeoutId, callback);
    return timeoutId;
  };

  globalThis.clearTimeout = (timeoutId) => {
    scheduledTimeouts.delete(timeoutId);
  };

  const modulePath = require.resolve('../js/transaction-form.js');
  delete require.cache[modulePath];
  require(modulePath);
  listeners['alpine:init']();

  const create = function create(config) {
    return transactionFormFactory(config);
  };
  create.runNextTimeout = function runNextTimeout() {
    const next = scheduledTimeouts.entries().next().value;
    if (!next) return false;
    const [timeoutId, callback] = next;
    scheduledTimeouts.delete(timeoutId);
    callback();
    return true;
  };
  create.pendingTimeoutCount = () => scheduledTimeouts.size;
  return create;
}

describe('transaction-form', function () {
  afterEach(function () {
    delete globalThis.window;
    delete globalThis.document;
    delete globalThis.bootstrap;
    delete globalThis.Alpine;
    delete globalThis.fetch;
    delete globalThis.setTimeout;
    delete globalThis.clearTimeout;
  });

  it('returns default visible columns for transactional forms', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    component.init();

    assert.deepStrictEqual(
      component.visibleColumns.map((column) => column.field),
      ['item_code', 'item_name', 'uom', 'qty', 'rate', 'amount']
    );
    assert.strictEqual(component.lines.length, 1);
  });

  it('locks company and currency for document flow forms', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_quotation',
      initialSourceType: 'purchase_request',
      initialHeader: { company: 'cacao', currency: 'NIO' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    component.init();

    assert.strictEqual(component.isFlowFieldLocked('company'), true);
    assert.strictEqual(component.isFlowFieldLocked('currency'), true);
    assert.strictEqual(component.isFlowFieldLocked('naming_series'), false);
  });

  it('prevents submit while source lines are loading or missing', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_quotation',
      initialSourceType: 'purchase_request',
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();

    const loadingEvent = { prevented: false, preventDefault() { this.prevented = true; } };
    component.sourceHydrationPending = true;
    component.prepareSubmit(loadingEvent);
    assert.strictEqual(loadingEvent.prevented, true);

    const emptyEvent = { prevented: false, preventDefault() { this.prevented = true; } };
    component.sourceHydrationPending = false;
    component.prepareSubmit(emptyEvent);
    assert.strictEqual(emptyEvent.prevented, true);
  });

  it('accepts a purchase transaction currency when the generic currency field is absent', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_order',
      initialHeader: { transaction_currency: 'NIO' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();

    const event = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(event);

    assert.strictEqual(event.prevented, false);
    assert.strictEqual(component.submitError, '');
  });

  it('preserves a manually entered amount for value-only inventory adjustments', function () {
    const create = loadTransactionForm();
    const component = create({
      allowManualAmount: true,
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    const line = component.lines[0];
    line.qty = 0;
    line.rate = 100;
    line.amount = 25;

    component.calcAmount(line);

    assert.strictEqual(line.amount, 25);
  });

  it('always returns all default columns regardless of config', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_order',
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    assert.strictEqual(component.visibleColumns.length, 6);
    assert.strictEqual(component.visibleColumns[0].field, 'item_code');
    assert.strictEqual(component.visibleColumns[1].field, 'item_name');
    assert.strictEqual(component.visibleColumns[2].field, 'uom');
    assert.strictEqual(component.visibleColumns[3].field, 'qty');
    assert.strictEqual(component.visibleColumns[4].field, 'rate');
    assert.strictEqual(component.visibleColumns[5].field, 'amount');
  });

  it('hides price columns when pricing is disabled', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'inventory.stock_entry',
      showPricing: false,
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    const fields = component.preferences.columns.map((column) => column.field);
    assert.strictEqual(fields.includes('rate'), true);
    assert.strictEqual(fields.includes('amount'), true);
    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'rate'), false);
    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'amount'), false);
  });

  it('adds the discount column when line discounts are enabled', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_order',
      enableLineDiscounts: true,
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    const discount = component.preferences.columns.find((column) => column.field === 'discount_percentage');
    assert.ok(discount);
    assert.strictEqual(discount.visible, true);
    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'discount_percentage'), true);
  });

  it('appends custom config columns but never the warehouse column', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_order',
      columns: [
        { field: 'warehouse', label: 'Almacén', visible: true, width: 2 },
        { field: 'custom_note', label: 'Nota', visible: true, width: 2 },
      ],
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    const fields = component.preferences.columns.map((column) => column.field);
    assert.strictEqual(fields.includes('custom_note'), true);
    assert.strictEqual(fields.includes('warehouse'), false);
  });

  it('keeps required default columns visible even when config hides them', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_order',
      columns: [{ field: 'item_code', visible: false, width: 4 }],
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    const itemCode = component.preferences.columns.find((column) => column.field === 'item_code');
    assert.strictEqual(itemCode.required, true);
    assert.strictEqual(itemCode.visible, true);
    assert.strictEqual(itemCode.width, 4);
  });

  it('keeps warehouse at the header level instead of the line grid', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_order',
      columns: [{ field: 'warehouse', label: 'Almacén', visible: true, width: 2 }],
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();

    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'warehouse'), false);
    assert.strictEqual(component.header.warehouse, '');
  });

  it('keeps lot and serial inputs in the detail modal instead of the inline grid', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'inventory.stock_entry',
      enableBatchSerial: true,
      initialHeader: { currency: 'NIO' },
      items: [{ code: 'LOT-ITEM', name: 'Artículo con lote', uom: 'UND', has_batch: true }],
      uoms: [{ code: 'UND', name: 'Unidad' }],
      defaultRows: 1,
    });
    component.init();
    const line = component.lines[0];
    line.item_code = 'LOT-ITEM';
    component.onItemChange(line);

    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'batch_id'), false);
    assert.strictEqual(component.visibleColumns.some((column) => column.field === 'serial_no'), false);
    const event = { prevented: false, preventDefault() { this.prevented = true; } };
    component.prepareSubmit(event);
    assert.strictEqual(event.prevented, true);
    assert.strictEqual(component.submitError, 'El item LOT-ITEM requiere lote.');
  });

  it('keeps required batch and serial status visible in the modal for tracked items', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'inventory.stock_entry',
      items: [{ code: 'LOT-ITEM', name: 'Artículo con lote', uom: 'UND', has_batch: true, has_serial_no: true }],
      uoms: [{ code: 'UND', name: 'Unidad' }],
      defaultRows: 1,
    });
    component.init();

    const line = component.lines[0];
    line.item_code = 'LOT-ITEM';
    line.batch_id = 'BATCH-001';
    line.serial_no = 'SER-001';
    const normalized = component.normalizeLine(line);

    assert.strictEqual(normalized.has_batch, true);
    assert.strictEqual(normalized.has_serial_no, true);
    assert.strictEqual(Boolean(normalized.batch_id), true);
    assert.strictEqual(Boolean(normalized.serial_no), true);
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

  it('matches required template headers and aliases when parsing pasted imports', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    component.init();
    component.importModal.schema = {
      columns: [
        { key: 'item_code', label: 'Artículo', aliases: ['item'] },
        { key: 'quantity', label: 'Cantidad', aliases: ['qty'] },
      ],
    };
    component.importModal.pastedText = 'Artículo *\tqty\nITEM-001\t2\n\t\n';

    component.parsePastedText();

    assert.deepStrictEqual(component.importModal.parsedRows, [
      { item_code: 'ITEM-001', quantity: '2' },
    ]);
  });

  it('keeps existing rows intact when appending imported lines', function () {
    const create = loadTransactionForm();
    const component = create({
      items: [{ code: 'ITEM-001', name: 'Caja de cacao', uom: 'UND' }],
      uoms: [{ code: 'UND', name: 'Unidad' }],
      defaultRows: 0,
      initialLines: [{ item_code: 'MANUAL-001', item_name: 'Manual', qty: 3, rate: 5, amount: 15 }],
    });

    component.init();
    component.importModal.doctype = 'purchase_request';
    component.importModal.isValidated = true;
    component.importModal.parsedRows = [{ item_code: 'ITEM-001', item_name: 'Caja de cacao', quantity: 2, uom: 'UND' }];

    component.insertImportedLines();

    assert.strictEqual(component.lines.length, 2);
    assert.strictEqual(component.lines[0].item_code, 'MANUAL-001');
    assert.strictEqual(component.lines[0].item_name, 'Manual');
    assert.strictEqual(component.lines[0].qty, 3);
    assert.strictEqual(component.lines[0].rate, 5);
    assert.strictEqual(component.lines[0].amount, 15);
    assert.strictEqual(component.lines[1].item_code, 'ITEM-001');
    assert.strictEqual(component.lines[1].qty, 2);
  });

  it('enables line import for operational doctypes', function () {
    const create = loadTransactionForm();
    [
      'purchases.purchase_request',
      'purchases.purchase_quotation',
      'purchases.supplier_quotation',
      'purchases.purchase_order',
      'purchases.purchase_receipt',
      'purchases.purchase_invoice',
      'sales.sales_request',
      'sales.sales_quotation',
      'sales.sales_order',
      'sales.delivery_note',
      'sales.sales_invoice',
      'inventory.stock_entry',
    ].forEach((formKey) => {
      const supported = create({
        formKey,
        items: [],
        uoms: [],
        defaultRows: 1,
      });
      supported.init();
      assert.strictEqual(supported.supportsLineImport(), true, formKey);
    });

    const unsupported = create({
      formKey: 'sales.customer',
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    unsupported.init();
    assert.strictEqual(unsupported.supportsLineImport(), false);
  });

  it('adds same-document update sources to operational doctypes', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_order',
      items: [],
      uoms: [],
      defaultRows: 1,
      availableSourceTypes: [
        { value: 'purchase_request', label: 'Solicitud de Compra' },
      ],
    });
    component.init();

    assert.deepStrictEqual(
      component.availableSourceTypes.map((sourceType) => sourceType.value),
      ['purchase_order', 'purchase_request']
    );

    const firstDocument = create({
      formKey: 'sales.sales_request',
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    firstDocument.init();
    assert.deepStrictEqual(
      firstDocument.availableSourceTypes.map((sourceType) => sourceType.value),
      ['sales_request']
    );
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

  it('skips fiscal preview calls for document types outside the fiscal matrix', async function () {
    const create = loadTransactionForm();
    let called = false;
    globalThis.fetch = async () => {
      called = true;
      throw new Error('unexpected preview call');
    };
    const component = create({
      formKey: 'sales.sales_quotation',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'cacao' },
    });

    component.init();
    await component.fetchTaxPreview();

    assert.strictEqual(component.supportsFiscalPreview(), false);
    assert.strictEqual(called, false);
    assert.strictEqual(component.taxCharges.error, '');
  });

  it('reports fiscal preview fetch failures through the shared error handler', async function () {
    const create = loadTransactionForm();
    const warnings = [];
    const originalWarn = console.warn;
    console.warn = (...args) => warnings.push(args);
    globalThis.fetch = async () => {
      throw new Error('preview down');
    };

    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'cacao' },
    });

    component.init();
    await component.fetchTaxPreview();

    console.warn = originalWarn;
    assert.strictEqual(component.taxCharges.error, 'No se pudo calcular.');
    assert.strictEqual(component.taxCharges.loading, false);
    assert.strictEqual(warnings.length, 1);
  });

  it('adds manual tax or charge lines and updates fiscal totals', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'cacao' },
      initialLines: [{ item_code: 'ITEM-001', item_name: 'Caja de cacao', qty: 2, rate: 50 }],
    });

    component.init();
    component.addTaxLine();
    component.taxCharges.modalLine.concept = 'Flete';
    component.taxCharges.modalLine.type = 'charge';
    component.taxCharges.modalLine.amount = 12.5;
    component.taxCharges.modalLine.accounting_treatment = 'capitalizable_inventory_cost';
    component.saveTaxLineModal();

    assert.strictEqual(component.taxCharges.lines.length, 1);
    assert.strictEqual(component.taxCharges.lines[0].manual, true);
    assert.strictEqual(component.taxCharges.lines[0].concept, 'Flete');
    assert.strictEqual(component.taxCharges.lines[0].affects_inventory, true);
    assert.strictEqual(component.taxCharges.summary.document_tax_total, '12.5');
    assert.strictEqual(component.taxCharges.summary.capitalizable_tax_total, '12.5');
    assert.strictEqual(component.grandTotal, 112.5);

    const payload = component.buildFiscalPayload();
    assert.strictEqual(payload.tax_lines[0].manual, true);
    assert.strictEqual(payload.tax_lines[0].allocation_method, 'by_value');
    assert.strictEqual(payload.tax_lines[0].affects_inventory, true);
  });

  it('derives inventory impact from treatment and ignores stale checkbox data', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    const line = component.normalizeTaxLine({
      manual: true,
      accounting_treatment: 'expense',
      affects_inventory: true,
      amount: 10,
    });

    assert.strictEqual(line.affects_inventory, false);
    line.accounting_treatment = 'capitalizable_inventory_cost';
    component.syncTaxTreatment(line);
    assert.strictEqual(line.affects_inventory, true);
  });

  it('reports import validation fetch failures through the shared error handler', async function () {
    const create = loadTransactionForm();
    const warnings = [];
    const originalWarn = console.warn;
    console.warn = (...args) => warnings.push(args);
    globalThis.fetch = async () => {
      throw new Error('validation down');
    };

    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
    });

    component.init();
    component.importModal.doctype = 'purchase_invoice';
    component.importModal.schema = { columns: [] };
    component.importModal.parsedRows = [{ item_code: 'ITEM-001' }];

    await component.validateImport();

    console.warn = originalWarn;
    assert.strictEqual(component.importModal.validating, false);
    assert.deepStrictEqual(component.importModal.errors, [{ message: 'Error de conexión al validar.' }]);
    assert.strictEqual(warnings.length, 1);
  });

  it('does not apply an old sales catalog price after pricing context changes', async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    globalThis.fetch = () => requests.shift().promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', party: 'CUSTOMER-A', currency: 'USD', posting_date: '2026-10-28' },
    });
    const line = component.newLine();
    line.item_code = 'ITEM-001';
    line.uom = 'EA';
    component.lines = [line];

    const oldPrice = component.refreshCatalogPrice(line);
    component.header.party = 'CUSTOMER-B';
    const newPrice = component.refreshCatalogPrice(line);
    newRequest.resolve({ ok: true, json: () => Promise.resolve({ price: '80', price_list_name: 'B' }) });
    await newPrice;
    oldRequest.resolve({ ok: true, json: () => Promise.resolve({ price: '100', price_list_name: 'A' }) });
    await oldPrice;

    assert.strictEqual(line.rate, 80);
    assert.strictEqual(line.price_list_name, 'B');
  });

  it('refreshes the sales catalog price when the line UOM changes', async function () {
    let requestUrl = '';
    globalThis.fetch = async (url) => {
      requestUrl = url;
      return { ok: true, json: async () => ({ price: '24', price_list_name: 'Box prices' }) };
    };
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });
    const line = component.newLine();
    line.item_code = 'ITEM-001';
    component.lines = [line];

    await component.onUomChange(line, 'BOX');

    assert.strictEqual(line.uom, 'BOX');
    assert.strictEqual(line.rate, 24);
    assert.strictEqual(new URL(requestUrl, 'http://localhost').searchParams.get('uom'), 'BOX');
  });

  it('clears the previous catalog price when the selected item has no price', async function () {
    const responses = [
      { price: '12', price_list_name: 'List' },
      { price: null, price_list_name: null },
    ];
    globalThis.fetch = async () => ({ ok: true, json: async () => responses.shift() });
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });
    const line = component.newLine();
    line.item_code = 'ITEM-A';
    component.lines = [line];

    await component.refreshCatalogPrice(line);
    line.item_code = 'ITEM-B';
    await component.refreshCatalogPrice(line);

    assert.strictEqual(line.rate, 0);
    assert.strictEqual(line.price_list_name, '');
  });

  it('does not replace a manually edited sales price with a pending lookup', async function () {
    const request = deferred();
    globalThis.fetch = () => request.promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_invoice',
      canEditPrices: true,
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });
    const line = component.newLine();
    line.item_code = 'ITEM-001';
    component.lines = [line];

    const lookup = component.refreshCatalogPrice(line);
    line.rate = 75;
    component.onRateInput(line);
    request.resolve({ ok: true, json: () => Promise.resolve({ price: '100', price_list_name: 'List' }) });
    await lookup;

    assert.strictEqual(line.rate, 75);
  });

  it('keeps the latest fiscal preview when requests finish out of order', async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    globalThis.fetch = () => requests.shift().promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });

    const oldPreview = component.fetchTaxPreview();
    component.header.posting_date = '2026-10-28';
    const newPreview = component.fetchTaxPreview();
    newRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ summary: { document_tax_total: '8' }, tax_lines: [{ concept: 'new' }] }),
    });
    await newPreview;
    oldRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ summary: { document_tax_total: '2' }, tax_lines: [{ concept: 'old' }] }),
    });
    await oldPreview;

    assert.strictEqual(component.taxCharges.summary.document_tax_total, '8');
    assert.strictEqual(component.taxCharges.lines[0].concept, 'new');
  });

  it('refreshes fiscal preview after header changes and ignores the prior context', async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    globalThis.fetch = () => requests.shift().promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });
    const watchers = {};
    component.$watch = (expression, callback) => { watchers[expression] = callback; };
    component.init();

    assert.strictEqual(typeof watchers['header.currency'], 'function');
    assert.strictEqual(create.runNextTimeout(), true);
    component.header.currency = 'NIO';
    watchers['header.currency']();
    assert.strictEqual(create.runNextTimeout(), true);

    newRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ summary: { document_tax_total: '8' }, tax_lines: [{ concept: 'NIO' }] }),
    });
    await new Promise((resolve) => setImmediate(resolve));
    oldRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ summary: { document_tax_total: '2' }, tax_lines: [{ concept: 'USD' }] }),
    });
    await new Promise((resolve) => setImmediate(resolve));

    assert.strictEqual(component.taxCharges.summary.document_tax_total, '8');
    assert.strictEqual(component.taxCharges.lines[0].concept, 'NIO');
  });

  it('cancels a queued fiscal preview when opening tax-line editing', function () {
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      items: [],
      uoms: [],
      defaultRows: 1,
      initialHeader: { company: 'COMP', currency: 'USD' },
    });
    component.taxCharges.lines = [component.newTaxLine()];
    component.queueTaxPreview();
    assert.strictEqual(create.pendingTimeoutCount(), 1);

    component.openTaxLineDetails(0);

    assert.strictEqual(create.pendingTimeoutCount(), 0);
  });

  it('keeps source documents from the latest company lookup', async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    globalThis.fetch = () => requests.shift().promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-1' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    component.searchCriteria.source_type = 'purchase_order';

    const oldLookup = component.fetchSourceDocuments();
    component.header.company = 'company-b';
    const newLookup = component.fetchSourceDocuments();

    newRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ source_documents: [{ source_id: 'PO-B', source_type: 'purchase_order' }] }),
    });
    await newLookup;
    oldRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ source_documents: [{ source_id: 'PO-A', source_type: 'purchase_order' }] }),
    });
    await oldLookup;

    assert.deepStrictEqual(component.sourceDocuments.map((doc) => doc.source_id), ['PO-B']);
    assert.strictEqual(component.loadingSource, false);
  });

  it('keeps pending source lines from the latest document selection', async function () {
    const oldRequest = deferred();
    const newRequest = deferred();
    const requests = [oldRequest, newRequest];
    globalThis.fetch = () => requests.shift().promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-1' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    component.searchCriteria.source_type = 'purchase_order';
    component.sourceDocuments = [{ source_id: 'PO-A', selected: true }];

    const oldLookup = component.fetchSourceItems();
    component.showSourceDocuments();
    component.sourceDocuments = [{ source_id: 'PO-B', selected: true }];
    const newLookup = component.fetchSourceItems();

    newRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [{ source_id: 'PO-B', source_item_id: 'ROW-B', item_code: 'ITEM-B' }] }),
    });
    await newLookup;
    oldRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [{ source_id: 'PO-A', source_item_id: 'ROW-A', item_code: 'ITEM-A' }] }),
    });
    await oldLookup;

    assert.deepStrictEqual(component.sourceItems.map((item) => item.source_item_id), ['ROW-B']);
    assert.strictEqual(component.loadingSource, false);
  });

  it('rejects URL source lines when the target party changes during loading', async function () {
    const pendingRequest = deferred();
    globalThis.fetch = () => pendingRequest.promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_quotation',
      initialSourceType: 'sales_request',
      initialHeader: { company: 'company-a', party_type: 'customer', party: 'customer-a' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    component.lines = [];

    const hydration = component.loadSourceFromUrl('/api/source-lines?request=REQ-A');
    component.header.party = 'customer-b';
    pendingRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [{ item_code: 'ITEM-A', source_id: 'REQ-A', source_item_id: 'ROW-A' }] }),
    });

    const loaded = await hydration;
    if (loaded) component.applySource();

    assert.strictEqual(loaded, false);
    assert.deepStrictEqual(component.sourceItems, []);
    assert.deepStrictEqual(component.lines, []);
    assert.strictEqual(component.sourceHydrationPending, false);
    assert.strictEqual(component.loadingSource, false);
  });

  it('invalidates pending URL source hydration when returning to document selection', async function () {
    const pendingRequest = deferred();
    globalThis.fetch = () => pendingRequest.promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialSourceType: 'purchase_order',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-a' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    component.lines = [];

    const hydration = component.loadSourceFromUrl('/api/source-lines?order=PO-A');
    component.showSourceDocuments();
    pendingRequest.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [{ item_code: 'ITEM-A', source_id: 'PO-A', source_item_id: 'ROW-A' }] }),
    });

    const loaded = await hydration;
    if (loaded) component.applySource();

    assert.strictEqual(loaded, false);
    assert.deepStrictEqual(component.sourceItems, []);
    assert.deepStrictEqual(component.lines, []);
    assert.strictEqual(component.autofillStep, 1);
    assert.strictEqual(component.sourceHydrationPending, false);
    assert.strictEqual(component.loadingSource, false);
  });

  it('applies current URL source lines only after hydration completes', async function () {
    globalThis.fetch = () => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        items: [{ item_code: 'ITEM-A', item_name: 'Cacao', qty: 2, rate: 5, source_id: 'PO-A', source_item_id: 'ROW-A' }],
      }),
    });
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialSourceType: 'purchase_order',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-a' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();

    const loaded = await component.loadSourceFromUrl('/api/source-lines?order=PO-A');
    if (loaded) component.applySource();

    assert.strictEqual(loaded, true);
    assert.strictEqual(component.lines.length, 1);
    assert.strictEqual(component.lines[0].source_id, 'PO-A');
    assert.strictEqual(component.lines[0].amount, 10);
    assert.strictEqual(component.sourceHydrationPending, false);
    assert.strictEqual(component.loadingSource, false);
  });

  it('does not apply source lines while their lookup is still loading', function () {
    const create = loadTransactionForm();
    const component = create({ items: [], uoms: [], defaultRows: 1 });
    component.init();
    component.lines = [];
    component.loadingSource = true;
    component.sourceItems = [{
      selected: true,
      item_code: 'ITEM-001',
      item_name: 'Caja de cacao',
      qty: 1,
      source_type: 'purchase_order',
      source_id: 'PO-001',
      source_item_id: 'PO-ROW-001',
    }];

    component.applySource();

    assert.deepStrictEqual(component.lines, []);
  });

  it('reports source document lookup failures to the user', async function () {
    const originalWarn = console.warn;
    console.warn = () => {};
    globalThis.fetch = async () => ({ ok: false, statusText: 'Unavailable' });
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-1' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();

    try {
      await component.fetchSourceDocuments();
    } finally {
      console.warn = originalWarn;
    }

    assert.strictEqual(component.sourceLoadError, 'No se pudieron cargar los documentos de origen.');
    assert.strictEqual(component.loadingSource, false);
    assert.deepStrictEqual(component.sourceDocuments, []);
  });

  it('reports pending source line failures and does not apply an empty result', async function () {
    const originalWarn = console.warn;
    console.warn = () => {};
    globalThis.fetch = async () => ({ ok: false, statusText: 'Unavailable' });
    const create = loadTransactionForm();
    const component = create({
      formKey: 'purchases.purchase_invoice',
      initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-1' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    component.sourceDocuments = [{ source_id: 'PO-001', selected: true }];
    const placeholder = component.lines[0];

    try {
      await component.fetchSourceItems();
      component.applySource();
    } finally {
      console.warn = originalWarn;
    }

    assert.notStrictEqual(component.sourceLoadError, '');
    assert.strictEqual(component.loadingSource, false);
    assert.strictEqual(component.lines[0], placeholder);
    assert.deepStrictEqual(component.sourceItems, []);
  });

  it('ignores URL source errors from an obsolete party context', async function () {
    const pendingRequest = deferred();
    globalThis.fetch = () => pendingRequest.promise;
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_quotation',
      initialSourceType: 'sales_request',
      initialHeader: { company: 'company-a', party_type: 'customer', party: 'customer-a' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    component.init();
    const originalWarn = console.warn;
    console.warn = () => {};

    let loaded;
    try {
      const hydration = component.loadSourceFromUrl('/api/source-lines?request=REQ-A');
      component.header.party = 'customer-b';
      pendingRequest.resolve({ ok: false, statusText: 'Not found' });
      loaded = await hydration;
    } finally {
      console.warn = originalWarn;
    }
    assert.strictEqual(loaded, false);
    assert.strictEqual(component.sourceLoadError, '');
    assert.strictEqual(component.sourceHydrationPending, false);
    assert.strictEqual(component.loadingSource, false);
  });

  it('clears URL source errors when the target party changes', async function () {
    const originalWarn = console.warn;
    console.warn = () => {};
    globalThis.fetch = async () => ({ ok: false, statusText: 'Unavailable' });
    const create = loadTransactionForm();
    const component = create({
      formKey: 'sales.sales_quotation',
      initialSourceType: 'sales_request',
      initialHeader: { company: 'company-a', party_type: 'customer', party: 'customer-a' },
      items: [],
      uoms: [],
      defaultRows: 1,
    });
    const watchers = {};
    component.$watch = (expression, callback) => { watchers[expression] = callback; };
    component.init();

    try {
      await component.loadSourceFromUrl('/api/source-lines?request=REQ-A');
      assert.notStrictEqual(component.sourceLoadError, '');
      component.header.party = 'customer-b';
      watchers['header.party']();
    } finally {
      console.warn = originalWarn;
    }

    assert.strictEqual(component.sourceLoadError, '');
  });

  it('clears URL source errors when returning and retrying document lookup', async function () {
    const originalWarn = console.warn;
    console.warn = () => {};
    let component;
    try {
      globalThis.fetch = async () => ({ ok: false, statusText: 'Unavailable' });
      const create = loadTransactionForm();
      component = create({
        formKey: 'purchases.purchase_invoice',
        initialSourceType: 'purchase_order',
        initialHeader: { company: 'company-a', party_type: 'supplier', party: 'supplier-a' },
        items: [],
        uoms: [],
        defaultRows: 1,
      });
      component.init();
      await component.loadSourceFromUrl('/api/source-lines?order=PO-A');
      assert.notStrictEqual(component.sourceLoadError, '');

      component.showSourceDocuments();
      assert.strictEqual(component.sourceLoadError, '');
      globalThis.fetch = async () => ({
        ok: true,
        json: async () => ({ source_documents: [{ source_id: 'PO-A', source_type: 'purchase_order' }] }),
      });
      await component.fetchSourceDocuments();
    } finally {
      console.warn = originalWarn;
    }

    assert.deepStrictEqual(component.sourceDocuments.map((doc) => doc.source_id), ['PO-A']);
    assert.strictEqual(component.sourceLoadError, '');
  });

});
