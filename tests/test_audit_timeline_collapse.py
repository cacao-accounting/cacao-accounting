# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2154: la etiqueta del colapso sigue el estado real del panel.

El control escucha los eventos `shown`/`hidden` de Bootstrap y actualiza el
texto después del toggle. No debe volver al `onclick` inline que leía el
`aria-expanded` previo.
"""

from __future__ import annotations

import re
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


# El contrato evento -> etiqueta del macro. La suite corre en Python y no
# ejecuta el navegador; estas expresiones fijan el comportamiento completo:
# qué texto muestra cada evento y qué asignación lo produce, de modo que
# intercambiar etiquetas, intercambiar asignaciones o retirar la mutación de
# `textContent` rompe la prueba.
_ETIQUETAS = re.compile(r'data-label-show="([^"]*)"\s*data-label-hide="([^"]*)"')
_AL_MOSTRAR = re.compile(
    r"panel\.addEventListener\('shown\.bs\.collapse',\s*function \(\) \{\s*"
    r"toggle\.textContent = toggle\.dataset\.labelHide;\s*\}\)",
)
_AL_OCULTAR = re.compile(
    r"panel\.addEventListener\('hidden\.bs\.collapse',\s*function \(\) \{\s*"
    r"toggle\.textContent = toggle\.dataset\.labelShow;\s*\}\)",
)


def test_la_etiqueta_resultante_sigue_el_estado_del_panel(app):
    """Al mostrar se ve «Ocultar…» y al ocultar «Ver…», sin estado previo."""
    with app.test_request_context("/"):
        html = render_template_string(
            "{% import 'macros.html' as m %}{{ m.audit_timeline(timeline, page_size=1) }}",
            timeline=[_timeline_row(), _timeline_row()],
        )

    pares = _ETIQUETAS.findall(html)
    assert pares, "El timeline debe declarar las etiquetas de ambos estados."
    for etiqueta_ver, etiqueta_ocultar in pares:
        # `label-show` es la etiqueta del estado oculto (la visible hoy);
        # `label-hide` es la del estado mostrado.
        assert etiqueta_ver.startswith("Ver"), etiqueta_ver
        assert etiqueta_ocultar.startswith("Ocultar"), etiqueta_ocultar

    eventos_mostrar = _AL_MOSTRAR.findall(html)
    eventos_ocultar = _AL_OCULTAR.findall(html)
    assert len(eventos_mostrar) == len(pares)
    assert len(eventos_ocultar) == len(pares)

    assert 'aria-expanded="false"' in html
    assert html.count('data-bs-toggle="collapse"') == len(pares)


def test_timeline_traduce_todas_las_acciones_en_ambos_idiomas(app):
    """Las 39 acciones de ALLOWED_ACTIONS tienen etiqueta real en es y en."""
    from flask_babel import force_locale

    from cacao_accounting import audit_action_label
    from cacao_accounting.audit_trail_service import ALLOWED_ACTIONS
    from cacao_accounting.i18n import _

    macro_mensajes = {
        "created": "creó este documento",
        "updated": "editó este documento",
        "submitted": "contabilizó este documento",
        "approved": "aprobó este documento",
        "cancelled": "anuló este documento",
        "rejected": "rechazó este documento",
        "reversed": "revirtió este documento",
        "reversal_draft_created": "creó un borrador de reversión",
        "commented": "agregó un comentario",
    }
    filas = [
        SimpleNamespace(
            event=SimpleNamespace(
                document_id="DOC-I18N",
                actor_name="Ana",
                action=accion,
                timestamp="2026-05-10 10:00",
                comment=None,
            ),
            changes=[],
        )
        for accion in sorted(ALLOWED_ACTIONS)
    ]
    plantilla = "{% import 'macros.html' as m %}{{ m.audit_timeline(timeline, page_size=100) }}"

    with app.test_request_context("/"):
        with force_locale("es"):
            html_es = render_template_string(plantilla, timeline=filas)
            etiquetas_es = {accion: audit_action_label(accion) for accion in ALLOWED_ACTIONS}
            macro_es = {accion: _(texto) for accion, texto in macro_mensajes.items()}
        with force_locale("en"):
            html_en = render_template_string(plantilla, timeline=filas)
            etiquetas_en = {accion: audit_action_label(accion) for accion in ALLOWED_ACTIONS}
            macro_en = {accion: _(texto) for accion, texto in macro_mensajes.items()}

    for accion in ALLOWED_ACTIONS:
        if accion in macro_mensajes:
            assert macro_es[accion] in html_es, accion
            assert macro_en[accion] in html_en, accion
            continue
        assert etiquetas_es[accion] != "acción registrada", accion
        assert etiquetas_en[accion] != "action recorded", accion
        assert etiquetas_es[accion] in html_es, accion
        assert etiquetas_en[accion] in html_en, accion
