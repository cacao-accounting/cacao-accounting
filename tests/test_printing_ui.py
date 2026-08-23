# SPDX-License-Identifier: Apache-2.0

"""Tests for printing controls rendered by the web interface."""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask, render_template_string


@pytest.fixture()
def app():
    """Create a minimal application for rendering printing controls."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parents[1] / "cacao_accounting" / "templates"),
    )
    app.config["TESTING"] = True
    app.config["MODO_ESCRITORIO"] = False
    app.jinja_env.globals["is_desktop_mode"] = lambda: bool(app.config["MODO_ESCRITORIO"])
    app.jinja_env.globals["_"] = lambda value: value
    app.add_url_rule("/preview", endpoint="printing_public.preview_document")
    app.add_url_rule("/pdf", endpoint="printing_public.document_pdf")
    return app


def _render_print_button(app, desktop: bool) -> str:
    """Render the document print macro for the requested runtime mode."""
    app.config["MODO_ESCRITORIO"] = desktop
    with app.test_request_context():
        return render_template_string(
            "{% from 'macros.html' import document_print_button %}" "{{ document_print_button('sales_invoice', 'INV-001') }}"
        )


def test_pdf_button_is_hidden_in_desktop_mode(app) -> None:
    """Desktop mode must not expose the WeasyPrint-backed PDF export link."""
    rendered = _render_print_button(app, desktop=True)

    assert "document_pdf" not in rendered
    assert "Imprimir / Vista previa" in rendered


def test_pdf_button_is_available_in_cloud_mode(app) -> None:
    """Cloud mode continues to expose the PDF export link."""
    rendered = _render_print_button(app, desktop=False)

    assert "/pdf" in rendered
    assert "Descargar PDF" in rendered
