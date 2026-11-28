# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1928: las vistas administrativas de impresión renderizan su contenido.

Las plantillas deben extender el bloque ``contenido`` del layout base; un
HTTP 200 con el layout vacío no es suficiente. La regresión verifica los
controles propios de lista, alta/edición y configuración.
"""

from __future__ import annotations


def test_lista_de_formatos_renderiza_sus_controles(authenticated_client):
    """El listado incluye los enlaces de alta y configuración."""
    client = authenticated_client("admin")

    response = client.get("/admin/print-templates")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/admin/print-templates/new" in body
    assert "/admin/print-templates/settings" in body


def test_formulario_de_formato_renderiza_sus_campos(authenticated_client):
    """El alta muestra el cuerpo de plantilla y la hoja de estilos."""
    client = authenticated_client("admin")

    response = client.get("/admin/print-templates/new")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="template_body"' in body
    assert 'name="stylesheet_body"' in body
    assert 'name="csrf_token"' in body


def test_configuracion_de_validacion_renderiza_sus_controles(authenticated_client):
    """La configuración expone el interruptor y la URL base de validación."""
    client = authenticated_client("admin")

    response = client.get("/admin/print-templates/settings")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="external_document_validation_enabled"' in body
    assert 'name="external_document_validation_base_url"' in body
