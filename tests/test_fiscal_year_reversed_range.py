# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1974: el CRUD rechaza un año fiscal con rango invertido."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import FiscalYear, database


def test_anio_fiscal_invertido_no_se_persiste(app, authenticated_client, entorno_contable):
    """El POST con fin anterior al inicio no crea el registro."""
    datos = {
        "id": "FY-INVERTIDO",
        "entidad": "cacao",
        "inicio": "2026-12-31",
        "fin": "2026-01-01",
    }
    respuesta = authenticated_client("admin").post("/accounting/fiscal_year/new", data=datos)

    assert respuesta.status_code == 200
    with app.app_context():
        creados = database.session.execute(database.select(FiscalYear).filter_by(name="FY-INVERTIDO")).scalars().all()
        assert creados == []


def test_editar_anio_fiscal_invertido_conserva_rango_original(app, authenticated_client, entorno_contable):
    """La ruta de edición rechaza el rango invertido sin modificar el año existente."""
    nombre = f"FY-EDITAR-{uuid4().hex[:10]}"
    with app.app_context():
        fiscal_year = FiscalYear(
            entity="cacao",
            name=nombre,
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add(fiscal_year)
        database.session.commit()
        fiscal_year_id = fiscal_year.id

    respuesta = authenticated_client("admin").post(
        f"/accounting/fiscal_year/{fiscal_year_id}/edit",
        data={
            "id": nombre,
            "entidad": "cacao",
            "inicio": "2026-12-31",
            "fin": "2026-01-01",
        },
    )

    assert respuesta.status_code == 200
    with app.app_context():
        guardado = database.session.get(FiscalYear, fiscal_year_id)
        assert guardado is not None
        assert guardado.year_start_date == date(2026, 1, 1)
        assert guardado.year_end_date == date(2026, 12, 31)
        database.session.delete(guardado)
        database.session.commit()


def test_editar_anio_cerrado_financieramente_no_cambia_fechas(app, authenticated_client, entorno_contable):
    """A fiscally closed year keeps its historical date range after an edit POST."""
    del entorno_contable
    fiscal_year_id = None
    try:
        with app.app_context():
            fiscal_year = FiscalYear(
                entity="cacao",
                name=f"FY-CERRADO-{uuid4().hex[:10]}",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=True,
                financial_closed=True,
            )
            database.session.add(fiscal_year)
            database.session.commit()
            fiscal_year_id = fiscal_year.id
            fiscal_year_name = fiscal_year.name

        response = authenticated_client("admin").post(
            f"/accounting/fiscal_year/{fiscal_year_id}/edit",
            data={
                "id": fiscal_year_name,
                "entidad": "cacao",
                "inicio": "2025-01-01",
                "fin": "2025-12-31",
                "cerrado": "y",
            },
        )

        assert response.status_code == 302
        with app.app_context():
            saved = database.session.get(FiscalYear, fiscal_year_id)
            assert saved is not None
            assert saved.year_start_date == date(2026, 1, 1)
            assert saved.year_end_date == date(2026, 12, 31)
            assert saved.financial_closed is True
    finally:
        if fiscal_year_id:
            with app.app_context():
                saved = database.session.get(FiscalYear, fiscal_year_id)
                if saved is not None:
                    database.session.delete(saved)
                    database.session.commit()


def test_crear_anio_fiscal_rechaza_superposicion_y_permite_rangos_adyacentes(app, authenticated_client, entorno_contable):
    """Creation rejects inclusive overlaps but allows consecutive calendar days."""
    del entorno_contable
    prefix = uuid4().hex[:10]
    base_name = f"FY-BASE-{prefix}"
    overlap_name = f"FY-OVERLAP-{prefix}"
    adjacent_name = f"FY-ADJACENT-{prefix}"
    created_names = [base_name, overlap_name, adjacent_name]
    try:
        with app.app_context():
            database.session.add(
                FiscalYear(
                    entity="cacao",
                    name=base_name,
                    year_start_date=date(2040, 1, 1),
                    year_end_date=date(2040, 12, 31),
                )
            )
            database.session.commit()

        overlap_response = authenticated_client("admin").post(
            "/accounting/fiscal_year/new",
            data={
                "id": overlap_name,
                "entidad": "cacao",
                "inicio": "2040-07-01",
                "fin": "2041-06-30",
            },
        )
        assert overlap_response.status_code == 200

        adjacent_response = authenticated_client("admin").post(
            "/accounting/fiscal_year/new",
            data={
                "id": adjacent_name,
                "entidad": "cacao",
                "inicio": "2041-01-01",
                "fin": "2041-12-31",
            },
        )
        assert adjacent_response.status_code == 302

        with app.app_context():
            saved = (
                database.session.execute(database.select(FiscalYear).where(FiscalYear.name.in_([overlap_name, adjacent_name])))
                .scalars()
                .all()
            )
            assert {year.name for year in saved} == {adjacent_name}
    finally:
        with app.app_context():
            database.session.execute(database.delete(FiscalYear).where(FiscalYear.name.in_(created_names)))
            database.session.commit()


def test_editar_anio_fiscal_rechaza_superposicion_inclusiva(app, authenticated_client, entorno_contable):
    """Editing cannot make the last date overlap the next fiscal year start."""
    del entorno_contable
    prefix = uuid4().hex[:10]
    first_name = f"FY-FIRST-{prefix}"
    next_name = f"FY-NEXT-{prefix}"
    fiscal_year_id = None
    try:
        with app.app_context():
            fiscal_year = FiscalYear(
                entity="cacao",
                name=first_name,
                year_start_date=date(2042, 1, 1),
                year_end_date=date(2042, 12, 30),
            )
            next_year = FiscalYear(
                entity="cacao",
                name=next_name,
                year_start_date=date(2042, 12, 31),
                year_end_date=date(2043, 12, 30),
            )
            database.session.add_all([fiscal_year, next_year])
            database.session.commit()
            fiscal_year_id = fiscal_year.id

        response = authenticated_client("admin").post(
            f"/accounting/fiscal_year/{fiscal_year_id}/edit",
            data={
                "id": first_name,
                "entidad": "cacao",
                "inicio": "2042-01-01",
                "fin": "2042-12-31",
            },
        )
        assert response.status_code == 200

        with app.app_context():
            saved = database.session.get(FiscalYear, fiscal_year_id)
            assert saved is not None
            assert saved.year_start_date == date(2042, 1, 1)
            assert saved.year_end_date == date(2042, 12, 30)
    finally:
        with app.app_context():
            database.session.execute(database.delete(FiscalYear).where(FiscalYear.name.in_([first_name, next_name])))
            database.session.commit()
