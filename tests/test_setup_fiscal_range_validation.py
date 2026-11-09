# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El asistente de setup rechaza rangos fiscales invertidos.

Escenario de negocio (issue #1952): el formulario solo validaba formato y el
rango invertido llegaba a la creación del año fiscal, provocando HTTP 500.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.setup.forms import SetupCompanyForm


def _crear_app():
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def _datos(**overrides) -> dict[str, str]:
    datos = {
        "id": "CACAO",
        "razon_social": "Cacao SA",
        "nombre_comercial": "Cacao",
        "id_fiscal": "J0001",
        "tipo_entidad": "Asociación",
        "catalogo": "en_cero",
        "inicio_anio_fiscal": "2026-01-01",
        "fin_anio_fiscal": "2026-12-31",
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("inicio", "fin", "valido"),
    [("2026-12-31", "2026-01-01", False), ("2026-01-01", "2026-12-31", True)],
)
def test_formulario_valida_el_orden_fiscal(inicio, fin, valido):
    """#1952: el formulario rechaza inicio posterior al fin."""
    application = _crear_app()
    try:
        with application.test_request_context(
            "/setup", method="POST", data=_datos(inicio_anio_fiscal=inicio, fin_anio_fiscal=fin)
        ):
            formulario = SetupCompanyForm(language="es")
            resultado = formulario.validate()

            assert resultado is valido
            if not valido:
                assert "La fecha final no puede ser anterior" in formulario.fin_anio_fiscal.errors[0]
    finally:
        with application.app_context():
            from cacao_accounting.database import database

            database.session.remove()
            database.engine.dispose()


def test_mensaje_localizado_en_ingles():
    """#1952: el setup en inglés devuelve el error en su idioma."""
    application = _crear_app()
    try:
        with application.test_request_context(
            "/setup",
            method="POST",
            data=_datos(inicio_anio_fiscal="2026-12-31", fin_anio_fiscal="2026-01-01"),
        ):
            formulario = SetupCompanyForm(language="en")
            assert formulario.validate() is False
            assert "end date cannot be earlier" in formulario.fin_anio_fiscal.errors[0]
    finally:
        with application.app_context():
            from cacao_accounting.database import database

            database.session.remove()
            database.engine.dispose()


def test_el_handler_no_invoca_finalize_con_rango_invertido(monkeypatch):
    """#1952: el paso de compañía no inicia la creación ni responde 500."""
    from cacao_accounting.setup import _handle_setup_company_step

    application = _crear_app()
    try:
        llamadas: list[object] = []
        monkeypatch.setattr("cacao_accounting.setup.finalize_setup", lambda *args, **kwargs: llamadas.append(args))
        with application.test_request_context(
            "/setup",
            method="POST",
            data=_datos(inicio_anio_fiscal="2026-12-31", fin_anio_fiscal="2026-01-01"),
        ):
            resultado = _handle_setup_company_step({"idioma": "es", "pais": "NI"})

            assert resultado is None
            assert llamadas == []
    finally:
        with application.app_context():
            from cacao_accounting.database import database

            database.session.remove()
            database.engine.dispose()
