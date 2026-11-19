# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2256/#setup: el setup inicial parte de SETUP_COMPLETE=False."""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import CacaoConfig, Currency, Entity, database
from cacao_accounting.setup.service import finalize_setup


def test_finalize_setup_reemplaza_el_false_de_la_carga_base():
    """La fila False creada por `db init` no simula un setup ya completado."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                CacaoConfig(key="SETUP_COMPLETE", value="False"),
            ]
        )
        database.session.commit()

        finalize_setup(
            {
                "id": "SETUPCO",
                "razon_social": "Setup Co SA",
                "nombre_comercial": "Setup Co",
                "id_fiscal": "J-SETUPCO",
                "tipo_entidad": "Sociedad Anonima",
                "moneda": "NIO",
                "pais": "NI",
                "inicio_anio_fiscal": date(2026, 1, 1),
                "fin_anio_fiscal": date(2026, 12, 31),
            },
            "en_cero",
            "NI",
            "en",
            None,
        )
        database.session.commit()

        assert database.session.execute(database.select(Entity.code).filter_by(code="SETUPCO")).scalar_one() == "SETUPCO"
        assert (
            database.session.execute(database.select(CacaoConfig.value).filter_by(key="SETUP_COMPLETE")).scalar_one() == "True"
        )
        database.session.remove()
        database.engine.dispose()
