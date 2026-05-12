// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

(function () {
  function normalizeObjectValue(value) {
    var scalarKeys = ['value', 'id', 'code'];
    for (var index = 0; index < scalarKeys.length; index += 1) {
      var key = scalarKeys[index];
      if (value[key] !== undefined && value[key] !== null) return value[key];
    }
    return '';
  }

  function normalizeValue(value) {
    if (typeof value === 'function') return normalizeValue(value());
    if (Array.isArray(value)) {
      return value
        .map(function (item) { return normalizeValue(item); })
        .filter(function (item) { return item !== undefined && item !== null && item !== ''; });
    }
    if (value && typeof value === 'object' && value.selector) {
      var element = document.querySelector(value.selector);
      return element ? normalizeValue(element.value) : '';
    }
    if (value && typeof value === 'object') {
      return normalizeObjectValue(value);
    }
    return value;
  }

  function appendParam(params, key, value) {
    var normalized = normalizeValue(value);
    if (Array.isArray(normalized)) {
      normalized.forEach(function (item) {
        if (item !== undefined && item !== null && item !== '') params.append(key, item);
      });
      return;
    }
    if (normalized !== undefined && normalized !== null && normalized !== '') params.append(key, normalized);
  }

  document.addEventListener('alpine:init', function () {
    Alpine.data('smartSelect', function (config) {
      return {
        endpoint: config.endpoint || '/api/search-select',
        doctype: config.doctype,
        name: config.name,
        minChars: config.minChars || 2,
        limit: config.limit || 20,
        filters: config.filters || {},
        filterSources: config.filterSources || [],
        requiredFilters: config.requiredFilters || [],
        preload: config.preload || false,
        loadOnFilterChange: config.loadOnFilterChange || false,
        preloadOnFocus: config.preloadOnFocus || false,
        autoSelectDefault: config.autoSelectDefault || false,
        messages: Object.assign({
          placeholder: '',
          loading: '...',
          noResults: '',
          minChars: '',
          clear: '',
          invalid: '',
          error: ''
        }, config.messages || {}),
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

        init: function () {
          this.lastFilterSignature = this.filterSignature();
          this.bindFilterSources();
          this.invalid = false;
          if (!this.selectedValue && config.initialValue) {
            this.selectedValue = normalizeValue(config.initialValue);
          }
          if (this.preload && this.requiredFiltersPresent() && !this.selectedValue) {
            this.preloadOptions();
          }
        },

        bindFilterSources: function () {
          var self = this;
          this.filterSources.forEach(function (selector) {
            var element = document.querySelector(selector);
            if (!element) return;
            element.addEventListener('change', function () {
              self.handleFilterChange();
            });
            element.addEventListener('input', function () {
              self.handleFilterChange();
            });
          });
        },

        resolvedFilters: function () {
          var resolved = {};
          Object.keys(this.filters).forEach(function (key) {
            resolved[key] = normalizeValue(this.filters[key]);
          }, this);
          return resolved;
        },

        filterSignature: function () {
          return JSON.stringify(this.resolvedFilters());
        },

        handleFilterChange: function () {
          var nextSignature = this.filterSignature();
          if (nextSignature === this.lastFilterSignature) return;
          this.lastFilterSignature = nextSignature;
          this.clearSelection();
          if ((this.preload || this.loadOnFilterChange) && this.requiredFiltersPresent()) {
            this.preloadOptions();
          }
        },

        onInput: function () {
          if (this.selectedLabel && this.search !== this.selectedLabel) {
            this.selectedValue = '';
            this.selectedLabel = '';
          }
          this.invalid = false;
          this.fetchOptions();
        },

        onFocus: function () {
          if (this.preload && this.preloadOnFocus && !this.open && !this.loading) {
            if (this.hasPreloadedOptions()) {
              this.open = true;
            } else {
              this.preloadOptions({ openMenu: true });
            }
          }

          // If preload started during init and is still loading, show the menu state on first focus.
          if (this.preload && this.preloadOnFocus && !this.open && this.loading) {
            this.open = true;
          }
        },

        hasPreloadedOptions: function () {
          return this.preload && this.options.length > 0;
        },

        notifyValueChange: function () {
          if (!this.$root) return;

          var input = this.$root.querySelector('input[type="hidden"][name="' + this.name + '"]');
          if (!input) return;

          input.value = this.selectedValue || '';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        },

        preloadOptions: function (settings) {
          var loadSettings = settings || {};
          var self = this;
          this.error = '';
          var params = new URLSearchParams();
          params.append('doctype', this.doctype);
          params.append('q', '');
          params.append('limit', this.limit);
          Object.keys(this.filters).forEach(function (key) {
            appendParam(params, key, self.filters[key]);
          });

          this.loading = true;
          if (loadSettings.openMenu) {
            this.open = true;
          }
          return fetch(this.endpoint + '?' + params.toString(), { credentials: 'same-origin' })
            .then(function (response) {
              if (!response.ok) throw new Error(response.statusText);
              return response.json();
            })
            .then(function (data) {
              self.options = data.results || [];
              self.loading = false;
              if (!self.selectedValue && self.autoSelectDefault) {
                var defaultOption = self.options.find(function (opt) { return opt.is_default; });
                if (defaultOption) {
                  self.selectedValue = normalizeValue(defaultOption.value !== undefined ? defaultOption.value : defaultOption.id) || '';
                  self.selectedLabel = defaultOption.display_name || defaultOption.label || '';
                  self.search = self.selectedLabel;
                  self.invalid = false;
                  self.error = '';
                  if (typeof self.onSelect === 'function') {
                    try {
                      self.onSelect(defaultOption);
                    } catch (ignore) {
                      // No-op: do not break select flow
                    }
                  }
                  self.notifyValueChange();
                  return;
                }
              }
            })
            .catch(function () {
              self.options = [];
              self.loading = false;
              self.error = self.messages.error;
            });
        },

        fetchOptions: function () {
          var query = this.search.trim();
          var self = this;
          this.error = '';
          if (this.requiredFilters.length && !this.requiredFiltersPresent()) {
            this.options = [];
            this.open = false;
            this.loading = false;
            return;
          }
          if (query.length < this.minChars) {
            if (this.hasPreloadedOptions()) {
              this.open = true;
              return;
            }
            this.options = [];
            this.open = false;
            this.loading = false;
            return;
          }

          var params = new URLSearchParams();
          params.append('doctype', this.doctype);
          params.append('q', query);
          params.append('limit', this.limit);
          Object.keys(this.filters).forEach(function (key) {
            appendParam(params, key, self.filters[key]);
          });

          this.loading = true;
          this.open = true;
          return fetch(this.endpoint + '?' + params.toString(), { credentials: 'same-origin' })
            .then(function (response) {
              if (!response.ok) throw new Error(response.statusText);
              return response.json();
            })
            .then(function (data) {
              self.options = data.results || [];
              self.loading = false;
              self.open = true;
            })
            .catch(function () {
              self.options = [];
              self.loading = false;
              self.error = self.messages.error;
              self.open = true;
            });
        },

        selectOption: function (option) {
          var optionValue = option.value !== undefined ? option.value : option.id;
          this.selectedValue = normalizeValue(optionValue) || '';
          this.selectedLabel = option.display_name || option.label || '';
          this.search = this.selectedLabel;
          this.options = [];
          this.open = false;
          this.invalid = false;
          this.error = '';
          if (typeof this.onSelect === 'function') {
            try {
              this.onSelect(option);
            } catch (ignore) {
              // No-op: do not break select flow
            }
          }
          this.notifyValueChange();
        },

        requiredFiltersPresent: function () {
          var self = this;
          return !this.requiredFilters.some(function (key) {
            return !normalizeValue(self.filters[key]);
          });
        },

        clearSelection: function () {
          this.selectedValue = '';
          this.selectedLabel = '';
          this.search = '';
          this.options = [];
          this.open = false;
          this.invalid = false;
          this.error = '';
          this.notifyValueChange();
        },

        closeSoon: function () {
          var self = this;
          window.setTimeout(function () {
            self.open = false;
            var restoredInitialLabel = self.selectedLabel && self.search === self.selectedLabel;
            self.invalid = Boolean(self.search.trim() && !self.selectedValue && !restoredInitialLabel);
          }, 150);
        }
      };
    });
  });
}());
