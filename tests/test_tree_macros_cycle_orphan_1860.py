# SPDX-License-Identifier: Apache-2.0
"""#1860: render_tree debe tolerar ciclos y mostrar huérfanos sin 500."""

from __future__ import annotations

from flask import render_template_string


def _render(app, roots, all_nodes):
    tpl = """
    {% from 'contabilidad/tree_macros.html' import render_tree with context %}
    {{ render_tree(roots, all_nodes, parent_key='parent', id_key='id', icon='bi-folder') }}
    """
    with app.test_request_context("/"):
        return render_template_string(tpl, roots=roots, all_nodes=all_nodes)


def test_render_tree_detects_cycle_without_500(app):
    """Un ciclo A->B->A no debe romper el render y debe mostrar diagnóstico."""
    a = {"id": "A", "code": "A", "name": "Nodo A", "parent": "B", "url": "/a", "badges": []}
    b = {"id": "B", "code": "B", "name": "Nodo B", "parent": "A", "url": "/b", "badges": []}
    html = _render(app, roots=[], all_nodes=[a, b])
    assert "Nodo A" in html or "Nodo B" in html
    assert "Ciclo jerárquico" in html
    assert "RecursionError" not in html


def test_render_tree_shows_orphan_with_warning(app):
    """Nodo cuyo padre no existe no debe desaparecer silenciosamente."""
    orphan = {
        "id": "O1",
        "code": "O1",
        "name": "Nodo huérfano",
        "parent": "MISSING",
        "url": "/o1",
        "badges": [],
    }
    html = _render(app, roots=[], all_nodes=[orphan])
    assert "Nodo huérfano" in html
    assert "Padre no encontrado" in html


def test_render_tree_preserves_valid_hierarchy(app):
    """árbol válido conserva jerarquía y no muestra diagnósticos falsos."""
    root = {"id": "R", "code": "R", "name": "Raíz", "parent": None, "url": "/r", "badges": []}
    child = {"id": "C", "code": "C", "name": "Hijo", "parent": "R", "url": "/c", "badges": []}
    html = _render(app, roots=[root], all_nodes=[root, child])
    assert "Raíz" in html
    assert "Hijo" in html
    assert "Ciclo jerárquico" not in html
    assert "Padre no encontrado" not in html
