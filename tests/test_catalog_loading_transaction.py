# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2150: la carga de catálogo no confirma por su cuenta."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.ctas import cargar_catalogos
from cacao_accounting.contabilidad.default_accounts import DefaultAccountError
from cacao_accounting.database import Accounts, Book, Currency, Entity, database
from cacao_accounting.setup import service
from cacao_accounting.setup.service import finalize_setup


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


def test_alta_compania_carga_catalogo_csv_seleccionado():
    """El alta de compañía selecciona y carga el CSV operativo sin depender del ODS."""
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.commit()

        finalize_setup(
            {
                "id": "CSVCO",
                "razon_social": "CSV Company SA",
                "nombre_comercial": "CSV Company",
                "id_fiscal": "J-CSVC0",
                "tipo_entidad": "Sociedad Anonima",
                "moneda": "NIO",
                "pais": "NI",
                "inicio_anio_fiscal": date(2026, 1, 1),
                "fin_anio_fiscal": date(2026, 12, 31),
            },
            "preexistente",
            "NI",
            "es",
            "base_es.csv",
        )

        entity = database.session.execute(database.select(Entity).filter_by(code="CSVCO")).scalar_one()
        accounts = database.session.execute(database.select(Accounts).filter_by(entity="CSVCO")).scalars().all()
        assert entity.country == "NI"
        assert len(accounts) > 0
        assert any(account.code == "11.01.001.001" for account in accounts)
        database.session.remove()
        database.engine.dispose()


def test_finalizacion_revierte_compania_si_falla_mapping(monkeypatch):
    """Una falla después de cargar el catálogo revierte toda la creación."""
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.commit()

        def fail_mapping(_company, _catalog):
            assert database.session.execute(database.select(Accounts).filter_by(entity="CSVFAIL")).first()
            raise DefaultAccountError("mapping invalidado durante la carga")

        monkeypatch.setattr(service, "apply_catalog_default_mapping", fail_mapping)
        with pytest.raises(ValueError, match="mapping invalidado"):
            finalize_setup(
                {
                    "id": "CSVFAIL",
                    "razon_social": "CSV Company SA",
                    "id_fiscal": "J-FAIL",
                    "moneda": "NIO",
                    "pais": "NI",
                    "inicio_anio_fiscal": date(2026, 1, 1),
                    "fin_anio_fiscal": date(2026, 12, 31),
                },
                "preexistente",
                "NI",
                "es",
                "base_es.csv",
            )
        assert database.session.execute(database.select(Entity).filter_by(code="CSVFAIL")).first() is None
        assert database.session.execute(database.select(Book).filter_by(entity="CSVFAIL")).first() is None
        assert database.session.execute(database.select(Accounts).filter_by(entity="CSVFAIL")).first() is None
        database.session.remove()
        database.engine.dispose()
