# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2150: la carga de catálogo no confirma por su cuenta."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.ctas import cargar_catalogos
from cacao_accounting.database import Accounts, Currency, Entity, database


def test_cargar_catalogos_deja_la_transaccion_al_caller(tmp_path):
    """El catálogo se confirma o revierte con el alta completa de la compañía."""
    catalogo = tmp_path / "catalogo.csv"
    catalogo.write_text(
        "code,name,parent,group,classification,type,account_type\n"
        "1101,Caja,,False,asset,,cash\n"
        "1102,Bancos,,False,asset,,bank\n",
        encoding="utf-8",
    )
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()

        cargar_catalogos(SimpleNamespace(file=str(catalogo)), "cacao")
        session = database.session()
        assert session.in_transaction()
        session.rollback()
        assert database.session.execute(database.select(Accounts)).scalars().all() == []

        database.session.remove()
        database.engine.dispose()
