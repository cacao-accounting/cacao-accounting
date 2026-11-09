# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La selección del catálogo del setup respeta país e idioma.

Escenario de negocio (issue #2106): ``choose_catalog_file`` devolvía siempre
el catálogo base español. Una compañía creada en inglés recibía nombres de
cuenta en español aunque el asistente hubiera elegido otro idioma.
"""

from __future__ import annotations

from os.path import basename

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, database
from cacao_accounting.setup.service import choose_catalog_file, create_company


def test_selecciona_el_catalogo_segun_el_idioma():
    """Inglés y español resuelven archivos base distintos."""
    ingles = choose_catalog_file("US", "en")
    espanol = choose_catalog_file("NI", "es")

    assert basename(ingles.file) == "base_en.csv"
    assert ingles.idioma == "EN"
    assert ingles.pais == "US"
    assert basename(espanol.file) == "base_es.csv"
    assert espanol.idioma == "ES"
    assert espanol.pais == "NI"


def test_normaliza_el_idioma_recibido():
    """Un idioma en mayúsculas o regional no cambia la selección."""
    assert basename(choose_catalog_file("US", "EN").file) == "base_en.csv"
    assert basename(choose_catalog_file("US", "en_US").file) == "base_en.csv"


def test_un_archivo_explicito_conserva_el_idioma_solicitado():
    """El nombre explícito se valida y conserva país e idioma."""
    catalogo = choose_catalog_file("US", "en", "us_gaap.csv")

    assert basename(catalogo.file) == "us_gaap.csv"
    assert catalogo.pais == "US"
    assert catalogo.idioma == "EN"


def test_un_archivo_inexistente_no_se_sustituye_por_el_base():
    """Un catálogo pedido y ausente devuelve None, no el catálogo ES."""
    assert choose_catalog_file("US", "en", "no_existe.csv") is None


def test_create_company_carga_el_catalogo_del_idioma():
    """La compañía creada en inglés recibe los nombres del catálogo EN."""
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
    try:
        with application.app_context():
            database.create_all()
            database.session.add(Currency(code="USD", name="Dólar", decimals=2, active=True, default=True))
            database.session.commit()

            create_company(
                {
                    "id": "ENCO",
                    "razon_social": "English Company",
                    "nombre_comercial": "English Co",
                    "id_fiscal": "J-ENCO",
                    "moneda": "USD",
                    "pais": "US",
                    "tipo_entidad": "Sociedad Anonima",
                },
                catalogo_tipo="preexistente",
                country="US",
                idioma="en",
            )
            database.session.commit()

            nombres = set(database.session.execute(database.select(Accounts.name).filter_by(entity="ENCO")).scalars().all())
            assert "Current Assets" in nombres
            assert "Activo Corriente" not in nombres
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
