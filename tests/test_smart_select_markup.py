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
