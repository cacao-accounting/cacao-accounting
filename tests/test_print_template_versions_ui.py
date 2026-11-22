# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1931: el historial de versiones de plantillas se muestra bajo RBAC.

La ruta existía y cargaba los snapshots, pero ninguna vista enlazaba ni
renderizaba el historial. La regresión cubre el enlace desde el listado, el
contenido del historial y la denegación a usuarios sin rol administrativo.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate, PrintTemplateVersion


def _crear_plantilla_con_versiones() -> tuple[int, list[int]]:
    """Persiste una plantilla con dos versiones históricas."""
    suffix = uuid4().hex[:6]
    with database.session.no_autoflush:
        template = PrintTemplate(
            document_type="sales_invoice",
            code=f"TPL-{suffix}",
            name=f"Formato {suffix}",
            template_body="<h1>{{ document_no }}</h1>",
            paper_size="letter",
            orientation="portrait",
            status="published",
            is_system=False,
            is_default=False,
            version=2,
        )
        database.session.add(template)
        database.session.flush()
        versiones = [
            PrintTemplateVersion(
                template_id=template.id,
                version=1,
                template_body="<h1>v1</h1>",
                paper_size="letter",
                orientation="portrait",
                status="draft",
                change_note=f"Borrador inicial {suffix}",
            ),
            PrintTemplateVersion(
                template_id=template.id,
                version=2,
                template_body="<h1>v2</h1>",
                paper_size="a4",
                orientation="landscape",
                status="published",
                change_note=f"Publicación {suffix}",
            ),
        ]
        database.session.add_all(versiones)
        database.session.commit()
        return template.id, [version.id for version in versiones]


def test_listado_enlaza_el_historial_de_cada_formato(app, authenticated_client):
    """El listado expone el enlace al historial del formato."""
    with app.app_context():
        template_id, _ = _crear_plantilla_con_versiones()
    client = authenticated_client("admin")

    response = client.get("/admin/print-templates")

    assert response.status_code == 200
    assert f"/admin/print-templates/{template_id}/versions" in response.get_data(as_text=True)


def test_historial_renderiza_las_versiones_registradas(app, authenticated_client):
    """La ruta de historial muestra versiones, fechas y notas."""
    with app.app_context():
        template_id, _ = _crear_plantilla_con_versiones()
        suffix = database.session.get(PrintTemplate, template_id).code.removeprefix("TPL-")
    client = authenticated_client("admin")

    response = client.get(f"/admin/print-templates/{template_id}/versions")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Historial de versiones" in body
    assert f"Borrador inicial {suffix}" in body
    assert f"Publicación {suffix}" in body
    assert "a4" in body
    assert "landscape" in body


def test_historial_niega_usuarios_sin_rol_administrativo(app, authenticated_client):
    """Un usuario sin rol administrativo no accede al historial."""
    with app.app_context():
        template_id, _ = _crear_plantilla_con_versiones()
    client = authenticated_client("writer")

    response = client.get(f"/admin/print-templates/{template_id}/versions")

    assert response.status_code == 403
