# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El CSS de plantillas de impresión no puede escapar del elemento style."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from unittest.mock import Mock

from cacao_accounting.printing.exceptions import TemplateValidationError
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.validators import validate_template_security

CSS_MALICIOSO = "</style><script>window.__print_css_xss__ = true</script><style>"


@pytest.mark.parametrize("stylesheet", [CSS_MALICIOSO, "</STYLE   ><script>alert(1)</script>", "</style"])
def test_validacion_completa_rechaza_cierre_de_style(stylesheet):
    """El guard CSS rechaza delimitadores de cierre, sin importar mayúsculas o espacios."""
    with pytest.raises(TemplateValidationError):
        PrintService().validate_template("<p>Invoice</p>", stylesheet, "sales_invoice")


@pytest.mark.parametrize(
    "template_body",
    [
        '<img src="/missing" onpointerover="alert(1)">',
        '<a href="java&#x73;cript:alert(1)">Open</a>',
        '<iframe src="/internal"></iframe>',
        "<scr{{ '' }}ipt>alert(1)</scr{{ '' }}ipt>",
        "<![CDATA[><script>alert(1)</script>]]>",
        "<!-- --!><script>alert(1)</script>",
        "<!--><script>alert(1)</script>",
        "<!---><script>alert(1)</script>",
    ],
)
def test_validacion_completa_rechaza_html_activo(template_body):
    """La validación detecta eventos, URLs ejecutables y Jinja que renderiza tags activos."""
    with pytest.raises(TemplateValidationError):
        PrintService().validate_template(template_body, "", "sales_invoice")


def test_vista_previa_conserva_contenido_pasivo():
    """El contenido normal de impresión, incluyendo imágenes, sigue permitido."""
    body = '<img src="/logo.png" alt>'
    validate_template_security(body)
    html = PrintService().build_print_html(body, ".print-document { color: #333; }")

    assert body in html
    assert ".print-document { color: #333; }" in html


@pytest.mark.parametrize("stylesheet_body", [CSS_MALICIOSO, "</style"])
def test_vista_previa_rechaza_css_malicioso_ya_guardado(monkeypatch, stylesheet_body):
    """La generación de la vista previa vuelve a validar CSS de plantillas persistidas."""
    service = PrintService()
    template = SimpleNamespace(template_body="<p>Invoice</p>", stylesheet_body=stylesheet_body)
    log_job = Mock()
    monkeypatch.setattr(service, "_build_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "resolve_template", lambda *_args, **_kwargs: template)
    monkeypatch.setattr(service, "log_print_job", log_job)

    with pytest.raises(TemplateValidationError):
        service.render_preview_html("sales_invoice", "invoice-1", object(), "cacao")

    assert log_job.call_args.kwargs["success"] is False


def test_validacion_rechaza_cdata_con_tags_activos_ocultos():
    """El parser HTML5 trata CDATA como comentario y expone tags dentro del body."""
    with pytest.raises(TemplateValidationError):
        validate_template_security("<![CDATA[><script>alert(1)</script>]]>")
