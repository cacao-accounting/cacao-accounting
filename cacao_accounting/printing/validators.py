# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Validadores para plantillas de impresión."""

import re
from html.parser import HTMLParser
from typing import Optional

from cacao_accounting.printing.exceptions import TemplateValidationError


from cacao_accounting.i18n import _


class _PrintTemplateSecurityParser(HTMLParser):
    """Capture active HTML features that are unsafe in printable templates."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.violation: tuple[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record the first active tag, event handler, or executable URL."""
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "iframe", "object", "embed"}:
            self.violation = ("element", normalized_tag)
            return

        for name, value in attrs:
            normalized_name = name.lower()
            if normalized_name.startswith("on"):
                self.violation = ("event", normalized_name)
                return
            url_attributes = {"href", "src", "action", "formaction", "xlink:href"}
            if normalized_name in url_attributes and _has_executable_url(value):
                self.violation = ("url", normalized_name)
                return


def _has_executable_url(value: str | None) -> bool:
    """Detect JavaScript and VBScript URL schemes after browser whitespace handling."""
    if not value:
        return False
    compact_value = re.sub(r"[\x00-\x20]+", "", value).lower()
    return compact_value.startswith(("javascript:", "vbscript:"))


def validate_template_security(template_body: str) -> None:
    """Valida que la plantilla no contenga elementos prohibidos."""
    if re.search(r"<!\s*\[\s*cdata\s*\[", template_body, re.IGNORECASE):
        raise TemplateValidationError(_("Las secciones CDATA no están permitidas en plantillas HTML."))
    ambiguous_comment_endings = r"<!--(?:.*?)--!>|<!-->|<!--->"
    if re.search(ambiguous_comment_endings, template_body, re.DOTALL):
        raise TemplateValidationError(_("Los delimitadores de comentario HTML ambiguos no están permitidos."))

    parser = _PrintTemplateSecurityParser()
    parser.feed(template_body)
    if parser.violation is None:
        return

    violation_type, value = parser.violation
    if violation_type == "event":
        raise TemplateValidationError(_("El atributo '%(event)s' no está permitido.") % {"event": value})
    if violation_type == "element":
        raise TemplateValidationError(_("El elemento HTML '%(element)s' no está permitido.") % {"element": value})
    raise TemplateValidationError(_("No se permiten URLs con esquemas ejecutables."))


def validate_css_safety(stylesheet_body: Optional[str]) -> None:
    """Valida que el CSS sea seguro."""
    if not stylesheet_body:
        return

    if re.search(r"</style(?=$|[\t\n\f\r />])", stylesheet_body, re.IGNORECASE):
        raise TemplateValidationError(_("El CSS no puede cerrar el elemento <style>."))

    # Basic check for expression() or other dynamic CSS
    if "expression(" in stylesheet_body.lower():
        raise TemplateValidationError(_("Dynamic CSS expressions are not allowed."))
