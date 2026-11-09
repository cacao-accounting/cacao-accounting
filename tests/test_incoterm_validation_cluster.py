# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Incoterms activos y propagación de contexto Jinja.

Escenario de negocio:
- #1959: el fallback reactivaba términos cuando el catálogo estaba inactivo.
- #1961: la macro logística se importaba sin contexto y no veía las opciones.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import render_template_string
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Incoterm, database
from cacao_accounting.logistics import incoterm_options, validate_incoterm


def _crear_app():
    application = create_app(
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
    with application.app_context():
        database.create_all()
    return application


def test_sin_catalogo_usa_los_codigos_estaticos():
    """#1959: el fallback solo aplica cuando no hay filas configuradas."""
    application = _crear_app()
    try:
        with application.app_context():
            assert len(incoterm_options()) == 11
            validate_incoterm({"incoterm_code": "EXW", "incoterm_version": "2020"})
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_catalogo_inactivo_no_rehabilita_el_fallback():
    """#1959: si existen filas, solo cuentan las activas."""
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add(Incoterm(code="EXW", version="2020", name="Ex Works", is_active=False))
            database.session.commit()

            assert incoterm_options() == []
            with pytest.raises(ValueError, match="no está disponible"):
                validate_incoterm({"incoterm_code": "EXW", "incoterm_version": "2020"})
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_catalogo_mixto_solo_ofrece_activos():
    """#1959: un término activo convive con otros desactivados sin reactivarlos."""
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add_all(
                [
                    Incoterm(code="FOB", version="2020", name="Free on Board", is_active=True),
                    Incoterm(code="EXW", version="2020", name="Ex Works", is_active=False),
                ]
            )
            database.session.commit()

            assert [option["code"] for option in incoterm_options()] == ["FOB"]
            validate_incoterm({"incoterm_code": "FOB", "incoterm_version": "2020"})
            with pytest.raises(ValueError, match="no está disponible"):
                validate_incoterm({"incoterm_code": "EXW", "incoterm_version": "2020"})
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_macro_logistica_recibe_las_opciones_con_contexto():
    """#1961: el import con contexto permite renderizar los Incoterms."""
    application = _crear_app()
    try:
        with application.test_request_context("/"):
            html = render_template_string(
                '{% import "transaction_form_macros.html" as tf with context %}{{ tf.logistics_section() }}',
                incoterm_options=[{"code": "EXW", "label": "Ex Works", "version": "2020"}],
            )

            assert 'value="EXW"' in html
            assert "Ex Works" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_todos_los_imports_de_la_macro_usan_contexto():
    """#1961: ningún formulario vuelve a importar la macro sin contexto."""
    pendientes = [
        str(path)
        for path in Path("cacao_accounting").rglob("*.html")
        if 'import "transaction_form_macros.html" as tf_macros %}' in path.read_text(encoding="utf-8")
    ]
    assert pendientes == []
