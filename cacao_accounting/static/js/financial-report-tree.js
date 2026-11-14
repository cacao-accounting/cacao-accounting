// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 William José Moreno Reyes

'use strict';

(function exposeFinancialReportTree(root, initializeFinancialReportTree) {
  if (typeof module === 'object' && module.exports) {
    module.exports = initializeFinancialReportTree;
    return;
  }
  initializeFinancialReportTree(root.document);
})(typeof globalThis === 'undefined' ? this : globalThis, function initializeFinancialReportTree(document) {
  if (!document || typeof document.querySelectorAll !== 'function') return;

  const table = document.querySelector('.ca-report-table');
  if (!table) return;

  const rows = Array.from(table.querySelectorAll('tbody tr'));
  const childrenByParent = new Map();
  const rowEntries = [];

  rows.forEach(function (row) {
    const cell = row.querySelector('td[data-code]');
    if (!cell) return;

    const code = cell.dataset.code || '';
    if (!code) return;

    const section = row.dataset.treeSection || '';
    const parent = cell.dataset.parent || '';
    const entry = {
      row: row,
      cell: cell,
      key: JSON.stringify([section, code]),
      parentKey: parent ? JSON.stringify([section, parent]) : null,
    };
    rowEntries.push(entry);

    if (entry.parentKey) {
      const children = childrenByParent.get(entry.parentKey) || [];
      children.push(entry);
      childrenByParent.set(entry.parentKey, children);
    }
  });

  const expandedByKey = new Map();

  function setDescendantVisibility(parentKey, parentVisible) {
    const children = childrenByParent.get(parentKey) || [];
    children.forEach(function (child) {
      child.row.hidden = !parentVisible;
      const childState = expandedByKey.get(child.key);
      const childExpanded = !childState || childState.expanded;
      setDescendantVisibility(child.key, parentVisible && childExpanded);
    });
  }

  rowEntries.forEach(function (entry) {
    const children = childrenByParent.get(entry.key) || [];
    if (!children.length) return;

    let state = expandedByKey.get(entry.key);
    if (!state) {
      state = { expanded: true, toggles: [] };
      expandedByKey.set(entry.key, state);
    }

    const label = entry.cell.querySelector('.ca-tree-label');
    if (!label) return;

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'ca-tree-toggle';
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', table.dataset.collapseLabel || '');
    toggle.textContent = '▾';
    state.toggles.push(toggle);
    label.insertBefore(toggle, label.firstChild);
    label.insertBefore(document.createTextNode(' '), toggle.nextSibling);

    toggle.addEventListener('click', function () {
      state.expanded = !state.expanded;
      state.toggles.forEach(function (control) {
        control.setAttribute('aria-expanded', state.expanded ? 'true' : 'false');
        control.setAttribute('aria-label', state.expanded ? table.dataset.collapseLabel || '' : table.dataset.expandLabel || '');
        control.textContent = state.expanded ? '▾' : '▸';
      });
      setDescendantVisibility(entry.key, state.expanded);
    });
  });
});
