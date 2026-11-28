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


def test_companias_distintas_no_se_bloquean(tmp_path):
    """Dos compañías pueden crear rangos solapados entre sí."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    company_a = _seed(app, suffix)
    company_b = f"G{suffix}"
    with app.app_context():
        database.session.add_all(
            [
                Currency(code=f"D{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company_b,
                    name=f"Empresa B {suffix}",
                    company_name=f"Empresa B {suffix} SA",
                    tax_id=f"U{suffix}",
                    currency=f"D{suffix}",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()
        database.session.remove()
    barrier = Barrier(2, timeout=30)

    def create(company: str, name: str) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                if _fiscal_year_range_conflicts(company, date(2026, 1, 1), date(2026, 12, 31)):
                    return "rechazado"
                database.session.add(
                    FiscalYear(
                        entity=company,
                        name=name,
                        year_start_date=date(2026, 1, 1),
                        year_end_date=date(2026, 12, 31),
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
            results = list(workers.map(lambda args: create(*args), ((company_a, f"{suffix}-A"), (company_b, f"{suffix}-B"))))
        assert results == ["creado", "creado"]
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_rangos_adyacentes_son_validos(tmp_path):
    """Un rango que empieza al día siguiente no es un solapamiento."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    company = _seed(app, suffix)
    with app.app_context():
        assert _fiscal_year_range_conflicts(company, date(2026, 1, 1), date(2026, 12, 31)) is False
        database.session.add(
            FiscalYear(entity=company, name=f"{suffix}-1", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31))
        )
        database.session.commit()
        assert _fiscal_year_range_conflicts(company, date(2027, 1, 1), date(2027, 12, 31)) is False
        database.session.add(
            FiscalYear(entity=company, name=f"{suffix}-2", year_start_date=date(2027, 1, 1), year_end_date=date(2027, 12, 31))
        )
        database.session.commit()
        years = database.session.execute(database.select(FiscalYear).filter_by(entity=company)).scalars().all()
        assert len(years) == 2
        database.session.remove()
        database.engine.dispose()


def test_ediciones_concurrentes_no_solapan(tmp_path):
    """Dos ediciones que se expanden al rango ajeno dejan una sola válida."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    company = _seed(app, suffix)
    with app.app_context():
        first = FiscalYear(
            entity=company,
            name=f"{suffix}-A",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 2, 28),
        )
        second = FiscalYear(
            entity=company,
            name=f"{suffix}-B",
            year_start_date=date(2026, 5, 1),
            year_end_date=date(2026, 6, 30),
        )
        database.session.add_all([first, second])
        database.session.commit()
        first_id, second_id = first.id, second.id
        database.session.remove()
    barrier = Barrier(2, timeout=30)

    def edit(year_id: str, start: date, end: date) -> str:
        with app.app_context():
            try:
                year = database.session.get(FiscalYear, year_id)
                barrier.wait(timeout=10)
                if _fiscal_year_range_conflicts(year.entity, start, end, exclude_fiscal_year_id=year.id):
                    return "rechazado"
                year.year_start_date = start
                year.year_end_date = end
                database.session.commit()
                return "editado"
            except Exception:
                database.session.rollback()
                return "error"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda args: edit(*args),
                    ((first_id, date(2026, 1, 1), date(2026, 4, 30)), (second_id, date(2026, 3, 1), date(2026, 6, 30))),
                )
            )
        assert sorted(results) == ["editado", "rechazado"], results
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
