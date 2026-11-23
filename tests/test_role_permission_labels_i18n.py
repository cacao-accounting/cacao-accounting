# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1907: las acciones de permisos de rol se traducen al locale activo."""

from __future__ import annotations

from flask_babel import force_locale

from cacao_accounting.admin.routes import _PERMISOS_ACCIONES


def _etiquetas(app, locale: str) -> set[str]:
    with app.test_request_context("/"):
        with force_locale(locale):
            return {str(etiqueta) for _accion, etiqueta in _PERMISOS_ACCIONES}


def test_etiquetas_en_ingles(app):
    """Con locale en no queda ningún nombre de acción en español."""
    etiquetas = _etiquetas(app, "en")

    assert "Access" in etiquetas
    assert "View" in etiquetas
    assert "Acceso" not in etiquetas


def test_etiquetas_en_espanol(app):
    """El locale base conserva los nombres en español."""
    etiquetas = _etiquetas(app, "es")

    assert "Acceso" in etiquetas
