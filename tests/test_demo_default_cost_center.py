# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2169: MAIN es el único centro de costo predeterminado canónico."""

from __future__ import annotations

import os
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.budget_service import BudgetService
from cacao_accounting.database import CostCenter, Currency, Entity, database
from cacao_accounting.datos.dev import cargar_centros_de_costos, demo_entidad
from cacao_accounting.datos.dev.data import _make_centros_de_costos


def test_los_centros_demo_no_son_default() -> None:
    """El seed demo no introduce defaults competidores ni agrupadores default."""
    centros = _make_centros_de_costos()
    assert not [centro for centro in centros if centro.default]
    for entidad in ("CACAO", "CAFE", "DULCE"):
        assert any(centro.entity == entidad and not centro.group and centro.active and centro.enabled for centro in centros)


def _sembrar_centros(app, company: str, *, main_default: bool = False) -> None:
    """Crea MAIN, centros demo y candidatos legacy no canónicos."""
    with app.app_context():
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía {company}",
                company_name=f"Compañía {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.add(
            Entity(
                code=f"{company}-O",
                name="Otra compañía",
                company_name="Otra compañía SA",
                tax_id=f"TAX-{company}-O",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            CostCenter(
                entity=company,
                code="MAIN",
                name="Centro principal",
                group=False,
                default=main_default,
                active=True,
                enabled=True,
            )
        )
        for centro in _make_centros_de_costos():
            if centro.entity == "CACAO":
                centro.entity = company
                database.session.add(centro)
        database.session.add_all(
            [
                CostCenter(
                    entity=company,
                    code="GRUPO",
                    name="Agrupador heredado",
                    group=True,
                    default=True,
                    active=True,
                    enabled=True,
                ),
                CostCenter(
                    entity=company,
                    code="INA",
                    name="Centro inactivo",
                    group=False,
                    default=True,
                    active=False,
                    enabled=True,
                ),
                CostCenter(
                    entity=company,
                    code="DIS",
                    name="Centro deshabilitado",
                    group=False,
                    default=True,
                    active=True,
                    enabled=False,
                ),
                CostCenter(
                    entity=f"{company}-O",
                    code="AJENA",
                    name="Default de otra compañía",
                    group=False,
                    default=True,
                    active=True,
                    enabled=True,
                ),
            ]
        )
        database.session.commit()


def _limpiar(app, company: str) -> None:
    """Retira las compañías y sus centros al finalizar la prueba."""
    with app.app_context():
        database.session.execute(database.delete(CostCenter).where(CostCenter.entity.in_((company, f"{company}-O"))))
        database.session.execute(database.delete(Entity).where(Entity.code.in_((company, f"{company}-O"))))
        database.session.commit()


def test_resolver_usa_main_posteable_aun_sin_default(app) -> None:
    """MAIN gana aunque otro centro posteable sea el único default heredado."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    with app.app_context():
        otro = database.session.execute(database.select(CostCenter).filter_by(entity=company, code="A00000")).scalar_one()
        otro.default = True
        database.session.commit()
    try:
        with app.app_context():
            servicio = BudgetService()
            assert servicio.resolve_cost_center("", company).code == "MAIN"
            assert servicio.resolve_cost_center("", company).code == "MAIN"
    finally:
        _limpiar(app, company)


@pytest.mark.parametrize("codigo", ["GRUPO", "INA", "DIS"])
def test_default_no_posteable_no_se_resuelve(app, codigo) -> None:
    """Un default que es agrupador, inactivo o deshabilitado no se selecciona."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    try:
        with app.app_context():
            for centro in database.session.execute(
                database.select(CostCenter).filter_by(entity=company, default=True)
            ).scalars():
                centro.default = centro.code == codigo
            principal = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="MAIN")
            ).scalar_one()
            principal.active = False
            database.session.commit()
        with app.app_context():
            assert BudgetService().resolve_cost_center("", company) is None
    finally:
        _limpiar(app, company)


