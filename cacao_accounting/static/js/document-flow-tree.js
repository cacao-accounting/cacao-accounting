// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

/**
 * Componente Alpine.js reutilizable: documentFlowTree
 *
 * Renderiza el árbol de flujo documental (upstream + downstream) de
 * cualquier documento del sistema.  El backend genera la estructura
 * completa del árbol; este componente sólo la visualiza.
 *
 * Registro: Alpine.data('documentFlowTree', documentFlowTree)
 *
 * Uso en templates:
 *   <div x-data="documentFlowTree({ apiUrl, docstatus })"> ... </div>
 */

(function () {
  const DEFAULT_MESSAGES = {
    total: 'Total:',
    relationship: 'Relación:',
    applied: 'Aplicado:',
    unallocated: 'Sin asignar:',
    voided: 'Anulado',
    current: 'Actual',
    cycleDetected: 'Ciclo detectado',
    maxDepthReached: 'Profundidad máxima alcanzada',
    maxNodesReached: 'Límite de nodos alcanzado',
    document: 'documento',
    documents: 'documentos',
    relatedDocument: 'documento relacionado',
    relatedDocuments: 'documentos relacionados',
    relationTypes: {
      reuse: 'Reutilización',
      quotation: 'Cotización',
      order: 'Orden',
      receipt: 'Recepción',
      billing: 'Facturación',
      advance: 'Anticipo',
      credit_note: 'Nota de crédito',
      debit_note: 'Nota de débito',
      landed_cost: 'Costo de importación',
      payment: 'Pago',
      refund: 'Reembolso',
      delivery: 'Entrega',
      return: 'Devolución',
      stock: 'Movimiento de inventario',
      accounting: 'Contabilidad',
      collection: 'Cobro',
      invoice_reversal: 'Reversión de factura',
      payment_reference: 'Referencia de pago',
      purchase_order: 'Orden de compra',
      stock_entry: 'Movimiento de inventario',
      source: 'Origen',
      reference: 'Referencia',
      fulfillment: 'Cumplimiento',
    },
  };

  // ---------------------------------------------------------------------------
  // Helpers de renderizado (sin dependencias externas)
  // ---------------------------------------------------------------------------

  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function fmtAmount(n, currency) {
    let formatted;
    try {
      formatted = Number(n).toLocaleString('es-NI', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    } catch (e) {
      formatted = String(n);
    }
    return currency ? `${escHtml(currency)} ${formatted}` : formatted;
  }

  function doctypeCode(doctype) {
    const map = {
      payment_entry: 'PE',
      sales_invoice: 'SI',
      purchase_invoice: 'PI',
      delivery_note: 'DN',
      sales_order: 'SO',
      purchase_order: 'PO',
      sales_quotation: 'QT',
      purchase_request: 'RQ',
      purchase_receipt: 'RC',
      sales_debit_note: 'ND',
      purchase_debit_note: 'ND',
      sales_credit_note: 'NC',
      purchase_credit_note: 'NC',
      import_landed_cost: 'ILC',
    };
    return escHtml(map[String(doctype || '').toLowerCase()] || String(doctype || '').slice(0, 2).toUpperCase());
  }

  function statusBadgeClass(node) {
    if (node.docstatus === 2) return 'ca-flow-badge--cancelled';
    const label = String(node?.status?.label || '').toLowerCase();
    if (label.includes('aprob') || label.includes('pagad')) return 'ca-flow-badge--approved';
    if (label.includes('pend') || label.includes('parcial')) return 'ca-flow-badge--partial';
    if (label.includes('borrador') || label.includes('draft')) return 'ca-flow-badge--draft';
    return '';
  }

  function renderMeta(node, messages) {
    const chunks = [];
    if (node.posting_date) chunks.push(escHtml(node.posting_date));
    if (node.party_name) chunks.push(escHtml(node.party_name));
    if (node.total != null) chunks.push(`${escHtml(messages.total)} ${fmtAmount(node.total, node.currency)}`);
    return chunks.join(' <span class="ca-flow-meta-sep">•</span> ');
  }

  function renderRelation(node, messages) {
    const pieces = [];
    if (node.relation_type) {
      const label = messages.relationTypes?.[node.relation_type] || DEFAULT_MESSAGES.relationTypes[node.relation_type] || node.relation_type;
      pieces.push(`${escHtml(messages.relationship)} ${escHtml(label)}`);
    }
    if (node.applied_amount != null) {
      pieces.push(`<span class="ca-flow-badge ca-flow-badge--approved">${escHtml(messages.applied)} ${fmtAmount(node.applied_amount, node.currency)}</span>`);
    }
    return pieces.join(' · ');
  }

  function renderNodeContent(node, isCurrent, messages) {
    const label = escHtml(node.label || node.document_type || '');
    const docNo = escHtml(node.document_no || node.document_id || '');
    const status = escHtml(node?.status?.label || (node.docstatus === 2 ? messages.voided : ''));
    const strikeClass = node.relation_status && node.relation_status !== 'active' ? ' text-decoration-line-through' : '';
    const mainLink = node.url
      ? `<a href="${escHtml(node.url)}" class="ca-flow-node__link${strikeClass}">${docNo}</a>`
      : `<span class="ca-flow-node__link ca-flow-node__link--static${strikeClass}">${docNo}</span>`;
    const relation = renderRelation(node, messages);
    const meta = renderMeta(node, messages);
    return `
      <article class="ca-flow-node${isCurrent ? ' ca-flow-node--current' : ''}">
        <div class="ca-flow-node__content">
          <div class="ca-flow-node__main">
            <span class="ca-flow-node__type-badge">${doctypeCode(node.document_type)}</span>
            <span class="ca-flow-node__type">${label}</span>
            ${mainLink}
            ${status ? `<span class="ca-flow-badge ${statusBadgeClass(node)}">${status}</span>` : ''}
            ${isCurrent ? `<span class="ca-flow-badge ca-flow-badge--current">${escHtml(messages.current)}</span>` : ''}
          </div>
          ${meta ? `<div class="ca-flow-node__meta">${meta}</div>` : ''}
          ${relation ? `<div class="ca-flow-node__relation">${relation}</div>` : ''}
        </div>
      </article>`;
  }

  function renderLimitNode(text) {
    return `<li class="ca-flow-tree__item"><div class="ca-flow-node-note">${escHtml(text)}</div></li>`;
  }

  function renderTree(nodes, current, expandAll, messages = DEFAULT_MESSAGES) {
    if (!Array.isArray(nodes) || nodes.length === 0) return '';
    let html = '<ul class="ca-flow-tree">';
    for (const node of nodes) {
      if (node?.cycle_detected) {
        html += renderLimitNode(messages.cycleDetected);
        continue;
      }
      if (node?.max_depth_reached) {
        html += renderLimitNode(messages.maxDepthReached);
        continue;
      }
      if (node?.max_nodes_reached) {
        html += renderLimitNode(messages.maxNodesReached);
        continue;
      }

      const isCurrent = current && node.document_type === current.document_type && node.document_id === current.document_id;
      html += `<li class="ca-flow-tree__item">${renderNodeContent(node, isCurrent, messages)}`;
      const children = Array.isArray(node.children) ? node.children : [];
      if (children.length > 0 && expandAll) {
        html += renderTree(children, current, expandAll, messages);
      } else if (children.length > 0 && !expandAll) {
        const relatedLabel = children.length === 1 ? messages.relatedDocument : messages.relatedDocuments;
        html += `<div class="ca-flow-node__relation">+${children.length} ${escHtml(relatedLabel)}</div>`;
      }
      html += '</li>';
    }
    html += '</ul>';
    return html;
  }

  // ---------------------------------------------------------------------------
  // Componente Alpine
  // ---------------------------------------------------------------------------

  function documentFlowTree(config) {
    const messages = {
      ...DEFAULT_MESSAGES,
      ...(config.messages || {}),
      relationTypes: { ...DEFAULT_MESSAGES.relationTypes, ...(config.messages?.relationTypes || {}) },
    };
    return {
      messages,
      apiUrl:   config.apiUrl   || '',
      docstatus: config.docstatus != null ? config.docstatus : -1,

      open:     false,
      loading:  false,
      loaded:   false,
      error:    false,

      upstream:      [],
      downstream:    [],
      createActions: Array.isArray(config.createActions) ? config.createActions : [],
      current:       null,
      meta:          null,
      expandAllNodes: true,

      get isDraft()    { return Number(this.current?.docstatus ?? this.docstatus) === 0; },
      get isCancelled(){ return Number(this.current?.docstatus ?? this.docstatus) === 2; },
      get documentCount() {
        const fromMeta = this.meta && Number.isFinite(this.meta.node_count) ? Number(this.meta.node_count) : 0;
        return Math.max(0, fromMeta + (this.current ? 1 : 0));
      },
      get documentCountLabel() {
        const count = this.documentCount;
        return `${count} ${count === 1 ? this.messages.document : this.messages.documents}`;
      },
      get currentAppliedAmount() {
        if (!this.current || this.current.document_type !== 'payment_entry') return null;
        if (this.isCancelled) return 0;
        const total = Number(this.current.total);
        const unallocated = Number(this.current.unallocated_amount);
        if (!Number.isFinite(total) || !Number.isFinite(unallocated)) return null;
        return Math.max(0, total - Math.max(0, unallocated));
      },
      get currentUnallocatedAmount() {
        if (!this.current || this.current.document_type !== 'payment_entry') return null;
        if (this.isCancelled) return 0;
        const unallocated = Number(this.current.unallocated_amount);
        if (!Number.isFinite(unallocated)) return null;
        return Math.max(0, unallocated);
      },

      toggle() {
        this.open = !this.open;
        if (this.open && !this.loaded) this.load();
      },
      expandAll() { this.expandAllNodes = true; },
      collapseAll() { this.expandAllNodes = false; },

      load() {
        if (!this.apiUrl) return;
        this.loading = true;
        this.error   = false;
        fetch(this.apiUrl, { credentials: 'same-origin' })
          .then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
          })
          .then((data) => {
            this.current       = data.current        || null;
            this.upstream      = data.upstream       || [];
            this.downstream    = data.downstream     || [];
            this.createActions = data.create_actions || [];
            this.meta          = data.meta           || null;
            this.loaded  = true;
            this.loading = false;
          })
          .catch(() => {
            this.error   = true;
            this.loading = false;
          });
      },

      /** Renderiza la lista de nodos raíz (upstream o downstream). */
      renderNodes(nodes) {
        return renderTree(nodes, this.current, this.expandAllNodes, this.messages);
      },
      renderCurrentNode() {
        if (!this.current) return '';
        let html = renderTree([this.current], this.current, true, this.messages);
        if (this.current.document_type === 'payment_entry' && this.current.total != null) {
          html += '<div class="ca-flow-node__payment-summary">';
          html += `<span>${escHtml(this.messages.total)} ${fmtAmount(this.current.total, this.current.currency)}</span>`;
          if (this.currentAppliedAmount != null) {
            html += `<span class="ca-flow-badge ca-flow-badge--approved">${escHtml(this.messages.applied)} ${fmtAmount(this.currentAppliedAmount, this.current.currency)}</span>`;
          }
          if (this.currentUnallocatedAmount != null && this.currentUnallocatedAmount > 0) {
            html += `<span class="ca-flow-badge ca-flow-badge--partial">${escHtml(this.messages.unallocated)} ${fmtAmount(this.currentUnallocatedAmount, this.current.currency)}</span>`;
          }
          html += '</div>';
        }
        return html;
      },
    };
  }

  // Registro en Alpine cuando esté disponible.
  if (typeof document !== 'undefined') {
    document.addEventListener('alpine:init', function () {
      if (typeof Alpine !== 'undefined' && typeof Alpine.data === 'function') {
        Alpine.data('documentFlowTree', documentFlowTree);
      }
    });
  }

  // Exposición global para tests y uso sin Alpine.
  if (typeof globalThis !== 'undefined') {
    globalThis.documentFlowTree = documentFlowTree;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { documentFlowTree, renderTree };
  }
})();
