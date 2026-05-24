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
    };
    return escHtml(map[String(doctype || '').toLowerCase()] || String(doctype || '').slice(0, 2).toUpperCase());
  }

  function statusBadgeClass(node) {
    if (node.docstatus === 2) return 'ca-flow-badge--cancelled';
    const label = String(node?.status?.label || '').toLowerCase();
    if (label.includes('aprob') || label.includes('pagad')) return 'ca-flow-badge--approved';
    if (label.includes('pend') || label.includes('parcial')) return 'ca-flow-badge--partial';
    if (label.includes('borrador') || label.includes('draft')) return 'ca-flow-badge--draft';
    return 'ca-flow-badge--draft';
  }

  function renderMeta(node) {
    const chunks = [];
    if (node.posting_date) chunks.push(escHtml(node.posting_date));
    if (node.party_name) chunks.push(escHtml(node.party_name));
    if (node.total != null) chunks.push(`Total: ${fmtAmount(node.total, node.currency)}`);
    return chunks.join(' <span class="ca-flow-meta-sep">•</span> ');
  }

  function renderRelation(node) {
    const pieces = [];
    if (node.relation_type) pieces.push(`Relación: ${escHtml(node.relation_type)}`);
    if (node.applied_amount != null) {
      pieces.push(`<span class="ca-flow-badge ca-flow-badge--approved">Aplicado: ${fmtAmount(node.applied_amount, node.currency)}</span>`);
    }
    return pieces.join(' · ');
  }

  function renderNodeContent(node, isCurrent) {
    const label = escHtml(node.label || node.document_type || '');
    const docNo = escHtml(node.document_no || node.document_id || '');
    const status = escHtml(node?.status?.label || (node.docstatus === 2 ? 'Anulado' : ''));
    const strikeClass = node.relation_status && node.relation_status !== 'active' ? ' text-decoration-line-through' : '';
    const mainLink = node.url
      ? `<a href="${escHtml(node.url)}" class="ca-flow-node__link${strikeClass}">${docNo}</a>`
      : `<span class="ca-flow-node__link ca-flow-node__link--static${strikeClass}">${docNo}</span>`;
    const relation = renderRelation(node);
    const meta = renderMeta(node);
    return `
      <article class="ca-flow-node${isCurrent ? ' ca-flow-node--current' : ''}">
        <div class="ca-flow-node__content">
          <div class="ca-flow-node__main">
            <span class="ca-flow-node__type-badge">${doctypeCode(node.document_type)}</span>
            <span class="ca-flow-node__type">${label}</span>
            ${mainLink}
            ${status ? `<span class="ca-flow-badge ${statusBadgeClass(node)}">${status}</span>` : ''}
            ${isCurrent ? '<span class="ca-flow-badge ca-flow-badge--current">Actual</span>' : ''}
          </div>
          ${meta ? `<div class="ca-flow-node__meta">${meta}</div>` : ''}
          ${relation ? `<div class="ca-flow-node__relation">${relation}</div>` : ''}
        </div>
      </article>`;
  }

  function renderLimitNode(text) {
    return `<li class="ca-flow-tree__item"><div class="ca-flow-node-note">${escHtml(text)}</div></li>`;
  }

  function renderTree(nodes, current, expandAll) {
    if (!Array.isArray(nodes) || nodes.length === 0) return '';
    let html = '<ul class="ca-flow-tree">';
    for (const node of nodes) {
      if (node?.cycle_detected) {
        html += renderLimitNode('Ciclo detectado');
        continue;
      }
      if (node?.max_depth_reached) {
        html += renderLimitNode('Profundidad máxima alcanzada');
        continue;
      }
      if (node?.max_nodes_reached) {
        html += renderLimitNode('Límite de nodos alcanzado');
        continue;
      }

      const isCurrent = current && node.document_type === current.document_type && node.document_id === current.document_id;
      html += `<li class="ca-flow-tree__item">${renderNodeContent(node, isCurrent)}`;
      const children = Array.isArray(node.children) ? node.children : [];
      if (children.length > 0 && expandAll) {
        html += renderTree(children, current, expandAll);
      } else if (children.length > 0 && !expandAll) {
        html += `<div class="ca-flow-node__relation">+${children.length} documento(s) relacionado(s)</div>`;
      }
      html += '</li>';
    }
    html += '</ul>';
    return html;
  }

  function sumApplied(nodes) {
    if (!Array.isArray(nodes)) return 0;
    let total = 0;
    for (const node of nodes) {
      if (node && node.applied_amount != null) total += Number(node.applied_amount) || 0;
      total += sumApplied(node?.children || []);
    }
    return total;
  }

  // ---------------------------------------------------------------------------
  // Componente Alpine
  // ---------------------------------------------------------------------------

  function documentFlowTree(config) {
    return {
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

      get isDraft()    { return this.docstatus === 0; },
      get isCancelled(){ return this.docstatus === 2; },
      get documentCount() {
        const fromMeta = this.meta && Number.isFinite(this.meta.node_count) ? Number(this.meta.node_count) : 0;
        return Math.max(0, fromMeta + (this.current ? 1 : 0));
      },
      get documentCountLabel() {
        const count = this.documentCount;
        return `${count} ${count === 1 ? 'documento' : 'documentos'}`;
      },
      get currentAppliedAmount() {
        if (!this.current || this.current.document_type !== 'payment_entry') return null;
        return sumApplied(this.downstream);
      },
      get currentUnallocatedAmount() {
        if (!this.current || this.current.document_type !== 'payment_entry') return null;
        const total = Number(this.current.total);
        if (!Number.isFinite(total)) return null;
        const unallocated = total - (this.currentAppliedAmount || 0);
        return unallocated > 0 ? unallocated : 0;
      },

      toggle() {
        this.open = !this.open;
        if (this.open && !this.loaded && !this.isDraft) this.load();
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
        return renderTree(nodes, this.current, this.expandAllNodes);
      },
      renderCurrentNode() {
        if (!this.current) return '';
        let html = renderTree([this.current], this.current, true);
        if (this.current.document_type === 'payment_entry' && this.current.total != null) {
          html += '<div class="ca-flow-node__payment-summary">';
          html += `<span>Total: ${fmtAmount(this.current.total, this.current.currency)}</span>`;
          if (this.currentAppliedAmount != null) {
            html += `<span class="ca-flow-badge ca-flow-badge--approved">Aplicado: ${fmtAmount(this.currentAppliedAmount, this.current.currency)}</span>`;
          }
          if (this.currentUnallocatedAmount != null && this.currentUnallocatedAmount > 0) {
            html += `<span class="ca-flow-badge ca-flow-badge--partial">Sin asignar: ${fmtAmount(this.currentUnallocatedAmount, this.current.currency)}</span>`;
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
  if (typeof window !== 'undefined') {
    window.documentFlowTree = documentFlowTree;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { documentFlowTree, renderTree };
  }
})();
