# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La etiqueta del colapso de auditoría sigue el estado posterior.

Escenario de negocio (issue #2154): el onclick inline leía aria-expanded antes
de que Bootstrap completara show()/hide(), por lo que la etiqueta quedaba
invertida. La etiqueta debe actualizarse en los eventos shown/hidden.
"""

from __future__ import annotations

from types import SimpleNamespace


def _evento(indice: int) -> SimpleNamespace:
    return SimpleNamespace(
        event=SimpleNamespace(
            actor_name="Ana",
            actor_user_id="ana",
            action="created",
            timestamp=f"2026-10-15 10:{indice:02d}",
            document_id="DOC-1",
            comment=None,
        ),
        changes=[],
    )


def test_el_toggle_usa_los_eventos_de_bootstrap(app):
    """No depende del onclick previo y escucha shown/hidden."""
    timeline = [_evento(indice) for indice in range(25)]

    with app.test_request_context("/accounting/journal"):
        html = app.jinja_env.get_template("macros.html").module.audit_timeline(timeline)

    assert "onclick=" not in html
    assert "shown.bs.collapse" in html
    assert "hidden.bs.collapse" in html
    assert "data-label-hide" in html
    assert "data-label-show" in html
