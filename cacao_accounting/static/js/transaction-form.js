// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose MORENO Reyes

(function () {
  let uidCounter = 0;

  function createUid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    uidCounter += 1;
    return `transaction-line-${Date.now()}-${uidCounter}`;
  }

  function toNumber(value) {
    const parsed = parseFloat(value || 0);
    if (Number.isNaN(parsed)) return 0;
    return parsed;
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

  function defaultColumns(messages) {
    return [
      { field: 'item_code', label: messages.itemCode || 'Código del item', width: 2, visible: true, required: true },
      { field: 'item_name', label: messages.itemName || 'Descripción del item', width: 3, visible: true, required: true },
      { field: 'uom', label: messages.uom || 'Unidad de medida', width: 2, visible: true, required: true },
      { field: 'qty', label: messages.qty || 'Cantidad', width: 1, visible: true, required: true },
      { field: 'rate', label: messages.rate || 'Precio / Costo Unitario', width: 2, visible: true, required: true },
      { field: 'amount', label: messages.amount || 'Precio / Costo Total', width: 2, visible: true, required: true },
    ];
  }

  function normalizeColumns(columns, messages) {
    const baseColumns = defaultColumns(messages);
    const normalized = Array.isArray(columns) ? columns
      .filter((column) => column && column.field)
      .map((column) => {
        return {
          field: String(column.field),
          label: column.label || String(column.field),
          width: Math.min(Math.max(parseInt(column.width || 1, 10), 1), 4),
          visible: column.visible !== false,
          required: Boolean(column.required),
        };
      }) : [];

    if (!normalized.length) return baseColumns;

    baseColumns.forEach((requiredColumn) => {
      const existing = normalized.find((column) => column.field === requiredColumn.field);
      if (existing) {
        existing.label = existing.label || requiredColumn.label;
        existing.width = existing.width || requiredColumn.width;
        existing.visible = true;
        existing.required = true;
        return;
      }
      normalized.push(requiredColumn);
    });

    return normalized;
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
      let effectivePreferences = config.initialPreferences;
      if (!effectivePreferences || !Array.isArray(effectivePreferences.columns)) {
        effectivePreferences = { columns: config.columns || [] };
      }

      return {
        formKey: config.formKey || '',
        viewKey: config.viewKey || 'draft',
        preferences: { columns: normalizeColumns(effectivePreferences.columns, messages) },
        messages,
        header: {
          company: '',
          naming_series: '',
          currency: '',
          posting_date: new Date().toISOString().slice(0, 10),
          party_type: '',
          party: '',
          party_label: '',
          source_id: '',
          ...config.initialHeader
        },
        availableItems: normalizeItems(config.items),
        availableUoms: Array.isArray(config.uoms) ? [...config.uoms] : [],
        availableWarehouses: Array.isArray(config.warehouses) ? [...config.warehouses] : [],
        availableSourceTypes: Array.isArray(config.availableSourceTypes) ? config.availableSourceTypes : [],
        searchCriteria: {
          source_type: config.initialSourceType || ''
        },
        autofillStep: 1,
        sourceDocuments: [],
        lines: [],
        sourceItems: [],
        loadingSource: false,
        activeIndex: null,
        modalLine: null,
        payload: '',

        init() {
          if (!this.header.party_type) {
            if (this.formKey.startsWith('sales.')) this.header.party_type = 'customer';
            if (this.formKey.startsWith('purchases.')) this.header.party_type = 'supplier';
          }
          this.lines = (config.initialLines || []).map((line) => {
            return this.normalizeLine(line);
          });
          if (!this.lines.length) this.addMultipleRows(config.defaultRows || 2);
        },

        get visibleColumns() {
          return (this.preferences.columns || []).filter((column) => {
            return column.visible !== false;
          });
        },

        get totalAmount() {
          return this.lines.reduce((total, line) => {
            return total + toNumber(line.amount);
          }, 0);
        },

        newLine() {
          return {
            uid: createUid(),
            item_code: '',
            item_name: '',
            qty: 1,
            uom: '',
            rate: 0,
            amount: 0,
            warehouse: '',
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
          const normalized = { ...base, ...(line || {}) };
          normalized.uid = normalized.uid || base.uid;
          normalized.allowed_uoms = normalizeAllowedUoms(normalized.allowed_uoms, normalized.uom);
          this.calcAmount(normalized);
          this.syncLineFromItem(normalized, Boolean(normalized.item_name));
          return normalized;
        },

        findItem(itemCode) {
          return this.availableItems.find((item) => {
            return item.code === itemCode;
          }) || null;
        },

        getLineUoms(line) {
          const item = this.findItem(line.item_code);
          const allowed = normalizeAllowedUoms(
            (item && item.allowed_uoms) || line.allowed_uoms,
            (item && item.default_uom) || line.uom
          );
          if (!allowed.length) {
            return [...this.availableUoms];
          }
          return allowed.map((code) => {
            return this.availableUoms.find((uom) => uom.code === code) || { code: code, name: code };
          });
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
          line.allowed_uoms = normalizeAllowedUoms(item.allowed_uoms, item.default_uom);
          if (line.allowed_uoms.length && line.allowed_uoms.indexOf(line.uom) === -1) {
            line.uom = line.allowed_uoms[0];
          }
          if (!line.uom && item.default_uom) line.uom = item.default_uom;
        },

        onItemChange(line) {
          this.syncLineFromItem(line, false);
          this.calcAmount(line);
        },

        addRow() {
          this.lines.push(this.newLine());
        },

        addMultipleRows(count) {
          for (let index = 0; index < count; index += 1) this.addRow();
        },

        insertRow(index, direction) {
          const target = direction < 0 ? index : index + 1;
          this.lines.splice(target, 0, this.newLine());
        },

        moveRow(index, direction) {
          const target = index + direction;
          if (target < 0 || target >= this.lines.length) return;
          const current = this.lines[index];
          this.lines[index] = this.lines[target];
          this.lines[target] = current;
        },

        duplicateRow(index) {
          const copy = this.normalizeLine(this.lines[index]);
          copy.uid = createUid();
          this.lines.splice(index + 1, 0, copy);
        },

        removeRow(index) {
          if (this.lines.length === 1) {
            this.lines[index] = this.newLine();
            return;
          }
          this.lines.splice(index, 1);
        },

        calcAmount(line) {
          line.amount = toNumber(line.qty) * toNumber(line.rate);
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
        },

        async fetchSource(apiUrl) {
          if (apiUrl) {
            this.loadingSource = true;
            this.autofillStep = 2;
            try {
              const response = await fetch(apiUrl, { credentials: 'same-origin' });
              const data = await response.json();
              this.sourceItems = (data.items || []).map((item) => {
                return { ...item, selected: true };
              });
              this.loadingSource = false;
            } catch (err) {
              this.loadingSource = false;
            }
          } else {
            this.autofillStep = 1;
            this.fetchSourceDocuments();
          }
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
            const sourceType = this.searchCriteria.source_type;
            this.sourceDocuments = (data.source_documents || [])
              .filter((doc) => !sourceType || doc.source_type === sourceType)
              .map((doc) => { return { ...doc, selected: false }; });
            this.loadingSource = false;
          } catch (err) {
            this.loadingSource = false;
          }
        },

        async fetchSourceItems() {
          const selectedIds = this.sourceDocuments.filter((d) => d.selected).map((d) => d.source_id);
          if (!selectedIds.length) return;

          const params = new URLSearchParams();
          params.append('source_type', this.searchCriteria.source_type);
          params.append('target_type', this.formKey.split('.')[1]);
          params.append('company', this.header.company);
          selectedIds.forEach((id) => { params.append('source_id', id); });

          this.loadingSource = true;
          this.autofillStep = 2;
          try {
            const response = await fetch(`/api/document-flow/pending-lines?${params.toString()}`, { credentials: 'same-origin' });
            const data = await response.json();
            this.sourceItems = (data.items || []).map((item) => {
              return { ...item, selected: true };
            });
            this.loadingSource = false;
          } catch (err) {
            this.loadingSource = false;
          }
        },

        applySource() {
          this.sourceItems.filter((item) => {
            return item.selected;
          }).forEach((item) => {
            const exists = this.lines.some((line) => {
              return line.source_type === item.source_type &&
                line.source_id === item.source_id &&
                line.source_item_id === item.source_item_id;
            });
            if (exists) return;
            let selectedQty = item.qty;
            if (selectedQty === null || selectedQty === undefined || selectedQty === '') {
              selectedQty = item.pending_qty || 0;
            }
            const line = this.newLine();
            line.item_code = item.item_code || '';
            line.item_name = item.item_name || '';
            line.qty = toNumber(selectedQty);
            line.uom = item.uom || '';
            line.rate = toNumber(item.rate || 0);
            line.source_type = item.source_type || '';
            line.source_id = item.source_id || '';
            line.source_document_no = item.source_document_no || '';
            line.source_item_id = item.source_item_id || '';
            this.syncLineFromItem(line, false);
            this.calcAmount(line);
            this.lines.push(line);
          });

          this.lines = this.lines.filter((line) => {
            return line.item_code || line.item_name || line.source_id;
          });
          if (!this.lines.length) this.addRow();
        },

        moveColumn(index, direction) {
          const target = index + direction;
          if (target < 0 || target >= this.preferences.columns.length) return;
          const column = this.preferences.columns.splice(index, 1)[0];
          this.preferences.columns.splice(target, 0, column);
        },

        async savePreferences() {
          if (!this.formKey || !this.viewKey) return;
          const csrfInput = document.querySelector('input[name="csrf_token"]');
          const csrfToken = csrfInput ? csrfInput.value : '';
          try {
            const response = await fetch(`/api/form-preferences/${encodeURIComponent(this.formKey)}/${encodeURIComponent(this.viewKey)}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
              credentials: 'same-origin',
              body: JSON.stringify(this.preferences)
            });
            const payload = await response.json();
            this.preferences = { columns: normalizeColumns(payload.columns || [], this.messages) };
            const modalEl = document.getElementById('columnsModal');
            if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          } catch (err) {
            // No-op
          }
        },

        async resetPreferences() {
          if (!this.formKey || !this.viewKey) {
            this.preferences = { columns: defaultColumns(this.messages) };
            return;
          }
          const csrfInput = document.querySelector('input[name="csrf_token"]');
          const csrfToken = csrfInput ? csrfInput.value : '';
          try {
            const response = await fetch(`/api/form-preferences/${encodeURIComponent(this.formKey)}/${encodeURIComponent(this.viewKey)}`, {
              method: 'DELETE',
              headers: { 'X-CSRFToken': csrfToken },
              credentials: 'same-origin'
            });
            const payload = await response.json();
            this.preferences = { columns: normalizeColumns(payload.columns || [], this.messages) };
          } catch (err) {
            // No-op
          }
        },

        formatMoney(value) {
          return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
      };
    });
  });
}());
