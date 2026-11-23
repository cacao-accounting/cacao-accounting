# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2131: el validador de plantillas analiza la salida renderizada."""

from __future__ import annotations

import pytest

from cacao_accounting.printing.exceptions import TemplateValidationError
from cacao_accounting.printing.validators import validate_template_security


def test_detecta_el_escape_de_jinja():
    """Validar la salida impide ocultar <script> con expresiones vacías."""
    with pytest.raises(TemplateValidationError, match="script"):
        validate_template_security("<scr{{ '' }}ipt>alert(1)</scr{{ '' }}ipt>")


def test_acepta_contenido_inerte():
    """Una plantilla sin elementos activos sigue siendo válida."""
    validate_template_security("<p>{{ document_no }}</p>")
