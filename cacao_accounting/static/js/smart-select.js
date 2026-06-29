// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

(function () {
  function normalizeObjectValue(value) {
    if (!value || typeof value !== 'object') return String(value || '');
    const scalarKeys = ['value', 'id', 'code'];
    for (const key of scalarKeys) {
      if (value[key] !== undefined && value[key] !== null) return String(value[key]);
    }
    return '';
  }

  function normalizeValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'function') return normalizeValue(value());
    if (Array.isArray(value)) return value;

    if (typeof value === 'object') {
      return normalizeObjectValueFromSelector(value);
    }
    return String(value);
  }

  function normalizeObjectValueFromSelector(value) {
    if (!value.selector) return normalizeObjectValue(value);
    const el = document.querySelector(value.selector);
    if (!el) return '';
    return extractValueFromElement(el);
  }

  function extractValueFromElement(el) {
    if (el.tagName !== 'INPUT' && el.tagName !== 'SELECT') {
      const hidden = el.querySelector ? el.querySelector('input[type="hidden"]') : null;
      if (hidden) return hidden.value;
    }
    const rawValue = el.value;
    if (rawValue === undefined || rawValue === null || rawValue === '') return '';
    if (typeof rawValue === 'object') return normalizeObjectValue(rawValue);
    return String(rawValue);
  }

  function appendParam(params, key, value) {
    const normalized = normalizeValue(value);
    if (Array.isArray(normalized)) {
      normalized.forEach((v) => {
        const s = normalizeValue(v);
        if (!Array.isArray(s) && s !== '') params.append(key, s);
      });
    } else if (normalized !== '') {
      params.append(key, normalized);
    }
  }

  document.addEventListener('alpine:init', () => {
    Alpine.data('smartSelect', (config) => {
      return {
        endpoint: config.endpoint || '/api/search-select',
        doctype: config.doctype,
        name: config.name,
        minChars: config.minChars || 1,
        limit: config.limit || 20,
        filters: config.filters || {},
        filterSources: config.filterSources || [],
        requiredFilters: config.requiredFilters || [],
        preload: config.preload || false,
        loadOnFilterChange: config.loadOnFilterChange || false,
        preloadOnFocus: config.preloadOnFocus || false,
        autoSelectDefault: config.autoSelectDefault || false,
        messages: {
          placeholder: '',
          loading: '...',
          noResults: '',
          minChars: '',
          clear: '',
          invalid: '',
          error: '',
          ...config.messages
        },
        search: config.initialLabel || '',
        selectedValue: normalizeValue(config.initialValue) || '',
        selectedLabel: config.initialLabel || '',
        options: [],
        open: false,
        loading: false,
        error: '',
        invalid: false,
        lastFilterSignature: '',
        onSelect: config.onSelect || null,

        init() {
          this.lastFilterSignature = this.filterSignature();
          this.bindFilterSources();
          this.invalid = false;
          this.syncFilledState();
          if (!this.selectedValue && config.initialValue) {
            this.selectedValue = normalizeValue(config.initialValue);
          }
          if (this.preload && this.requiredFiltersPresent() && !this.selectedValue) {
            this.preloadOptions();
          }

          if (typeof this.$watch === 'function') {
            this.$watch('selectedValue', this.handleSelectedValueChange.bind(this));
          }
        },

        handleSelectedValueChange(value) {
          const normalized = normalizeValue(value);
          if (normalized) {
            this.updateLabelFromOptions(normalized);
          } else {
            this.search = '';
            this.selectedLabel = '';
          }
          this.syncFilledState();
        },

        updateLabelFromOptions(normalized) {
          const opt = this.options.find((o) => normalizeValue(o.value ?? o.id) === normalized);
          if (opt) {
            this.selectedLabel = opt.display_name || opt.label || '';
            this.search = this.selectedLabel;
          } else if (normalized !== normalizeValue(this.selectedLabel)) {
            this.search = this.selectedLabel || normalized;
          }
        },

        bindFilterSources() {
          this.filterSources.forEach((selector) => {
            const element = document.querySelector(selector);
            if (!element) return;
            const handler = () => { this.handleFilterChange(); };
            element.addEventListener('change', handler);
            element.addEventListener('input', handler);
          });
        },

        resolvedFilters() {
          const resolved = {};
          Object.keys(this.filters).forEach((key) => {
            resolved[key] = normalizeValue(this.filters[key]);
          });
          return resolved;
        },

        filterSignature() {
          return JSON.stringify(this.resolvedFilters());
        },

        handleFilterChange() {
          const nextSignature = this.filterSignature();
          if (nextSignature === this.lastFilterSignature) return;
          this.lastFilterSignature = nextSignature;
          this.clearSelection();
          if ((this.preload || this.loadOnFilterChange) && this.requiredFiltersPresent()) {
            this.preloadOptions();
          }
        },

        onInput(event) {
          if (event?.target) {
            this.search = event.target.value || '';
          }
          if (this.selectedLabel && this.search !== this.selectedLabel) {
            this.selectedValue = '';
            this.selectedLabel = '';
          }
          this.invalid = false;
          this.fetchOptions();
        },

        onFocus() {
          if (this.preloadOnFocus) {
            this.handlePreloadOnFocus();
          } else if (this.options.length > 0) {
            this.open = true;
          }
        },

        handlePreloadOnFocus() {
          if (this.loading) {
            this.open = true;
          } else if (!this.open) {
            this.openWhenNotOpen();
          }
        },

        openWhenNotOpen() {
          if (this.options.length > 0) {
            this.open = true;
          } else if (this.requiredFiltersPresent()) {
            this.preloadOptions({ openMenu: true });
          }
        },

        hasPreloadedOptions() {
          return this.options.length > 0;
        },

        notifyValueChange() {
          if (!this.$root) return;
          const input = this.$root.querySelector(`input[type="hidden"][name="${this.name}"]`);
          if (!input) {
            this.syncFilledState();
            return;
          }
          input.value = this.selectedValue || '';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          this.syncFilledState();
        },

        syncFilledState() {
          if (!this.$root?.classList) return;
          this.$root.classList.toggle('filled', Boolean(this.selectedValue));
        },

        async preloadOptions(settings) {
          const loadSettings = settings || {};
          this.error = '';
          const params = this.buildSearchParams('');
          this.loading = true;
          if (loadSettings.openMenu) {
            this.open = true;
          }
          try {
            const response = await this.fetchOptionsResponse(params);
            this.handlePreloadResponse(response);
          } catch (err) {
            this.handleFetchError(err, { keepOpen: false });
          }
        },

        async fetchOptionsResponse(params) {
          const response = await fetch(`${this.endpoint}?${params.toString()}`, { credentials: 'same-origin' });
          if (!response.ok) throw new Error(response.statusText);
          return response.json();
        },

        handlePreloadResponse(data) {
          this.options = data.results || [];
          this.loading = false;
          if (!this.selectedValue && this.autoSelectDefault) {
            this.autoSelectDefaultOption();
          }
        },

        autoSelectDefaultOption() {
          const defaultOption = this.options.find((opt) => opt.is_default);
          if (defaultOption) {
            this.selectOption(defaultOption);
          }
        },

        async fetchOptions() {
          const query = this.search.trim();
          this.error = '';
          if (!this.hasValidFilters()) {
            this.options = [];
            this.open = false;
            this.loading = false;
            return;
          }
          if (query.length < this.minChars) {
            this.handleShortQuery();
            return;
          }

          const params = this.buildSearchParams(query);
          this.loading = true;
          this.open = true;
          try {
            const data = await this.fetchOptionsResponse(params);
            this.options = data.results || [];
            this.loading = false;
            this.open = true;
          } catch (err) {
            this.handleFetchError(err, { keepOpen: true });
          }
        },

        handleFetchError(err, settings) {
          const errorSettings = settings || {};
          console.warn('smartSelect fetch failed', err);
          this.options = [];
          this.loading = false;
          this.error = this.messages.error;
          this.open = Boolean(errorSettings.keepOpen);
        },

        hasValidFilters() {
          return !this.requiredFilters.length || this.requiredFiltersPresent();
        },

        handleShortQuery() {
          if (this.hasPreloadedOptions()) {
            this.open = true;
            return;
          }
          this.options = [];
          this.open = false;
          this.loading = false;
        },

        buildSearchParams(query) {
          const params = new URLSearchParams();
          params.append('doctype', this.doctype);
          params.append('q', query);
          params.append('limit', this.limit);

          const currentFilters = this.resolvedFilters();
          Object.keys(currentFilters).forEach((key) => {
            appendParam(params, key, currentFilters[key]);
          });
          return params;
        },

        selectOptionValue(value, label) {
          this.selectedValue = normalizeValue(value) || '';
          this.selectedLabel = label || '';
          this.search = this.selectedLabel;
          this.open = false;
          this.invalid = false;
          this.error = '';
          this.notifyValueChange();
        },

        selectOptionFromValues(value, label, option) {
          this.selectOptionValue(value, label);
          if (typeof this.onSelect === 'function') {
            try {
              this.onSelect(option || { value: value, id: value, display_name: label, label: label });
            } catch (_) {
              console.warn('Error in onSelect callback:', _);
            }
          }
        },

        selectOption(option) {
          const optionValue = option.value ?? option.id;
          this.selectedValue = normalizeValue(optionValue) || '';
          this.selectedLabel = option.display_name || option.label || '';
          this.search = this.selectedLabel;
          this.open = false;
          this.invalid = false;
          this.error = '';
          if (typeof this.onSelect === 'function') {
            try {
              this.onSelect(option);
            } catch (_) {
              console.warn('Error in onSelect callback:', _);
            }
          }
          this.notifyValueChange();
        },

        requiredFiltersPresent() {
          const currentFilters = this.resolvedFilters();
          return !this.requiredFilters.some((key) => {
            return currentFilters[key] === '' || (Array.isArray(currentFilters[key]) && currentFilters[key].length === 0);
          });
        },

        clearSelection() {
          this.selectedValue = '';
          this.selectedLabel = '';
          this.search = '';
          this.options = [];
          this.open = false;
          this.invalid = false;
          this.error = '';
          this.notifyValueChange();
        },

        closeSoon() {
          setTimeout(() => {
            this.open = false;
            const restoredInitialLabel = this.selectedLabel && this.search === this.selectedLabel;
            this.invalid = Boolean(this.search.trim() && !this.selectedValue && !restoredInitialLabel);
          }, 300);
        }
      };
    });
  });
}());
