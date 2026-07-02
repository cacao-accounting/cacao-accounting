# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Validadores para plantillas de impresión."""

import re
from typing import Optional
from cacao_accounting.printing.exceptions import TemplateValidationError


def validate_template_security(template_body: str) -> None:
    """Valida que la plantilla no contenga elementos prohibidos."""
    # Check for <script>
    if re.search(r"<script", template_body, re.IGNORECASE):
        raise TemplateValidationError("Las plantillas no pueden contener etiquetas <script>.")

    # Check for inline events
    forbidden_events = [
        "onclick",
        "onload",
        "onerror",
        "onmouseover",
        "onfocus",
        "onsubmit",
    ]
    for event in forbidden_events:
        if re.search(rf"\b{event}\s*=", template_body, re.IGNORECASE):
            raise TemplateValidationError(f"El atributo '{event}' no está permitido.")


def validate_css_safety(stylesheet_body: Optional[str]) -> None:
    """Valida que el CSS sea seguro."""
    if not stylesheet_body:
        return

    # Basic check for expression() or other dynamic CSS
    if "expression(" in stylesheet_body.lower():
        raise TemplateValidationError("Dynamic CSS expressions are not allowed.")
