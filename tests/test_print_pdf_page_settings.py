# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1930: el PDF respeta el tamaño y la orientación configurados."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cacao_accounting.printing.service import PrintService


def _template(paper_size: str = "letter", orientation: str = "portrait") -> SimpleNamespace:
    """Construye una plantilla mínima para el servicio de impresión."""
    return SimpleNamespace(
        template_body="<p>Documento</p>",
        stylesheet_body="@page { size: letter portrait; margin: 15mm; }",
        paper_size=paper_size,
        orientation=orientation,
    )


def test_la_regla_configurada_gana_al_css_de_la_plantilla():
    """La regla inyectada se emite después del CSS persistido."""
    html = PrintService().build_print_html(
        "<p>Documento</p>",
        "@page { size: letter portrait; margin: 15mm; }",
        paper_size="a4",
        orientation="landscape",
    )

    assert html.index("size: letter portrait") < html.index("size: A4 landscape")


def test_valores_predeterminados_son_letter_portrait():
    """Sin configuración explícita se conserva el formato histórico."""
    html = PrintService().build_print_html("<p>Documento</p>", "")

    assert "size: letter portrait" in html


@pytest.mark.parametrize(("paper_size", "orientation"), [("b5", "portrait"), ("a4", "diagonal")])
def test_valores_invalidos_se_rechazan(paper_size, orientation):
    """Un tamaño u orientación desconocidos no llegan al render."""
    with pytest.raises(ValueError, match="no soportad"):
        PrintService().build_print_html("<p>Documento</p>", "", paper_size=paper_size, orientation=orientation)


def test_validate_template_rechaza_configuracion_invalida():
    """La validación de plantilla aplica el mismo contrato de página."""
    with pytest.raises(ValueError, match="no soportad"):
        PrintService().validate_template("<p>Documento</p>", "", "unknown", paper_size="b5")


def test_render_pdf_usa_la_configuracion_de_la_plantilla(monkeypatch):
    """`render_pdf` entrega al motor la página configurada en la plantilla."""
    service = PrintService()
    capturado: dict[str, str] = {}
    monkeypatch.setattr(service, "_build_context", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "resolve_template", lambda *args, **kwargs: _template("a4", "landscape"))
    monkeypatch.setattr(service, "_template_bank_account_id", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "log_print_job", lambda **kwargs: None)

    def _capture(html: str) -> bytes:
        capturado["html"] = html
        return b"%PDF-1.7"

    monkeypatch.setattr(service, "_render_pdf_document", _capture)

    pdf = service.render_pdf("unknown_document", "doc-1", object(), "cacao")

    assert pdf == b"%PDF-1.7"
    assert "size: A4 landscape" in capturado["html"]


def test_preview_usa_la_configuracion_de_la_plantilla(monkeypatch):
    """El preview HTML refleja la misma página que el PDF."""
    service = PrintService()
    monkeypatch.setattr(service, "_build_context", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "resolve_template", lambda *args, **kwargs: _template("letter", "landscape"))
    monkeypatch.setattr(service, "_template_bank_account_id", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "log_print_job", lambda **kwargs: None)

    html = service.render_preview_html(
        "unknown_document",
        "doc-1",
        object(),
        "cacao",
        sample=True,
    )

    assert "size: letter landscape" in html
