// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

document.addEventListener('alpine:init', () => {
  Alpine.data('hierarchyParentSelect', (config) => ({
    requestId: 0,

    async refresh(entity) {
      const select = this.$refs.parent;
      const currentValue = select.value;
      const requestId = ++this.requestId;

      if (!entity) {
        this.replaceOptions(select, [], currentValue);
        return;
      }

      const params = new URLSearchParams({ entity, action: config.action });
      if (config.excludeId) params.set('exclude_id', config.excludeId);

      try {
        const response = await fetch(`${config.endpoint}?${params}`, { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Could not load hierarchy parents');
        const options = await response.json();
        if (requestId !== this.requestId) return;
        this.replaceOptions(select, options, currentValue);
      } catch (_error) {
        if (requestId === this.requestId) this.replaceOptions(select, [], currentValue);
      }
    },

    replaceOptions(select, options, currentValue) {
      const document = select.ownerDocument;
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = config.placeholder;
      select.replaceChildren(placeholder);

      for (const option of options) {
        const element = document.createElement('option');
        element.value = option.value;
        element.textContent = option.label;
        select.append(element);
      }

      select.value = options.some((option) => option.value === currentValue) ? currentValue : '';
    },
  }));
});
