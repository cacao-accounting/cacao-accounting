# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Valida traducciones i18n para mensajes de flujo documental."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from flask import Flask
from flask_babel import Babel, gettext

TRANSLATIONS_DIR = Path(__file__).resolve().parents[1] / "cacao_accounting" / "translations"


@pytest.fixture
def english_gettext() -> Callable[[str], str]:
    """Construye un traductor con locale inglés para validar msgid críticos."""
    app = Flask(__name__)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(TRANSLATIONS_DIR)
    Babel(app, locale_selector=lambda: "en")

    def _translate(message: str) -> str:
        with app.test_request_context():
            return gettext(message)

    return _translate


@pytest.mark.parametrize(
    ("msgid", "expected"),
    [
        (
            "La referencia de documento fuente está incompleta.",
            "The source document reference is incomplete.",
        ),
        (
            "El parametro source debe usar formato doctype:id.",
            "The source parameter must use the doctype:id format.",
        ),
    ],
)
def test_document_flow_messages_have_english_translation(
    english_gettext: Callable[[str], str],
    msgid: str,
    expected: str,
) -> None:
    """Asegura traducciones en inglés para mensajes usados en validaciones de flujo."""
    assert english_gettext(msgid) == expected
