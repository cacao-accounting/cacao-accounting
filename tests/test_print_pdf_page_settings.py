# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1930: el PDF respeta el tamaño y la orientación configurados."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from cacao_accounting.database import database
from cacao_accounting.printing.exceptions import TemplateValidationError
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.service import PrintService


def _template(paper_size: str = "letter", orientation: str = "portrait") -> SimpleNamespace:
    """Construye una plantilla mínima para el servicio de impresión."""
    return SimpleNamespace(
        template_body="<p>Documento</p>",
        stylesheet_body="@page { margin: 15mm; }",
        paper_size=paper_size,
        orientation=orientation,
    )


@pytest.mark.parametrize(
    "stylesheet",
    [
        "@page { size: letter portrait; margin: 15mm; }",
        "@page { size: A4 landscape !important; }",
        "@page { /**/size: A4 landscape !important; }",
        "@page :first { size: A4 landscape; }",
    ],
)
def test_css_de_plantilla_no_puede_definir_el_tamano_de_pagina(stylesheet):
    """El CSS persistido no puede imponerse a la p?gina configurada (#1930)."""
    with pytest.raises(TemplateValidationError, match="tama?o de p?gina|tama"):
        PrintService().build_print_html("<p>Documento</p>", stylesheet, paper_size="a4", orientation="landscape")

def test_margenes_del_css_no_alteran_la_pagina_configurada():
    """Un @page sin `size` conserva márgenes y la configuración se aplica después."""
    html = PrintService().build_print_html(
        "<p>Documento</p>",
        "@page { margin: 15mm; }",
        paper_size="a4",
        orientation="landscape",
    )

    assert "margin: 15mm" in html
    assert "size: A4 landscape" in html
    assert html.rindex("size: A4 landscape") > html.index("margin: 15mm")


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
    with pytest.raises(TemplateValidationError, match="no soportad"):
        PrintService().validate_template("<p>Documento</p>", "", "unknown", paper_size="b5")


@pytest.mark.parametrize("endpoint", ["/admin/print-templates/new", "/admin/print-templates/{template_id}/edit"])
@pytest.mark.parametrize(("paper_size", "orientation"), [("b5", "portrait"), ("letter", "diagonal")])
def test_rutas_admin_muestran_error_controlado_para_pagina_invalida(
    app, authenticated_client, endpoint, paper_size, orientation
):
    """Alta y edición rechazan settings manipulados sin responder con HTTP 500."""
    client = authenticated_client("admin")
    with app.app_context():
        template = PrintTemplate(
            document_type="sales_invoice",
            code=f"invalid-page-{endpoint.rsplit('/', 1)[-1]}-{id(app)}",
            name="Invalid page setting test",
            template_body="<p>Documento</p>",
            stylesheet_body="",
            created_by=None,
        )
        database.session.add(template)
        database.session.commit()
        template_id = template.id
        code = template.code

    response = client.post(
        endpoint.format(template_id=template_id) if "{template_id}" in endpoint else endpoint,
        data={
            "document_type": "sales_invoice",
            "code": code,
            "name": "Invalid page setting test",
            "template_body": "<p>Documento</p>",
            "stylesheet_body": "",
            "paper_size": paper_size,
            "orientation": orientation,
        },
    )

    assert response.status_code == 200
    assert b"no soportad" in response.data.lower()
    with app.app_context():
        persisted = database.session.get(PrintTemplate, template_id)
        assert persisted is not None
        assert persisted.paper_size == "letter"


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


def _pdf_disponible() -> bool:
    """Indica si WeasyPrint puede generar PDFs en este entorno."""
    try:
        from weasyprint import HTML

        HTML(string="<p>prueba</p>").write_pdf()
    except Exception:
        return False
    return True


def _extraer_mediabox(pdf: bytes) -> tuple[int, int] | None:
    """Extrae MediaBox aunque venga como referencia indirecta."""
    caja_directa = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", pdf)
    if caja_directa:
        return int(float(caja_directa.group(1))), int(float(caja_directa.group(2)))
    ref = re.search(rb"/MediaBox\s+(\d+)\s+(\d+)\s+R", pdf)
    if not ref:
        return None
    obj = re.search(
        rb"%s\s+%s\s+obj\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]\s*endobj"
        % (re.escape(ref.group(1)), re.escape(ref.group(2))),
        pdf,
    )
    if not obj:
        return None
    return int(float(obj.group(1))), int(float(obj.group(2)))


@pytest.mark.skipif(not _pdf_disponible(), reason="WeasyPrint sin librerías nativas; CI Linux cubre el PDF")
@pytest.mark.parametrize(
    ("paper_size", "orientation", "ancho", "alto"),
    [("letter", "portrait", 612, 792), ("a4", "landscape", 842, 595)],
)
def test_pdf_real_usa_las_dimensiones_configuradas(paper_size, orientation, ancho, alto):
    """El PDF generado expone el MediaBox del tamaño y orientación elegidos."""
    service = PrintService()
    html = service.build_print_html(
        "<p>Documento</p>",
        "@page { margin: 15mm; }",
        paper_size=paper_size,
        orientation=orientation,
    )

    pdf = service._render_pdf_document(html)

    caja = _extraer_mediabox(pdf)
    if caja is None:
        pytest.skip("El PDF generado no expone MediaBox legible en este entorno.")
    assert caja[0] == ancho
    assert caja[1] == alto
