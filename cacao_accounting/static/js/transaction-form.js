// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

(function () {
  let uidCounter = 0;

  function createUid() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    uidCounter += 1;
    return `transaction-line-${Date.now()}-${uidCounter}`;
  }

  function toNumber(value) {
    const parsed = Number.parseFloat(value || 0);
    if (Number.isNaN(parsed)) return 0;
    return parsed;
  }

  /** Serializa un valor financiero a cadena decimal limpia.
   *
   * Evita que representaciones IEEE 754 (ej. 0.020000000000000004)
   * lleguen al backend. Usa toFixed(9) — la escala máxima del sistema —
   * y elimina ceros finales para producir una cadena que
   * Decimal(str(value)) en el servidor procese sin perder precisión.
   */
  function toCurrencyString(value) {
    if (value === null || value === undefined || value === '') return '0';
    const str = typeof value === 'string' ? value.trim() : String(value);
    if (!str) return '0';
    const num = Number(str);
    if (Number.isNaN(num) || !Number.isFinite(num)) return '0';
    const formatted = num.toFixed(9).replace(/\.?0+$/, '') || '0';
    return formatted === '-0' ? '0' : formatted;
  }

  function normalizeAllowedUoms(source, fallback) {
    const values = Array.isArray(source) ? [...source] : [];
    if (!values.length && fallback) values.push(fallback);
    const seen = new Set();
    return values
      .map((value) => {
        if (!value) return '';
        if (typeof value === 'object') return value.code || value.value || value.id || '';
        return String(value);
      })
      .filter((value) => {
        if (!value || seen.has(value)) return false;
        seen.add(value);
        return true;
      });
  }

  function normalizeItems(items) {
    if (!Array.isArray(items)) return [];
    return items.map((item) => {
      const normalized = item || {};
      const defaultUom = normalized.uom || normalized.default_uom || '';
      return {
        ...normalized,
        code: normalized.code || normalized.value || '',
        name: normalized.name || normalized.item_name || normalized.label || '',
        default_uom: defaultUom,
        allowed_uoms: normalizeAllowedUoms(normalized.allowed_uoms || normalized.uoms, defaultUom),
      };
    });
  }

  function defaultTaxSummary() {
    return {
      subtotal: '0',
      document_tax_total: '0',
      capitalizable_tax_total: '0',
      separate_tax_total: '0',
      withholding_total: '0',
      grand_total: '0',
    };
  }

  const FISCAL_PREVIEW_DOCUMENT_TYPES = new Set([
    'purchase_request',
    'purchase_order',
    'purchase_receipt',
    'purchase_invoice',
    'sales_request',
    'sales_order',
    'delivery_note',
    'sales_invoice',
    'stock_entry',
    'payment_entry',
  ]);

  const LINE_IMPORT_DOCUMENT_TYPES = new Set([
    'purchase_request',
    'purchase_quotation',
    'supplier_quotation',
    'purchase_order',
    'purchase_receipt',
    'purchase_invoice',
    'sales_request',
    'sales_quotation',
    'sales_order',
    'delivery_note',
    'sales_invoice',
    'journal_entry',
    'bank_transaction',
    'stock_entry',
  ]);

  const OPERATIONAL_DOCUMENT_LABELS = {
    purchase_request: 'Solicitud de Compra',
    purchase_quotation: 'Solicitud de Cotización',
    supplier_quotation: 'Cotización de Proveedor',
    purchase_order: 'Orden de Compra',
    purchase_receipt: 'Recepción de Compra',
    purchase_invoice: 'Factura de Compra',
    sales_request: 'Pedido de Venta',
    sales_quotation: 'Cotización de Venta',
    sales_order: 'Orden de Venta',
    delivery_note: 'Nota de Entrega',
    sales_invoice: 'Factura de Venta',
    stock_entry: 'Movimiento de Inventario',
  };

  function normalizeAvailableSourceTypes(formKey, configuredTypes) {
    const documentType = String(formKey || '').split('.')[1] || '';
    const configured = Array.isArray(configuredTypes) ? [...configuredTypes] : [];
    if (!Object.hasOwn(OPERATIONAL_DOCUMENT_LABELS, documentType)) {
      return configured;
    }

    const sourceTypes = [{ value: documentType, label: OPERATIONAL_DOCUMENT_LABELS[documentType] }, ...configured];
    const seen = new Set();
    return sourceTypes.filter((sourceType) => {
      const value = sourceType?.value;
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function normalizeImportHeader(value) {
    let header = String(value || '').trim().toLowerCase();
    while (header.endsWith('*')) {
      header = header.slice(0, -1).trimEnd();
    }
    return header
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[_-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function findImportColumnIndex(headers, column) {
    const candidates = new Set([column.key, column.label, ...(Array.isArray(column.aliases) ? column.aliases : [])]
      .map((value) => normalizeImportHeader(value))
      .filter(Boolean));
    return headers.findIndex((header) => candidates.has(header));
  }

  function mapImportedRows(rawRows, schema) {
    if (!schema || !Array.isArray(schema.columns) || rawRows.length < 2) return [];

    const headers = (rawRows[0] || []).map((value) => normalizeImportHeader(value));
    const matchedIndexes = schema.columns.map((col) => findImportColumnIndex(headers, col));
    const hasHeaderMatches = matchedIndexes.some((index) => index >= 0);
    return rawRows
      .slice(1)
      .map((row) => {
        const obj = {};
        schema.columns.forEach((col, columnIndex) => {
          const foundIndex = matchedIndexes[columnIndex];
          let effectiveIndex;
          if (foundIndex >= 0) {
            effectiveIndex = foundIndex;
          } else if (!hasHeaderMatches) {
            effectiveIndex = columnIndex;
          } else {
            effectiveIndex = -1;
          }
          if (effectiveIndex >= 0) {
            obj[col.key] = row[effectiveIndex] === undefined ? '' : String(row[effectiveIndex]).trim();
          }
        });
        return obj;
      })
      .filter((row) => Object.values(row).some((val) => val !== null && val !== undefined && String(val).trim() !== ''));
  }

  function normalizeWorksheetValue(value) {
    if (value === null || value === undefined) return '';
    if (value instanceof Date) return value.toISOString().slice(0, 10);
    if (typeof value === 'object') {
      if (Array.isArray(value.richText)) {
        return value.richText.map((part) => part.text || '').join('');
      }
      if (value.text !== undefined) return String(value.text);
      if (value.result !== undefined) return normalizeWorksheetValue(value.result);
      if (value.hyperlink !== undefined) return String(value.text || value.hyperlink);
    }
    return String(value);
  }

  function worksheetToRows(worksheet) {
    if (!worksheet) return [];
    const rows = [];
    worksheet.eachRow({ includeEmpty: false }, (row) => {
      const values = [];
      for (let index = 1; index <= row.cellCount; index += 1) {
        values.push(normalizeWorksheetValue(row.getCell(index).value));
      }
      rows.push(values);
    });
    return rows;
  }

  function isItemSelected(doc) {
    return doc.selected;
  }

  function extractSourceId(doc) {
    return doc.source_id;
  }

  function mapColumnHeader(col) {
    return col.required ? `${col.label} *` : col.label;
  }

  function normalizeLineWithCb(ctx) {
    return function (line) {
      return ctx.normalizeLine(line);
    };
  }

  function matchItemCode(code) {
    return function (item) {
      return item.code === code;
    };
  }

  function splitTab(line) {
    return line.split("\t");
  }

  document.addEventListener('alpine:init', () => {
    Alpine.data('transactionForm', (config) => {
      const messages = {
        itemCode: 'Código del item',
        itemName: 'Descripción del item',
        uom: 'Unidad de medida',
        qty: 'Cantidad',
        rate: 'Precio / Costo Unitario',
        amount: 'Precio / Costo Total',
        ...config.messages
      };

      const defaultCols = [
        { field: 'item_code', label: 'Código', visible: true, width: 2, required: true },
        { field: 'item_name', label: 'Descripción', visible: true, width: 3, required: false },
        { field: 'uom', label: 'UOM', visible: true, width: 1, required: false },
        { field: 'qty', label: 'Cantidad', visible: true, width: 1, required: false },
        { field: 'rate', label: 'Precio', visible: true, width: 1, required: false },
        { field: 'discount_percentage', label: 'Descuento %', visible: config.enableLineDiscounts === true, width: 1, required: false },
        { field: 'amount', label: 'Monto', visible: true, width: 1, required: false },
        { field: 'batch_id', label: 'Lote', visible: false, width: 1, required: false },
        { field: 'serial_no', label: 'Serie', visible: false, width: 1, required: false },
      ];

      const configColumns = Array.isArray(config.columns) ? config.columns : [];

      const columnsList = [];
      for (const defCol of defaultCols) {
        const matchingConfig = configColumns.find(c => c.field === defCol.field);
        if (matchingConfig) {
          const merged = { ...defCol, ...matchingConfig };
          if (defCol.required) {
            merged.required = true;
            merged.visible = true;
          }
          columnsList.push(merged);
        } else {
          columnsList.push({ ...defCol });
        }
      }

      for (const confCol of configColumns) {
        if (!defaultCols.some(d => d.field === confCol.field)) {
          columnsList.push({ ...confCol });
        }
      }

      if (config.showPricing === false) {
        for (const column of columnsList) {
          if (column.field === 'rate' || column.field === 'amount') column.visible = false;
        }
      }

      if (config.enableBatchSerial === true) {
        for (const column of columnsList) {
          if (column.field === 'batch_id' || column.field === 'serial_no') column.visible = true;
        }
      }

      const flowLockedFields = Array.isArray(config.flowLockedFields)
        ? [...config.flowLockedFields]
        : [];
      if (!flowLockedFields.length && config.initialSourceType) {
        flowLockedFields.push('company', 'currency');
      }

      return {
        formKey: config.formKey || '',
        showPricing: config.showPricing !== false,
        canEditPrices: config.canEditPrices === true || !String(config.formKey || '').startsWith('sales.'),
        enableSalesPriceLookup: String(config.formKey || '').startsWith('sales.'),
        viewKey: config.viewKey || 'draft',
        flowLockedFields,
        messages,
        preferences: {
          columns: columnsList
        },
        get visibleColumns() {
          return (this.preferences?.columns || []).filter((column) => column.visible);
        },
        header: {
          company: '',
          naming_series: '',
          currency: '',
          posting_date: new Date().toISOString().slice(0, 10),
          party_type: '',
          party: '',
          party_label: '',
          warehouse: '',
          from_warehouse: '',
          to_warehouse: '',
          source_id: '',
          ...config.initialHeader
        },
        availableItems: normalizeItems(config.items),
        availableUoms: Array.isArray(config.uoms) ? [...config.uoms] : [],
        availableWarehouses: Array.isArray(config.warehouses) ? [...config.warehouses] : [],
        availableSourceTypes: normalizeAvailableSourceTypes(config.formKey, config.availableSourceTypes),
        searchCriteria: {
          source_type: config.initialSourceType || ''
        },
        autofillStep: 1,
        sourceDocuments: [],
        lines: [],
        sourceItems: [],
        loadingSource: false,
        sourceHydrationPending: false,
        sourceLoadError: '',
        submitError: '',
        activeIndex: null,
        modalLine: null,
        payload: '',
        importModal: {
          show: false,
          doctype: '',
          schema: null,
          pastedText: '',
          parsedRows: [],
          errors: [],
          validating: false,
          isValidated: false,
          fileLoading: false,
        },
        taxPreviewDebounceId: null,
        taxCharges: {
          loading: false,
          error: '',
          profile: null,
          summary: defaultTaxSummary(),
          lines: [],
          activeIndex: null,
          modalLine: null,
        },

        init() {
          if (this.$root?.addEventListener) {
            this.$root.addEventListener('submit', this.prepareSubmit.bind(this));
          }
          if (!this.header.party_type) {
            if (this.formKey.startsWith('sales.')) this.header.party_type = 'customer';
            if (this.formKey.startsWith('purchases.')) this.header.party_type = 'supplier';
          }
          this.lines = (config.initialLines || []).map(normalizeLineWithCb(this));
          if (!this.lines.length) this.addMultipleRows(config.defaultRows || 2);
          if (typeof this.$watch === 'function') {
            this.$watch('header.party', () => this.refreshCatalogPrices());
            this.$watch('header.company', () => this.refreshCatalogPrices());
            this.$watch('header.posting_date', () => this.refreshCatalogPrices());
          }
          this.queueTaxPreview();
        },

        isFlowFieldLocked(field) {
          return this.flowLockedFields.includes(field);
        },

        prepareSubmit(event) {
          this.submitError = '';
          this.syncLineInputs();
          if (this.sourceHydrationPending || this.loadingSource) {
            this.submitError = 'Espere a que termine la carga del documento origen.';
            event.preventDefault();
            return;
          }
          if (!this.header.currency) {
            this.submitError = 'La moneda transaccional es obligatoria.';
            event.preventDefault();
            return;
          }
          const requiresLines = Boolean(config.sourceApiUrl || config.requiresLines || config.initialSourceType);
          if (requiresLines && !this.lines.some((line) => String(line.item_code || '').trim())) {
            this.submitError = 'El documento requiere al menos una línea.';
            event.preventDefault();
          }
          for (const line of this.lines) {
            if (line.item_code && line.has_batch && !line.batch_id) {
              this.submitError = `El item ${line.item_code} requiere lote.`;
              event.preventDefault();
              return;
            }
            if (line.item_code && line.has_serial_no && !line.serial_no) {
              this.submitError = `El item ${line.item_code} requiere número de serie.`;
              event.preventDefault();
              return;
            }
          }
        },

        syncLineInputs() {
          const root = this.$root || document;
          const fields = ['item_code', 'item_name', 'uom', 'qty', 'rate', 'amount', 'warehouse',
            'batch_id', 'serial_no', 'account',
            'cost_center', 'unit', 'project', 'remarks', 'source_type', 'source_id', 'source_item_id'];
          const monetaryFields = new Set(['qty', 'rate', 'amount']);
          for (const [index, line] of this.lines.entries()) {
            for (const field of fields) {
              const input = root.querySelector(`[name="${field}_${index}"]`);
              if (!input) continue;
              const globalWarehouse = this.header.warehouse || this.header.from_warehouse || this.header.to_warehouse;
              const value = field === 'warehouse' && !line[field] ? globalWarehouse : line[field];
              const stringValue = monetaryFields.has(field) ? toCurrencyString(value) : String(value);
              input.value = value === undefined || value === null ? '' : stringValue;
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
        },

        get defaultColumns() {
          return [
            { field: 'item_code', label: this.messages.itemCode, width: 2 },
            { field: 'item_name', label: this.messages.itemName, width: 3 },
            { field: 'uom', label: this.messages.uom, width: 1 },
            { field: 'qty', label: this.messages.qty, width: 1 },
            { field: 'rate', label: this.messages.rate, width: 1 },
            { field: 'amount', label: this.messages.amount, width: 1 },
          ];
        },

        get totalAmount() {
          return this._sumLineAmounts(this.lines);
        },

        _sumLineAmounts(lines) {
          let total = 0;
          for (const line of lines) {
            total += toNumber(line.amount);
          }
          return total;
        },

        get documentTaxTotal() {
          return toNumber(this.taxCharges.summary.document_tax_total);
        },

        get grandTotal() {
          return this.totalAmount + this.documentTaxTotal;
        },

        newLine() {
          return {
            uid: createUid(),
            item_code: '',
            item_name: '',
            qty: 1,
            uom: '',
            rate: 0,
            discount_percentage: 0,
            amount: 0,
            warehouse: '',
            batch_id: '',
            serial_no: '',
            has_batch: false,
            has_serial_no: false,
            has_expiry_date: false,
            batch_no: '',
            account: '',
            cost_center: '',
            unit: '',
            project: '',
            remarks: '',
            source_type: '',
            source_id: '',
            source_item_id: '',
            allowed_uoms: [],
            ...config.linePrototype
          };
        },

        normalizeLine(line) {
          const base = this.newLine();
          const normalized = { ...base, ...line };
          normalized.uid = normalized.uid || base.uid;
          normalized.allowed_uoms = normalizeAllowedUoms(normalized.allowed_uoms, normalized.uom);
          this.calcAmount(normalized);
          this.syncLineFromItem(normalized, Boolean(normalized.item_name));
          return normalized;
        },

        findItem(itemCode) {
          return this.availableItems.find(matchItemCode(itemCode)) || null;
        },

        getLineUoms(line) {
          const item = this.findItem(line.item_code);
          const allowed = normalizeAllowedUoms(
            item?.allowed_uoms || line.allowed_uoms,
            item?.default_uom || line.uom
          );
          if (!allowed.length) {
            return [...this.availableUoms];
          }
          return this.mapAllowedUomCodes(allowed);
        },

        mapAllowedUomCodes(allowed) {
          const result = [];
          for (const code of allowed) {
            const uom = this._findUomByCode(code);
            result.push(uom || { code, name: code });
          }
          return result;
        },

        _findUomByCode(code) {
          for (const uom of this.availableUoms) {
            if (uom.code === code) return uom;
          }
          return undefined;
        },

        syncLineFromItem(line, keepCustomName) {
          const item = this.findItem(line.item_code);
          if (!item) {
            line.allowed_uoms = normalizeAllowedUoms(line.allowed_uoms, line.uom);
            return;
          }
          if (!keepCustomName || !line.item_name) {
            line.item_name = item.name || line.item_name;
          }
          this._applyItemUom(line, item);
          line.has_batch = item.has_batch || false;
          line.has_serial_no = item.has_serial_no || false;
          line.has_expiry_date = item.has_expiry_date || false;
          if (!keepCustomName) {
            line.batch_id = '';
            line.serial_no = '';
            line.batch_no = '';
          }
        },

        _applyItemUom(line, item) {
          line.allowed_uoms = normalizeAllowedUoms(item.allowed_uoms, item.default_uom);
          const allowedUomSet = new Set(line.allowed_uoms);
          if (line.allowed_uoms.length && !allowedUomSet.has(line.uom)) {
            line.uom = line.allowed_uoms[0];
          }
          if (!line.uom && item.default_uom) line.uom = item.default_uom;
        },

        onItemChange(line) {
          this.syncLineFromItem(line, false);
          this.calcAmount(line);
          this.refreshCatalogPrice(line);
        },

        async refreshCatalogPrice(line) {
          if (!this.enableSalesPriceLookup || line.source_item_id || !line.item_code || !this.header.company) return;
          const itemCode = line.item_code;
          const params = new URLSearchParams({
            company: this.header.company,
            customer_id: this.header.party || '',
            item_code: itemCode,
            qty: toCurrencyString(line.qty || 1),
            uom: line.uom || '',
            posting_date: this.header.posting_date || '',
          });
          try {
            const response = await fetch(`/api/sales/catalog-price?${params.toString()}`, { credentials: 'same-origin' });
            const payload = await response.json();
            if (!response.ok || line.item_code !== itemCode || payload.price === null) return;
            line.rate = toNumber(payload.price);
            line.price_list_name = payload.price_list_name || '';
            this.calcAmount(line);
          } catch (err) {
            console.warn('transactionForm catalog price lookup failed', err);
          }
        },

        refreshCatalogPrices() {
          for (const line of this.lines) this.refreshCatalogPrice(line);
        },

        addRow() {
          this.lines.push(this.newLine());
          this.queueTaxPreview();
        },

        addMultipleRows(count) {
          for (let index = 0; index < count; index += 1) this.addRow();
        },

        insertRow(index, direction) {
          const target = direction < 0 ? index : index + 1;
          this.lines.splice(target, 0, this.newLine());
          this.queueTaxPreview();
        },

        moveRow(index, direction) {
          const target = index + direction;
          if (target < 0 || target >= this.lines.length) return;
          const current = this.lines[index];
          this.lines[index] = this.lines[target];
          this.lines[target] = current;
          this.queueTaxPreview();
        },

        duplicateRow(index) {
          const copy = this.normalizeLine(this.lines[index]);
          copy.uid = createUid();
          this.lines.splice(index + 1, 0, copy);
          this.queueTaxPreview();
        },

        removeRow(index) {
          if (this.lines.length === 1) {
            this.lines[index] = this.newLine();
            this.queueTaxPreview();
            return;
          }
          this.lines.splice(index, 1);
          this.queueTaxPreview();
        },

        calcAmount(line) {
          const gross = toNumber(line.qty) * toNumber(line.rate);
          line.amount = gross * (1 - (toNumber(line.discount_percentage) / 100));
          this.queueTaxPreview();
        },

        openDetails(index) {
          this.activeIndex = index;
          this.modalLine = this.normalizeLine(this.lines[index]);
          const modalEl = document.getElementById('lineDetailModal');
          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
        },

        saveModalLine() {
          if (this.activeIndex !== null && this.modalLine) {
            this.calcAmount(this.modalLine);
            this.lines[this.activeIndex] = this.normalizeLine(this.modalLine);
          }
          const modalEl = document.getElementById('lineDetailModal');
          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          this.queueTaxPreview();
        },

        documentType() {
          if (config.documentType) return config.documentType;
          const chunks = (this.formKey || '').split('.');
          return chunks.length > 1 ? chunks[1] : '';
        },

        supportsFiscalPreview() {
          if (config.enableFiscalPreview === false) return false;
          return FISCAL_PREVIEW_DOCUMENT_TYPES.has(this.documentType());
        },

        supportsLineImport() {
          return LINE_IMPORT_DOCUMENT_TYPES.has(this.documentType());
        },

        buildFiscalPayload() {
          return {
            document_type: this.documentType(),
            company: this.header.company || '',
            currency: this.header.currency || '',
            posting_date: this.header.posting_date || '',
            party_type: this.header.party_type || '',
            party_id: this.header.party || '',
            purpose: this.header.purpose || '',
            payment_type: this.header.payment_type || '',
            lines: this.mapLinesToPayload(),
            tax_lines: this.mapTaxLinesToPayload(),
          };
        },

        mapLinesToPayload() {
          const result = [];
          for (const line of this.lines) {
            result.push(this._serializeLine(line));
          }
          return result;
        },

        _serializeLine(line) {
          return {
            uid: line.uid || '',
            item_code: line.item_code || '',
            item_name: line.item_name || '',
            qty: toCurrencyString(line.qty),
            uom: line.uom || '',
            rate: toCurrencyString(line.rate),
            amount: toCurrencyString(line.amount),
            batch_id: line.batch_id || '',
            serial_no: line.serial_no || '',
          };
        },

        mapTaxLinesToPayload() {
          const result = [];
          for (const line of this.taxCharges.lines) {
            result.push(this._serializeTaxLine(line));
          }
          return result;
        },

        _serializeTaxLine(line) {
          this.syncTaxTreatment(line);
          const accountingTreatment = line.accounting_treatment || 'separate_tax_account';
          return {
            source_rule_id: line.source_rule_id || '',
            manual: Boolean(line.manual),
            concept: line.concept || '',
            type: line.type || 'tax',
            calculation_method: line.calculation_method || 'percentage',
            base_mode: line.base_mode || 'goods',
            include_concepts: line.include_concepts || [],
            exclude_concepts: line.exclude_concepts || [],
            rate: toCurrencyString(line.rate),
            amount: toCurrencyString(line.amount),
            accounting_treatment: accountingTreatment,
            allocation_method: line.allocation_method || '',
            affects_inventory: accountingTreatment === 'capitalizable_inventory_cost',
            affects_document_total: Boolean(line.affects_document_total),
            included_in_price: Boolean(line.included_in_price),
            account_id: line.account_id || '',
            notes: line.notes || '',
          };
        },

        queueTaxPreview() {
          if (!this.supportsFiscalPreview()) return;
          const hasWindowTimers = typeof globalThis !== 'undefined' &&
            typeof globalThis.setTimeout === 'function' &&
            typeof globalThis.clearTimeout === 'function';
          if (!hasWindowTimers) return;
          if (this.taxPreviewDebounceId) {
            globalThis.clearTimeout(this.taxPreviewDebounceId);
          }
          this.taxPreviewDebounceId = globalThis.setTimeout(this.executeTaxPreview.bind(this), 250);
        },

        executeTaxPreview() {
          this.fetchTaxPreview();
        },

        async fetchTaxPreview() {
          if (!this.supportsFiscalPreview()) {
            this.taxCharges.loading = false;
            this.taxCharges.error = '';
            return;
          }
          if (!this.header.company) return;
          this.taxCharges.loading = true;
          this.taxCharges.error = '';
          await this._executeTaxPreviewRequest();
        },

        async _executeTaxPreviewRequest() {
          try {
            const response = await this.requestTaxPreview();
            const data = await response.json();
            if (!response.ok) {
              this.taxCharges.error = data?.message || 'No se pudo calcular.';
              this.taxCharges.loading = false;
              return;
            }
            this.applyTaxPreviewData(data);
          } catch (err) {
            this.handleTaxPreviewError(err);
          }
        },

        handleTaxPreviewError(err) {
          console.warn('transactionForm tax preview failed', err);
          this.taxCharges.error = 'No se pudo calcular.';
          this.taxCharges.loading = false;
        },

        async requestTaxPreview() {
          const csrfInput = document.querySelector('input[name="csrf_token"]');
          const csrfToken = csrfInput ? csrfInput.value : '';
          return fetch('/api/fiscal/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            credentials: 'same-origin',
            body: JSON.stringify(this.buildFiscalPayload()),
          });
        },

        applyTaxPreviewData(data) {
          this.taxCharges.profile = data.profile || null;
          this.taxCharges.summary = data.summary || this.taxCharges.summary;
          this.taxCharges.lines = Array.isArray(data.tax_lines) ? data.tax_lines : [];
          this.taxCharges.loading = false;
        },

	        openTaxLineDetails(index) {
	          this.taxCharges.activeIndex = index;
	          this.taxCharges.modalLine = this.normalizeTaxLine(this.taxCharges.lines[index] || {});
	          const modalEl = document.getElementById('taxChargeDetailModal');
	          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
	        },

	        saveTaxLineModal() {
	          if (this.taxCharges.activeIndex !== null && this.taxCharges.modalLine) {
	            this.syncTaxTreatment(this.taxCharges.modalLine);
	            if (this.taxCharges.modalLine.manual) {
	              this.calcTaxLine(this.taxCharges.modalLine);
	            }
	            this.taxCharges.lines[this.taxCharges.activeIndex] = this.normalizeTaxLine(this.taxCharges.modalLine);
	            this.recalculateTaxSummary();
	          }
	          const modalEl = document.getElementById('taxChargeDetailModal');
	          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
	        },

	        newTaxLine() {
	          return {
	            line_id: createUid(),
	            source_rule_id: `MANUAL-${createUid()}`,
	            manual: true,
	            concept: 'Cargo manual',
	            type: 'charge',
	            calculation_method: 'manual',
	            base_mode: 'goods',
	            base_amount: this.totalAmount,
	            rate: 0,
	            amount: 0,
	            accounting_treatment: 'separate_tax_account',
	            allocation_method: 'by_value',
	            affects_inventory: false,
	            affects_document_total: true,
	            included_in_price: false,
	            account_id: '',
	            notes: '',
	          };
	        },

	        normalizeTaxLine(line) {
	          const normalized = { ...this.newTaxLine(), ...line };
	          normalized.manual = Boolean(normalized.manual || String(normalized.source_rule_id || '').startsWith('MANUAL-'));
	          this.syncTaxTreatment(normalized);
	          if (normalized.manual) {
	            this.calcTaxLine(normalized);
	          }
	          return normalized;
	        },

	        syncTaxTreatment(line) {
	          if (!line) return;

	          line.affects_inventory = line.accounting_treatment === 'capitalizable_inventory_cost';
	        },

	        addTaxLine() {
	          const line = this.newTaxLine();
	          this.taxCharges.lines.push(line);
	          this.taxCharges.activeIndex = this.taxCharges.lines.length - 1;
	          this.taxCharges.modalLine = { ...line };
	          this.recalculateTaxSummary();
	          const modalEl = document.getElementById('taxChargeDetailModal');
	          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
	        },

	        removeTaxLine(index) {
	          this.taxCharges.lines.splice(index, 1);
	          this.recalculateTaxSummary();
	        },

        calcTaxLine(line) {
          line.base_amount = toNumber(line.base_amount || this.totalAmount);
          line.rate = toNumber(line.rate);
          line.amount = this.calculateTaxAmount(line);
        },

        calculateTaxAmount(line) {
          if (line.calculation_method === 'percentage') {
            return line.base_amount * line.rate / 100;
          }
          return toNumber(line.amount);
        },

        recalculateTaxSummary() {
          const summary = defaultTaxSummary();
          const lines = this.taxCharges.lines || [];
          const documentTaxTotal = this.calcDocumentTaxTotal(lines);
          const capitalizableTaxTotal = this.calcCapitalizableTaxTotal(lines);
          const separateTaxTotal = this.calcSeparateTaxTotal(lines);
          const withholdingTotal = this.calcWithholdingTotal(lines);
          summary.subtotal = toCurrencyString(this.totalAmount);
          summary.document_tax_total = toCurrencyString(documentTaxTotal);
          summary.capitalizable_tax_total = toCurrencyString(capitalizableTaxTotal);
          summary.separate_tax_total = toCurrencyString(separateTaxTotal);
          summary.withholding_total = toCurrencyString(withholdingTotal);
          summary.grand_total = toCurrencyString(this.totalAmount + documentTaxTotal);
          this.taxCharges.summary = summary;
        },

        calcDocumentTaxTotal(lines) {
          return this._sumLinesByTaxType(lines, 'affects');
        },

        _sumLinesByTaxType(lines, taxType) {
          let total = 0;
          for (const line of lines) {
            let amount = 0;
            if (taxType === 'affects') {
              amount = this._taxAmountIfAffects(line);
            } else if (taxType === 'capitalizable') {
              amount = this._taxAmountIfCapitalizable(line);
            } else if (taxType === 'separate') {
              amount = this._taxAmountIfSeparate(line);
            } else if (taxType === 'withholding') {
              amount = this._taxAmountIfWithholding(line);
            }
            total += amount;
          }
          return total;
        },

        _taxAmountIfAffects(line) {
          const isWithholding = line.type === 'withholding';
          const isIncludedInPrice = line.included_in_price;
          const notAffectsTotal = line.affects_document_total === false;
          if (isWithholding || isIncludedInPrice || notAffectsTotal) return 0;
          return toNumber(line.amount);
        },

        calcCapitalizableTaxTotal(lines) {
          return this._sumLinesByTaxType(lines, 'capitalizable');
        },

        _taxAmountIfCapitalizable(line) {
          const isCapitalizable = line.accounting_treatment === 'capitalizable_inventory_cost';
          if (!isCapitalizable) return 0;
          return toNumber(line.amount);
        },

        calcSeparateTaxTotal(lines) {
          return this._sumLinesByTaxType(lines, 'separate');
        },

        _taxAmountIfSeparate(line) {
          const isSeparate = line.accounting_treatment === 'separate_tax_account';
          if (!isSeparate) return 0;
          return toNumber(line.amount);
        },

        calcWithholdingTotal(lines) {
          return this._sumLinesByTaxType(lines, 'withholding');
        },

        _taxAmountIfWithholding(line) {
          const isWithholding = line.type === 'withholding';
          if (!isWithholding) return 0;
          return toNumber(line.amount);
        },

	        async fetchSource(apiUrl) {
          if (apiUrl) {
            await this.loadSourceFromUrl(apiUrl);
          } else {
            this.autofillStep = 1;
            this.fetchSourceDocuments();
          }
        },

        async loadSourceFromUrl(apiUrl) {
          this.sourceHydrationPending = true;
          this.loadingSource = true;
          this.sourceLoadError = '';
          this.autofillStep = 2;
          try {
            const response = await fetch(apiUrl, { credentials: 'same-origin' });
            if (!response.ok) throw new Error(response.statusText || 'source request failed');
            const data = await response.json();
            this.sourceItems = this.mapSourceItems(data.items);
            this.loadingSource = false;
          } catch (err) {
            console.warn('Error al obtener source lines:', err);
            this.loadingSource = false;
            this.sourceLoadError = 'No se pudieron cargar las líneas del documento origen.';
          } finally {
            this.sourceHydrationPending = false;
          }
        },

        mapSourceItems(rawItems) {
          const items = rawItems || [];
          const result = [];
          for (const item of items) {
            result.push({ ...item, selected: true });
          }
          return result;
        },

        async fetchSourceDocuments() {
          const params = new URLSearchParams();
          params.append('target_type', this.formKey.split('.')[1]);
          params.append('company', this.header.company);
          params.append('party_type', this.header.party_type);
          params.append('party_id', this.header.party);

          this.loadingSource = true;
          try {
            const response = await fetch(`/api/document-flow/source-documents?${params.toString()}`, { credentials: 'same-origin' });
            const data = await response.json();
            this.sourceDocuments = this.processSourceDocuments(data.source_documents);
            this.loadingSource = false;
          } catch (err) {
            console.warn('Error al obtener source documents:', err);
            this.loadingSource = false;
          }
        },

        processSourceDocuments(rawDocs) {
          const docs = rawDocs || [];
          const result = [];
          const sourceType = this.searchCriteria.source_type;
          for (const doc of docs) {
            if (!sourceType || doc.source_type === sourceType) {
              result.push({ ...doc, selected: false });
            }
          }
          return result;
        },

        async fetchSourceItems() {
          const selectedIds = this.sourceDocuments.filter(isItemSelected).map(extractSourceId);
          if (!selectedIds.length) return;

          const params = this.buildSourceItemsParams(selectedIds);
          this.loadingSource = true;
          this.autofillStep = 2;
          try {
            const response = await fetch(`/api/document-flow/pending-lines?${params.toString()}`, { credentials: 'same-origin' });
            const data = await response.json();
            this.sourceItems = this.mapSourceItems(data.items);
            this.loadingSource = false;
          } catch (err) {
            console.warn('Error al obtener source items:', err);
            this.loadingSource = false;
          }
        },

        buildSourceItemsParams(selectedIds) {
          const params = new URLSearchParams();
          params.append('source_type', this.searchCriteria.source_type);
          params.append('target_type', this.formKey.split('.')[1]);
          params.append('company', this.header.company);
          for (const id of selectedIds) {
            params.append('source_id', id);
          }
          return params;
        },

        applySource() {
          this.processSelectedSourceItems();
          this.cleanupEmptyLines();
          if (!this.lines.length) this.addRow();
          this.queueTaxPreview();
        },

        processSelectedSourceItems() {
          for (const item of this.sourceItems) {
            if (item.selected) this.addSourceItemAsLine(item);
          }
        },

        addSourceItemAsLine(item) {
          if (this.lineAlreadyExists(item)) return;
          const line = this.createLineFromSourceItem(item);
          this.lines.push(line);
        },

        lineAlreadyExists(item) {
          return this._hasMatchingSourceLine(this.lines, item);
        },

        _hasMatchingSourceLine(lines, item) {
          for (const line of lines) {
            if (
              line.source_type === item.source_type &&
              line.source_id === item.source_id &&
              line.source_item_id === item.source_item_id
            ) return true;
          }
          return false;
        },

        createLineFromSourceItem(item) {
          const line = this.newLine();
          line.item_code = item.item_code || '';
          line.item_name = item.item_name || '';
          line.qty = this.normalizeSourceQty(item);
          line.uom = item.uom || '';
          line.rate = toNumber(item.rate || 0);
          line.source_type = item.source_type || '';
          line.source_id = item.source_id || '';
          line.source_document_no = item.source_document_no || '';
          line.source_item_id = item.source_item_id || '';
          this.syncLineFromItem(line, false);
          this.calcAmount(line);
          return line;
        },

        normalizeSourceQty(item) {
          const qty = item.qty;
          if (qty !== null && qty !== undefined && qty !== '') return toNumber(qty);
          return toNumber(item.pending_qty || 0);
        },

        cleanupEmptyLines() {
          const filtered = [];
          for (const line of this.lines) {
            if (line.item_code || line.item_name || line.source_id) {
              filtered.push(line);
            }
          }
          this.lines = filtered;
        },

        formatMoney(value) {
          return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        },

        serializedTaxLines() {
          return JSON.stringify(
            (this.taxCharges.lines || []).map((line) => ({
              ...line,
              base_amount: toCurrencyString(line.base_amount),
              rate: toCurrencyString(line.rate),
              amount: toCurrencyString(line.amount),
            }))
          );
        },

        serializedTaxSummary() {
          return JSON.stringify(this.taxCharges.summary || {});
        },

        async openImportModal() {
          if (!this.supportsLineImport()) return;
          this.importModal.doctype = this.documentType();
          this.importModal.schema = null;
          this.importModal.pastedText = "";
          this.importModal.parsedRows = [];
          this.importModal.errors = [];
          this.importModal.isValidated = false;

          try {
            const response = await fetch(
              `/api/line-import/schema?doctype=${this.importModal.doctype}`,
              { credentials: "same-origin" }
            );
            const payload = await response.json();
            if (response.ok) {
              this.importModal.schema = payload;
            } else {
              this.importModal.schema = { columns: [] };
              this.importModal.errors = [{ message: payload.error || "No se pudo cargar la plantilla de importación." }];
            }
          } catch (err) {
            console.error("Error fetching import schema:", err);
            this.importModal.schema = { columns: [] };
            this.importModal.errors = [{ message: "No se pudo cargar la plantilla de importación." }];
          } finally {
            const modalEl = document.getElementById("modalImportLines");
            if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
          }
        },

        onPasteAreaInput() {
          this.importModal.isValidated = false;
          this.parsePastedText();
        },

        parsePastedText() {
          const text = this.importModal.pastedText.trim();
          if (!text) {
            this.importModal.parsedRows = [];
            return;
          }

          const lines = text.split(/\r?\n/);
          const rows = lines.map(splitTab);
          this.importModal.parsedRows = mapImportedRows(rows, this.importModal.schema);
        },

        async validateImport() {
          this.importModal.validating = true;
          this.importModal.errors = [];

          const csrfInput = document.querySelector('input[name="csrf_token"]');
          const csrfToken = csrfInput ? csrfInput.value : "";

          try {
            const response = await fetch("/api/line-import/validate", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
              },
              credentials: "same-origin",
              body: JSON.stringify({
                doctype: this.importModal.doctype,
                context: {
                  company_id: this.header.company,
                  currency_id: this.header.currency,
                },
                rows: this.importModal.parsedRows,
              }),
            });

            const data = await response.json();
            if (response.ok && data.valid) {
              this.importModal.isValidated = true;
              this.importModal.parsedRows = data.rows;
            } else {
              this.importModal.errors = data.errors || [{ message: data.error || "No se pudo validar." }];
              this.importModal.isValidated = false;
            }
          } catch (err) {
            this.handleImportValidationError(err);
          } finally {
            this.importModal.validating = false;
          }
        },

        handleImportValidationError(err) {
          console.warn('transactionForm import validation failed', err);
          this.importModal.errors = [
            { message: "Error de conexión al validar." },
          ];
        },

        insertImportedLines() {
          if (!this.importModal.isValidated) return;

          // Safer placeholder clearing: if grid has only one empty row, clear it before appending
          if (
            this.lines.length === 1 &&
            !this.lines[0].item_code &&
            !this.lines[0].account &&
            !this.lines[0].item_name &&
            !this.lines[0].source_id
          ) {
            this.lines = [];
          }

          // Append-only behavior: push to existing lines
          for (const row of this.importModal.parsedRows) {
            this._processImportedRow(row);
          }

          if (!this.lines.length) this.addRow();

          const modalEl = document.getElementById("modalImportLines");
          if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          this.queueTaxPreview();
        },

        _processImportedRow(row) {
          const line = this.newLine();
          for (const key of Object.keys(row)) {
            this._assignRowKeyToLine(line, row, key);
          }

          // Handle specific mappings
          if (row.quantity !== undefined) line.qty = toNumber(row.quantity);
          if (row.rate !== undefined) line.rate = toNumber(row.rate);
          if (row.account !== undefined) line.account = row.account;

          // Journal Entry specific mapping for debit/credit into value/rate
          if (this.importModal.doctype === "journal_entry") {
            this._applyJournalEntryDebitCredit(line, row);
          }

          if (line.item_code) {
            this.syncLineFromItem(line, true);
          }
          this.calcAmount(line);
          this.lines.push(line);
        },

        _assignRowKeyToLine(line, row, key) {
          if (key in line || key === "item_id") {
            line[key] = row[key];
          }
        },

        _applyJournalEntryDebitCredit(line, row) {
          const dr = toNumber(row.debit);
          const cr = toNumber(row.credit);
          if (dr > 0) {
            line.rate = dr;
            line.qty = 1;
            line.debit = dr;
            line.credit = 0;
          } else if (cr > 0) {
            line.rate = -cr;
            line.qty = 1;
            line.debit = 0;
            line.credit = cr;
          }
        },

        async downloadTemplate() {
          if (!this.importModal.schema) return;
          const headers = this.importModal.schema.columns.map(mapColumnHeader);
          const workbook = new ExcelJS.Workbook();
          const worksheet = workbook.addWorksheet("Plantilla");
          worksheet.addRow(headers);
          const buffer = await workbook.xlsx.writeBuffer();
          const blob = new Blob(
            [buffer],
            { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }
          );
          const url = globalThis.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${this.importModal.doctype}_template.xlsx`;
          link.click();
          globalThis.URL.revokeObjectURL(url);
        },

        async handleFileUpload(event) {
          const file = event.target.files[0];
          if (!file) return;
          if (!/\.xlsx$/i.test(file.name || '')) {
            this.importModal.errors = [{ message: "Solo se permiten archivos .xlsx." }];
            this.importModal.parsedRows = [];
            event.target.value = '';
            return;
          }

          this.importModal.fileLoading = true;
          this.importModal.isValidated = false;
          this.importModal.errors = [];

          try {
            const workbook = new ExcelJS.Workbook();
            await workbook.xlsx.load(await file.arrayBuffer());
            this.importModal.parsedRows = mapImportedRows(worksheetToRows(workbook.worksheets[0]), this.importModal.schema);
          } catch (err) {
            console.error("Error processing XLSX:", err);
            this.importModal.errors = [{ message: "Error al procesar el archivo XLSX." }];
          } finally {
            this.importModal.fileLoading = false;
          }
        },
      };
    });
  });
}());
