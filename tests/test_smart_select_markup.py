# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1976: el smart select renderizado expone roles, ARIA y acciones."""

from __future__ import annotations

from flask import render_template_string


def test_markup_smart_select_expone_roles_aria_y_acciones(app):
    """El HTML generado permite navegación accesible y selección con click."""
    with app.app_context():
        html = render_template_string(
            '{% import "smart_select_field.html" as ss %}' '{{ ss.smart_select_field("Compañía", "company", "company") }}'
        )

    assert 'role="combobox"' in html
    assert 'aria-autocomplete="list"' in html
    assert ':aria-expanded="open"' in html
    assert ":aria-activedescendant=" in html
    assert 'role="listbox"' in html
    assert 'role="option"' in html
    assert ':aria-selected="index === highlightedIndex"' in html
    assert '@mousemove="highlightedIndex = index"' in html
    assert '@click="selectOption(option)"' in html


def test_party_company_settings_inline_smart_select_usa_click_y_aria():
    """#1976: bloques inline de party company settings no usan mousedown y exponen ARIA."""
    from pathlib import Path

    tpl = Path("cacao_accounting/templates/party_company_settings_form.html").read_text(encoding="utf-8")
    assert '@mousedown.prevent="selectOption(option)"' not in tpl
    assert tpl.count('@click="selectOption(option)"') >= 5
    assert 'role="option"' in tpl
    assert 'role="listbox"' in tpl
    assert 'aria-autocomplete="list"' in tpl
