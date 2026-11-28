# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1923: la URL de retorno de la vista previa no puede salir del sitio."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from flask import url_for

from cacao_accounting.printing.routes import _safe_return_url


@pytest.fixture
def app_preview():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    yield application
    with application.app_context():
        from cacao_accounting.database import database

        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize(
    "valor",
    [
        "//evil.example/path",
        r"/\evil.example/path",
        "/%5Cevil.example/path",
        "https://evil.example/path",
        "javascript:alert(1)",
        "/ruta\x00con-control",
        "",
        None,
    ],
)
def test_rechaza_destinos_inseguros(app_preview, valor):
    """Todo destino externo, esquema o barra invertida cae al inicio."""
    with app_preview.test_request_context("/"):
        assert _safe_return_url(valor) == url_for("cacao_app.pagina_inicio")


def test_conserva_rutas_internas(app_preview):
    """Una ruta interna legítima se conserva para volver al comprobante."""
    with app_preview.test_request_context("/"):
        assert _safe_return_url("/accounting/journal/ABC") == "/accounting/journal/ABC"
