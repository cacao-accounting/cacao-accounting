# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2154: la etiqueta del colapso sigue el estado real del panel.

El control escucha los eventos `shown`/`hidden` de Bootstrap y actualiza el
texto después del toggle. No debe volver al `onclick` inline que leía el
`aria-expanded` previo.
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template_string


def _timeline_row() -> SimpleNamespace:
    """Construye una fila mínima del timeline de auditoría."""
    return SimpleNamespace(
        event=SimpleNamespace(
            document_id="DOC-TIMELINE",
            actor_name="Ana",
            action="created",
            timestamp="2026-05-10 10:00",
            comment=None,
        ),
        changes=[],
    )


def test_colapso_de_eventos_anteriores_actualiza_etiqueta_tras_el_toggle(app):
    """La etiqueta se actualiza en shown/hidden y no con el estado previo."""
    with app.test_request_context("/"):
        html = render_template_string(
            "{% import 'macros.html' as m %}{{ m.audit_timeline(timeline, page_size=1) }}",
            timeline=[_timeline_row(), _timeline_row()],
        )

    assert "onclick=" not in html
    assert "shown.bs.collapse" in html
    assert "hidden.bs.collapse" in html
    assert "data-label-show=" in html
    assert "data-label-hide=" in html
