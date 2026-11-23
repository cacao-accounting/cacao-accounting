# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1968: ninguna acción de auditoría permitida se muestra como código crudo."""

from __future__ import annotations

from pathlib import Path

from cacao_accounting import audit_action_label
from cacao_accounting.audit_trail_service import ALLOWED_ACTIONS

RAIZ = Path(__file__).resolve().parents[1]


def test_toda_accion_permitida_tiene_etiqueta(app):
    """Cada acción de ALLOWED_ACTIONS deja de mostrarse como identificador."""
    with app.test_request_context("/"):
        for accion in sorted(ALLOWED_ACTIONS):
            etiqueta = audit_action_label(accion)
            assert etiqueta != accion, accion
            assert "_" not in etiqueta, (accion, etiqueta)


def test_el_catalogo_tiene_traduccion_para_cada_etiqueta(app):
    """Las etiquetas nuevas existen en el catálogo inglés."""
    catalogo = (RAIZ / "cacao_accounting" / "translations" / "en" / "LC_MESSAGES" / "messages.po").read_text(
        encoding="utf-8"
    )
    with app.test_request_context("/"):
        for accion in sorted(ALLOWED_ACTIONS):
            etiqueta = audit_action_label(accion)
            assert f'msgid "{etiqueta}"' in catalogo, etiqueta
