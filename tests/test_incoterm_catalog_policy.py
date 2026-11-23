# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1959: el catálogo de Incoterms es la única fuente; no hay fallback estático."""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Incoterm, database
from cacao_accounting.logistics import incoterm_options, validate_incoterm


@pytest.fixture
def incoterm_app():
    """App aislada sin catálogo sembrado para cada escenario."""
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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_sin_catalogo_no_hay_opciones_ni_se_acepta_incoterm(incoterm_app):
    """Sin catálogo se rechaza el código en lugar de reactivar la lista estática."""
    with incoterm_app.app_context():
        assert incoterm_options() == []
        with pytest.raises(ValueError, match="no está disponible"):
            validate_incoterm({"incoterm_code": "EXW"})


def test_catalogo_solo_inactivo_no_habilita_el_codigo(incoterm_app):
    """Un catálogo sin términos activos se comporta como ausente."""
    with incoterm_app.app_context():
        database.session.add(Incoterm(code="EXW", version="2020", name="Ex Works", is_active=False))
        database.session.commit()

        assert incoterm_options() == []
        with pytest.raises(ValueError, match="no está disponible"):
            validate_incoterm({"incoterm_code": "EXW"})


def test_solo_los_activos_del_catalogo_estan_disponibles(incoterm_app):
    """El código activo pasa; el inactivo del mismo catálogo se rechaza."""
    with incoterm_app.app_context():
        database.session.add_all(
            [
                Incoterm(code="FOB", version="2020", name="Free on Board", is_active=True),
                Incoterm(code="EXW", version="2020", name="Ex Works", is_active=False),
            ]
        )
        database.session.commit()

        opciones = incoterm_options()
        assert [opcion["code"] for opcion in opciones] == ["FOB"]
        validate_incoterm({"incoterm_code": "FOB"})
        with pytest.raises(ValueError, match="no está disponible"):
            validate_incoterm({"incoterm_code": "EXW"})
