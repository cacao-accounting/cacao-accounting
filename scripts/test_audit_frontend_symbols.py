"""Tests for independently identifiable template audit candidates."""

import unittest

from jinja2 import TemplateSyntaxError

from audit_frontend_symbols import template_units


class TemplateUnitsTests(unittest.TestCase):
    """Exercise Jinja scope, HTML actions, handlers and syntax errors."""

    def test_units_are_in_source_order_and_keep_positions(self):
        source = """{% macro editor() %}
<form action="{{ url_for('save') }}" x-data="editor()">
  {% if can_save %}
  <button @click="save()">Save</button>
  {% endif %}
</form>
{% endmacro %}
<script>function start() { return 1; }</script>
"""
        units = template_units(source)
        names = [name for _, name in units]
        self.assertEqual([line for line, _ in units], [1, 2, 2, 3, 4, 4, 8])
        self.assertEqual(names[0], "macro editor")
        self.assertTrue(any(name.startswith("editor: condicional Jinja") for name in names))
        self.assertTrue(any(name.startswith("handler @click") for name in names))
        self.assertTrue(any(name == "script [línea 8].start()" for name in names))

    def test_empty_template_is_represented(self):
        self.assertEqual(template_units("plain text"), [(1, "[plantilla]")])

    def test_invalid_jinja_is_not_silently_skipped(self):
        with self.assertRaises(TemplateSyntaxError):
            template_units("{% if ok %}no end")


class JavascriptUnitsTests(unittest.TestCase):
    """Check named functions, nested callbacks and duplicate declarations."""

    def test_extracts_methods_and_callbacks(self):
        from audit_frontend_symbols import javascript_units

        source = "function outer() { return [1].map((x) => x); }\nconst panel = { save() { return 1; } };"
        entries = javascript_units(source)
        names = [name for _, name in entries]
        self.assertEqual(names[0], "outer()")
        self.assertTrue(names[1].startswith("outer.callback"))
        self.assertEqual(names[2], "panel.save()")

    def test_invalid_script_fails(self):
        import subprocess
        from audit_frontend_symbols import javascript_units

        with self.assertRaises(subprocess.CalledProcessError):
            javascript_units("function broken( {")

    def test_invalid_embedded_script_is_flagged(self):
        entries = template_units("<script>function broken( {</script>")
        self.assertIn("análisis JS pendiente", entries[0][1])


class EmbeddedHandlerTests(unittest.TestCase):
    """Exercise real HTML and Alpine constructs omitted by a script-only scan."""

    def test_native_handlers_and_alpine_methods_are_individual(self):
        source = """<form onsubmit="return confirm('sure')">
<select onchange="this.form.submit()"></select>
<div x-data='{ rows: {{ rows|tojson }},
  addRow() { this.rows.push(1); },
  removeRow(index) { this.rows.splice(index, 1); }
}'><button onclick="save()">Save</button></div></form>"""
        entries = template_units(source)
        names = [name for _, name in entries]
        self.assertTrue(any(name.startswith("handler onsubmit ") for name in names))
        self.assertTrue(any(name.startswith("handler onchange ") for name in names))
        self.assertTrue(any(name.startswith("handler onclick ") for name in names))
        self.assertTrue(any(".addRow()" in name for name in names))
        self.assertTrue(any(".removeRow()" in name for name in names))
        self.assertTrue(any(line == 5 and ".removeRow()" in name for line, name in entries))

    def test_method_line_uses_multiline_attribute_location(self):
        source = """<div
  class="entry"
  x-data='{
    save() { return 1; }
  }'>
</div>"""
        self.assertTrue(any(line == 4 and name.endswith(".save()") for line, name in template_units(source)))

    def test_missing_javascript_parser_is_reported_for_each_embedded_unit(self):
        from unittest.mock import patch

        with patch("audit_frontend_symbols.javascript_units", side_effect=FileNotFoundError):
            entries = template_units('<div x-data="component()"></div><script>start()</script>')
        names = [name for _, name in entries]
        self.assertTrue(any(name.startswith("componente Alpine: análisis JS pendiente") for name in names))
        self.assertTrue(any(name.startswith("script embebido: análisis JS pendiente") for name in names))

    def test_invalid_alpine_expression_is_flagged(self):
        entries = template_units('<div x-data="{ broken( }"></div>')
        self.assertTrue(any("componente Alpine: análisis JS pendiente" in name for _, name in entries))


class JinjaConditionalJavascriptTests(unittest.TestCase):
    """All feasible Jinja branches inside Alpine expressions remain auditable."""

    def test_callbacks_in_both_conditional_branches(self):
        source = """<div x-data='{
{% if a %} save() { return 1; }{% else %} cancel() { return 2; }{% endif %},
common() { return 3; }
}'></div>"""
        names = [name for _, name in template_units(source)]
        self.assertTrue(any(name.endswith(".save()") for name in names))
        self.assertTrue(any(name.endswith(".cancel()") for name in names))
        self.assertEqual(sum(name.endswith(".common()") for name in names), 1)
        self.assertFalse(any("análisis JS pendiente" in name for name in names))

    def test_unsupported_loop_remains_explicit(self):
        source = """<div x-data='{ {% for a in xs %} a: 1, {% endfor %} common() {} }'></div>"""
        names = [name for _, name in template_units(source)]
        self.assertTrue(any("análisis JS pendiente" in name for name in names))

    def test_repository_jinja_components_extract_callbacks(self):
        from pathlib import Path

        source = Path("cacao_accounting/templates/party_company_settings_form.html").read_text(encoding="utf-8")
        units = template_units(source)
        for component_line in (117, 201, 247):
            names = [name for _, name in units if f"componente Alpine [línea {component_line}," in name]
            self.assertTrue(any(name.endswith(".filters.company()") for name in names))
            self.assertTrue(any(name.endswith(".onSelect()") for name in names))
        self.assertFalse(any("análisis JS pendiente" in name for _, name in units))


if __name__ == "__main__":
    unittest.main()
