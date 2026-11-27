# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2356: dos años fiscales solapados no pueden confirmarse a la vez."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from time import sleep
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.routes import _fiscal_year_range_conflicts
from cacao_accounting.database import Currency, Entity, FiscalYear, database

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'fiscal-year.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2356",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str) -> str:
    company = f"F{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()
        database.session.remove()
    return company


def test_dos_anios_solapados_no_confirman(tmp_path):
    """Dos rangos que se solapan dejan exactamente un año fiscal."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    company = _seed(app, suffix)
    barrier = Barrier(2, timeout=30)

    def create(name: str, start: date, end: date) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                if _fiscal_year_range_conflicts(company, start, end):
                    return "rechazado"
                # Mantiene abierta la transacción para exponer la carrera.
                sleep(0.5)
                database.session.add(
                    FiscalYear(
                        entity=company,
                        name=name,
                        year_start_date=start,
                        year_end_date=end,
                        is_closed=False,
                    )
                )
                database.session.commit()
                return "creado"
            except Exception:
                database.session.rollback()
                return "error"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda args: create(*args),
                    [
                        (f"{suffix}-A", date(2026, 1, 1), date(2026, 12, 31)),
                        (f"{suffix}-B", date(2026, 6, 1), date(2027, 5, 31)),
                    ],
                )
            )
        assert sorted(results) == ["creado", "rechazado"], results
        with app.app_context():
            years = database.session.execute(database.select(FiscalYear).filter_by(entity=company)).scalars().all()
            assert len(years) == 1
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
