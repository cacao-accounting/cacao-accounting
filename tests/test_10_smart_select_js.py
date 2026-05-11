# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

import subprocess
from pathlib import Path


SMART_SELECT_FILE = Path(__file__).resolve().parents[1] / "cacao_accounting" / "static" / "js" / "smart-select.js"


def _run_node_script(script_body: str) -> None:
    process = subprocess.run(
        ["node", "-e", script_body],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def test_smart_select_fetch_options_uses_active_company_filter() -> None:
    script = f"""
const fs = require('fs');
const source = fs.readFileSync({str(SMART_SELECT_FILE)!r}, 'utf8');
const listeners = {{}};
const registry = {{}};
const companyInput = {{ value: 'cacao', addEventListener: () => {{}} }};
const hiddenInput = {{ value: '', dispatchEvent: () => {{}} }};
const requests = [];

global.Event = function(type, options) {{
  this.type = type;
  this.bubbles = Boolean(options && options.bubbles);
}};
global.window = {{ setTimeout: (fn) => fn() }};
global.document = {{
  addEventListener: (name, callback) => {{ listeners[name] = callback; }},
  querySelector: (selector) => {{
    if (selector === '#company') return companyInput;
    return null;
  }}
}};
global.Alpine = {{
  data: (name, factory) => {{ registry[name] = factory; }}
}};
global.fetch = (url) => {{
  requests.push(url);
  return Promise.resolve({{
    ok: true,
    json: () => Promise.resolve({{ results: [] }})
  }});
}};

eval(source);
listeners['alpine:init']();

(async () => {{
  const component = registry.smartSelect({{
    doctype: 'account',
    name: 'account',
    minChars: 1,
    filters: {{ company: {{ selector: '#company' }} }},
    filterSources: ['#company'],
    requiredFilters: ['company']
  }});
  component.$root = {{
    querySelector: (selector) => selector === 'input[type="hidden"][name="account"]' ? hiddenInput : null
  }};
  component.search = 'ca';
  await component.fetchOptions();
  if (requests.length !== 1) throw new Error('Expected one request');
  if (!requests[0].includes('doctype=account')) throw new Error('Missing doctype filter');
  if (!requests[0].includes('company=cacao')) throw new Error('Missing company filter');
  if (!requests[0].includes('q=ca')) throw new Error('Missing search query');
}})().catch((error) => {{
  console.error(error.stack || error.message);
  process.exit(1);
}});
"""
    _run_node_script(script)



def test_smart_select_preload_auto_selects_default_without_losing_options() -> None:
    script = f"""
const fs = require('fs');
const source = fs.readFileSync({str(SMART_SELECT_FILE)!r}, 'utf8');
const listeners = {{}};
const registry = {{}};
const companyInput = {{ value: 'cacao', addEventListener: () => {{}} }};
const hiddenInput = {{ value: '', dispatchEvent: () => {{}} }};

const defaultOption = {{ value: 'SER-DEFAULT', display_name: 'Serie default', is_default: true }};
const secondaryOption = {{ value: 'SER-ALT', display_name: 'Serie alternativa', is_default: false }};

global.Event = function(type, options) {{
  this.type = type;
  this.bubbles = Boolean(options && options.bubbles);
}};
global.window = {{ setTimeout: (fn) => fn() }};
global.document = {{
  addEventListener: (name, callback) => {{ listeners[name] = callback; }},
  querySelector: (selector) => {{
    if (selector === '#company') return companyInput;
    return null;
  }}
}};
global.Alpine = {{
  data: (name, factory) => {{ registry[name] = factory; }}
}};
global.fetch = () => Promise.resolve({{
  ok: true,
  json: () => Promise.resolve({{ results: [defaultOption, secondaryOption] }})
}});

eval(source);
listeners['alpine:init']();

(async () => {{
  const component = registry.smartSelect({{
    doctype: 'naming_series',
    name: 'naming_series_id',
    minChars: 1,
    loadOnFilterChange: true,
    autoSelectDefault: true,
    filters: {{ company: {{ selector: '#company' }}, entity_type: 'journal_entry' }},
    filterSources: ['#company'],
    requiredFilters: ['company']
  }});
  component.$root = {{
    querySelector: (selector) => selector === 'input[type="hidden"][name="naming_series_id"]' ? hiddenInput : null
  }};
  await component.preloadOptions();
  if (component.selectedValue !== 'SER-DEFAULT') throw new Error('Default series was not auto-selected');
  if (component.options.length !== 2) throw new Error('Preloaded options should remain available');
}})().catch((error) => {{
  console.error(error.stack || error.message);
  process.exit(1);
}});
"""
    _run_node_script(script)
