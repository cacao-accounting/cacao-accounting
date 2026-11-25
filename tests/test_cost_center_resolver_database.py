# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2169: la prioridad de MAIN se verifica también en los motores de CI."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.budget_service import BudgetService
from cacao_accounting.database import CostCenter, Currency, Entity, database

pytestmark = pytest.mark.database


def _motor_externo() -> str:
    """Devuelve la URI externa de CI o omite la prueba en SQLite."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        pytest.skip("La prioridad del resolvedor se verifica en PostgreSQL y MySQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    return uri


def test_main_posteable_gana_sobre_default_legacy_en_motor_externo() -> None:
    """La prioridad canónica no depende del orden de inserción del motor."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": _motor_externo(),
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 2, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    sufijo = uuid4().hex[:6].upper()
    company = f"CC-{sufijo}"
    try:
        with application.app_context():
            database.create_all()
            if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
                database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True))
                database.session.flush()
            database.session.add(
                Entity(
                    code=company,
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()
            database.session.add_all(
                [
                    CostCenter(
                        entity=company,
                        code="ZZ9999",
                        name="Default legacy",
                        group=False,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="GRUPO",
                        name="Agrupador",
                        group=True,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="MAIN",
                        name="Principal",
                        group=False,
                        default=False,
                        active=True,
                        enabled=True,
                    ),
                ]
            )
            database.session.commit()
            assert BudgetService().resolve_cost_center("", company).code == "MAIN"
    finally:
        with application.app_context():
            database.session.execute(database.delete(CostCenter).where(CostCenter.entity == company))
            database.session.execute(database.delete(Entity).where(Entity.code == company))
            database.session.commit()
            database.session.remove()
            database.engine.dispose()


def test_fallback_legacy_es_determinista_en_motor_externo() -> None:
    """Con MAIN no posteable, gana el default posteable menor por código."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": _motor_externo(),
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 2, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    sufijo = uuid4().hex[:6].upper()
    company = f"CC-{sufijo}"
    try:
        with application.app_context():
            database.create_all()
            if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
                database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True))
                database.session.flush()
            database.session.add(
                Entity(
                    code=company,
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()
            # MAIN es agrupador y no puede resolverse como centro implícito.
            # El candidato menor se inserta al final para exigir ORDER BY.
            database.session.add_all(
                [
                    CostCenter(
                        entity=company,
                        code="MAIN",
                        name="Principal no posteable",
                        group=True,
                        default=False,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="ZZ9999",
                        name="Legacy alto",
                        group=False,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="MM9999",
                        name="Legacy medio",
                        group=False,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="AA9999",
                        name="Legacy menor",
                        group=False,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="GRUPO",
                        name="Agrupador default",
                        group=True,
                        default=True,
                        active=True,
                        enabled=True,
                    ),
                    CostCenter(
                        entity=company,
                        code="INA",
                        name="Default inactivo",
                        group=False,
                        default=True,
                        active=False,
                        enabled=True,
                    ),
                ]
            )
            database.session.commit()
            assert BudgetService().resolve_cost_center("", company).code == "AA9999"
    finally:
        with application.app_context():
            database.session.execute(database.delete(CostCenter).where(CostCenter.entity == company))
            database.session.execute(database.delete(Entity).where(Entity.code == company))
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
