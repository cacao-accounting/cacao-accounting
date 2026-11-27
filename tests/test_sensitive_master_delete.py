# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2322: libros y años fiscales no se borran físicamente desde la UI."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    User,
    UserCompanyAccess,
    database,
)


def _crear_app(cloud: bool = False) -> Flask:
    """Crea una app aislada con controles internos activos y dos compañías."""
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
            "MODO_ESCRITORIO": not cloud,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=True, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(id="admin", user="admin", name="Admin", password=b"x", active=True, classification="admin"),
                Entity(
                    code="A",
                    name="Compañía A",
                    company_name="Razón A",
                    tax_id="TAX-A",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="B",
                    name="Compañía B",
                    company_name="Razón B",
                    tax_id="TAX-B",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                UserCompanyAccess(user_id="admin", company_code="A"),
            ]
        )
        database.session.commit()
        database.session.add_all(
            [
                Book(code="LIBROA", name="Libro A", entity="A", currency="NIO", status="activo", is_primary=True),
                Book(code="LIBROB", name="Libro B", entity="B", currency="NIO", status="activo", is_primary=True),
                FiscalYear(
                    entity="A",
                    name="EJERCICIO-A",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                ),
                FiscalYear(
                    entity="B",
                    name="EJERCICIO-B",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                ),
            ]
        )
        database.session.commit()
    return application


def _cerrar_app(application: Flask) -> None:
    """Libera la sesión y el motor SQLite de una aplicación de prueba."""
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def application() -> Iterator[Flask]:
    """Proporciona el escenario HTTP aislado."""
    app = _crear_app()
    try:
        yield app
    finally:
        _cerrar_app(app)


def _cliente(application: Flask) -> FlaskClient:
    """Autentica un administrador sin pasar por el formulario de acceso."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _mensaje_proteccion(respuesta) -> bool:
    """El rechazo controlado aparece en el contenido renderizado."""
    return "es un maestro protegido" in respuesta.get_data(as_text=True)


def test_libro_sin_dependencias_no_se_borra(application):
    """Un libro sin movimientos responde con error controlado y persiste."""
    respuesta = _cliente(application).post("/accounting/book/delete/LIBROA", follow_redirects=True)

    assert respuesta.status_code == 200
    assert _mensaje_proteccion(respuesta)
    with application.app_context():
        assert database.session.execute(database.select(Book).filter_by(code="LIBROA")).scalar_one_or_none() is not None


def test_anio_fiscal_sin_dependencias_no_se_borra(application):
    """Un año fiscal sin períodos responde con error controlado y persiste."""
    with application.app_context():
        exercise = database.session.execute(database.select(FiscalYear).filter_by(name="EJERCICIO-A")).scalar_one()
        exercise_id = exercise.id

    respuesta = _cliente(application).post(f"/accounting/fiscal_year/{exercise_id}/delete", follow_redirects=True)

    assert respuesta.status_code == 200
    assert _mensaje_proteccion(respuesta)
    with application.app_context():
        assert database.session.get(FiscalYear, exercise_id) is not None


def test_anio_fiscal_con_dependencias_no_se_borra(application):
    """La dependencia se informa sin borrar el año ni el período."""
    with application.app_context():
        exercise = database.session.execute(database.select(FiscalYear).filter_by(name="EJERCICIO-A")).scalar_one()
        database.session.add(
            AccountingPeriod(
                entity="A",
                fiscal_year_id=exercise.id,
                name="2026-01",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
            )
        )
        database.session.commit()
        exercise_id = exercise.id

    respuesta = _cliente(application).post(f"/accounting/fiscal_year/{exercise_id}/delete", follow_redirects=True)

    assert respuesta.status_code == 200
    assert "existen dependencias" in respuesta.get_data(as_text=True)
    with application.app_context():
        assert database.session.get(FiscalYear, exercise_id) is not None


def test_borrado_de_compania_ajena_se_rechaza():
    """En Cloud el acceso parcial impide borrar un libro ajeno."""
    application = _crear_app(cloud=True)
    try:
        respuesta = _cliente(application).post("/accounting/book/delete/LIBROB", follow_redirects=False)

        assert respuesta.status_code == 403
        with application.app_context():
            assert database.session.execute(database.select(Book).filter_by(code="LIBROB")).scalar_one_or_none() is not None
    finally:
        _cerrar_app(application)
