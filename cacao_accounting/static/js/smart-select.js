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
      for (const v of normalized) {
        const s = normalizeValue(v);
        if (!Array.isArray(s) && s !== '') params.append(key, s);
      }
    } else if (normalized !== '') {
      params.append(key, normalized);
    }
  }

  function findOptionByNormalizedValue(options, normalized) {
    for (const option of options) {
      if (normalizeValue(option.value ?? option.id) === normalized) return option;
    }
    return undefined;
  }

  function clampNumber(value, min, max) {
    return Math.min(Math.max(value, min), max);
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
        _positionHandler: null,

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
          const opt = findOptionByNormalizedValue(this.options, normalized);
          if (opt) {
            this.selectedLabel = opt.display_name || opt.label || '';
            this.search = this.selectedLabel;
          } else if (normalized !== normalizeValue(this.selectedLabel)) {
            this.search = this.selectedLabel || normalized;
          }
        },

        bindFilterSources() {
          for (const selector of this.filterSources) {
            const element = document.querySelector(selector);
            if (!element) continue;
            const handler = this.handleFilterChange.bind(this);
            element.addEventListener('change', handler);
            element.addEventListener('input', handler);
          }
        },

        resolvedFilters() {
          const resolved = {};
          for (const key of Object.keys(this.filters)) {
            resolved[key] = normalizeValue(this.filters[key]);
          }
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
            this.openMenu();
          }
        },

        handlePreloadOnFocus() {
          if (this.loading) {
            this.openMenu();
          } else if (!this.open) {
            this.openWhenNotOpen();
          }
        },

        openWhenNotOpen() {
          if (this.options.length > 0) {
            this.openMenu();
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
            this.openMenu();
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
          const defaultOption = this._findDefaultOption();
          if (defaultOption) {
            this.selectOption(defaultOption);
          }
        },

        _findDefaultOption() {
          for (const opt of this.options) {
            if (opt.is_default) return opt;
          }
          return undefined;
        },

        _isDefaultOption(opt) {
          return opt.is_default;
        },

        async fetchOptions() {
          const query = this.search.trim();
          this.error = '';
          if (!this.hasValidFilters()) {
            this.options = [];
            this.closeMenu();
            this.loading = false;
            return;
          }
          if (query.length < this.minChars) {
            this.handleShortQuery();
            return;
          }

          const params = this.buildSearchParams(query);
          this.loading = true;
          this.openMenu();
          try {
            const data = await this.fetchOptionsResponse(params);
            this.options = data.results || [];
            this.loading = false;
            this.openMenu();
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
          if (errorSettings.keepOpen) {
            this.openMenu();
          } else {
            this.closeMenu();
          }
        },

        hasValidFilters() {
          return !this.requiredFilters.length || this.requiredFiltersPresent();
        },

        handleShortQuery() {
          if (this.hasPreloadedOptions()) {
            this.openMenu();
            return;
          }
          this.options = [];
          this.closeMenu();
          this.loading = false;
        },

        buildSearchParams(query) {
          const params = new URLSearchParams();
          params.append('doctype', this.doctype);
          params.append('q', query);
          params.append('limit', this.limit);

          const currentFilters = this.resolvedFilters();
          for (const key of Object.keys(currentFilters)) {
            appendParam(params, key, currentFilters[key]);
          }
          return params;
        },

        selectOptionValue(value, label) {
          this.selectedValue = normalizeValue(value) || '';
          this.selectedLabel = label || '';
          this.search = this.selectedLabel;
          this.closeMenu();
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
          this.closeMenu();
          this.invalid = false;
          this.error = '';
          if (typeof this.onSelect === 'function') {
            this._safeCallOnSelect(option);
          }
          this.notifyValueChange();
        },

        _safeCallOnSelect(option) {
          try {
            this.onSelect(option);
          } catch (_) {
            console.warn('Error in onSelect callback:', _);
          }
        },

        requiredFiltersPresent() {
          const currentFilters = this.resolvedFilters();
          return !this._hasEmptyRequiredFilter(currentFilters);
        },

        _hasEmptyRequiredFilter(currentFilters) {
          for (const key of this.requiredFilters) {
            const val = currentFilters[key];
            if (val === '' || (Array.isArray(val) && val.length === 0)) return true;
          }
          return false;
        },

        clearSelection() {
          this.selectedValue = '';
          this.selectedLabel = '';
          this.search = '';
          this.options = [];
          this.closeMenu();
          this.invalid = false;
          this.error = '';
          this.notifyValueChange();
        },

        closeSoon() {
          setTimeout(this._closeSoonHandler.bind(this), 300);
        },

        _closeSoonHandler() {
          this.closeMenu();
          const restoredInitialLabel = this.selectedLabel && this.search === this.selectedLabel;
          this.invalid = Boolean(this.search.trim() && !this.selectedValue && !restoredInitialLabel);
        },

        openMenu() {
          this.open = true;
          this.bindMenuPositionListeners();
          this.scheduleMenuPositionUpdate();
        },

        closeMenu() {
          this.open = false;
          this.unbindMenuPositionListeners();
          this.clearMenuPosition();
        },

        scheduleMenuPositionUpdate() {
          if (typeof window === 'undefined') return;
          const defer = typeof window.setTimeout === 'function' ? window.setTimeout.bind(window) : setTimeout;
          defer(this.updateMenuPosition.bind(this), 0);
        },

        bindMenuPositionListeners() {
          if (this._positionHandler || typeof window === 'undefined') return;
          if (typeof window.addEventListener !== 'function') return;
          this._positionHandler = this.updateMenuPosition.bind(this);
          window.addEventListener('resize', this._positionHandler);
          window.addEventListener('scroll', this._positionHandler, true);
        },

        unbindMenuPositionListeners() {
          if (!this._positionHandler || typeof window === 'undefined') return;
          if (typeof window.removeEventListener !== 'function') return;
          window.removeEventListener('resize', this._positionHandler);
          window.removeEventListener('scroll', this._positionHandler, true);
          this._positionHandler = null;
        },

        menuElements() {
          if (!this.$root?.querySelector) return {};
          const menu = this.$root.querySelector('.ca-smart-select-menu');
          const anchor = this.$root.querySelector('.ca-smart-select-input-wrap') || this.$root.querySelector('.ca-smart-select-input');
          return { menu, anchor };
        },

        updateMenuPosition() {
          if (!this.open || typeof window === 'undefined') return;
          const { menu, anchor } = this.menuElements();
          if (!menu || !anchor?.getBoundingClientRect) return;

          const rect = anchor.getBoundingClientRect();
          const margin = 8;
          const gap = 4;
          const minWidth = 160;
          const maxHeight = 256;
          const viewportWidth = window.innerWidth || document.documentElement.clientWidth || rect.right;
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight || rect.bottom;
          const availableBelow = viewportHeight - rect.bottom - margin;
          const availableAbove = rect.top - margin;
          const openAbove = availableBelow < 120 && availableAbove > availableBelow;
          const availableHeight = Math.max(72, (openAbove ? availableAbove : availableBelow) - gap);
          const menuHeight = Math.min(maxHeight, availableHeight);
          const menuWidth = Math.max(rect.width, minWidth);
          const maxLeft = Math.max(margin, viewportWidth - menuWidth - margin);
          const left = clampNumber(rect.left, margin, maxLeft);
          const maxTop = Math.max(margin, viewportHeight - margin - menuHeight);
          const top = openAbove ? Math.max(margin, rect.top - gap - menuHeight) : Math.min(rect.bottom + gap, maxTop);

          menu.style.position = 'fixed';
          menu.style.left = `${left}px`;
          menu.style.right = 'auto';
          menu.style.top = `${top}px`;
          menu.style.width = `${menuWidth}px`;
          menu.style.maxHeight = `${menuHeight}px`;
          menu.style.zIndex = '2000';
        },

        clearMenuPosition() {
          const { menu } = this.menuElements();
          if (!menu) return;
          menu.style.position = '';
          menu.style.left = '';
          menu.style.right = '';
          menu.style.top = '';
          menu.style.width = '';
          menu.style.maxHeight = '';
          menu.style.zIndex = '';
        }
      };
    });
  });
}());