def test_resolver_no_cruza_companias_sin_candidato_local(app) -> None:
    """El default de otra compañía no resuelve un centro local ausente."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    try:
        with app.app_context():
            for centro in database.session.execute(
                database.select(CostCenter).filter_by(entity=company, default=True)
            ).scalars():
                centro.default = False
            principal = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="MAIN")
            ).scalar_one()
            principal.active = False
            database.session.commit()
        with app.app_context():
            assert BudgetService().resolve_cost_center("", company) is None
    finally:
        _limpiar(app, company)


def test_resolver_legacy_es_determinista_por_codigo(app) -> None:
    """Sin MAIN posteable, el fallback elige el default posteable menor por código."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    try:
        with app.app_context():
            principal = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="MAIN")
            ).scalar_one()
            principal.active = False
            for centro in database.session.execute(
                database.select(CostCenter).filter_by(entity=company, default=True)
            ).scalars():
                centro.default = False
            for code in ("Z99999", "M99999"):
                database.session.add(
                    CostCenter(
                        entity=company,
                        code=code,
                        name=f"Legacy {code}",
                        group=False,
                        default=True,
                        active=True,
                        enabled=True,
                    )
                )
            heredado = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="A00000")
            ).scalar_one()
            heredado.default = True
            database.session.commit()
        with app.app_context():
            resultado = BudgetService().resolve_cost_center("", company)
            assert resultado is not None
            assert resultado.code == "A00000"
    finally:
        _limpiar(app, company)


def test_seed_demo_crea_un_main_posteable_por_compania() -> None:
    """El seed real crea MAIN sin defaults competidores en cada compañía demo."""
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
            database.session.add_all(
                [
                    Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                    Currency(code="USD", name="Dólar", decimals=2, active=True),
                    Currency(code="EUR", name="Euro", decimals=2, active=True),
                ]
            )
            database.session.commit()
            demo_entidad()
            cargar_centros_de_costos()
            companias = database.session.execute(database.select(Entity.code)).scalars().all()
            assert {"CACAO", "CAFE", "DULCE"}.issubset(set(companias))
            for company in ("CACAO", "CAFE", "DULCE"):
                defaults = (
                    database.session.execute(database.select(CostCenter).filter_by(entity=company, default=True))
                    .scalars()
                    .all()
                )
                assert [centro.code for centro in defaults] == ["MAIN"]
                assert defaults[0].group is False
                assert defaults[0].active is True
                assert defaults[0].enabled is True
                assert BudgetService().resolve_cost_center("", company).code == "MAIN"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.database
def test_seed_demo_postgresql_crea_un_main_posteable_por_compania() -> None:
    """El seed real resuelve MAIN en PostgreSQL, sin defaults competidores."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("postgresql"):
        pytest.skip("Este caso valida el orden de lectura de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    schema_name = f"demo_default_cc_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri)
    with bootstrap_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    engine_options: Any = {"pool_size": 4, "max_overflow": 0, "connect_args": {"options": f"-csearch_path={schema_name}"}}
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": cast(Any, engine_options),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    try:
        with application.app_context():
            database.create_all()
            database.session.add_all(
                [
                    Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                    Currency(code="USD", name="Dólar", decimals=2, active=True),
                    Currency(code="EUR", name="Euro", decimals=2, active=True),
                ]
            )
            database.session.commit()
            demo_entidad()
            cargar_centros_de_costos()
            for company in ("CACAO", "CAFE", "DULCE"):
                defaults = (
                    database.session.execute(database.select(CostCenter).filter_by(entity=company, default=True))
                    .scalars()
                    .all()
                )
                assert [centro.code for centro in defaults] == ["MAIN"]
                assert defaults[0].group is False
                assert defaults[0].active is True
                assert defaults[0].enabled is True
                assert BudgetService().resolve_cost_center("", company).code == "MAIN"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        bootstrap_engine.dispose()
