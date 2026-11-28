# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión HTTP de validación y borrado de entidades (#1768, #1769).

Las colisiones de identidad deben volver al formulario sin modificar la fila,
incluso cuando cada campo coincide con una entidad distinta. Cloud rechaza el
borrado con un mensaje controlado y no ofrece la acción en la interfaz.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, UserCompanyAccess, database


def _crear_app(cloud: bool = False) -> tuple[Flask, dict[str, str]]:
    """Crea una aplicación aislada con tres entidades sin dependencias."""
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
            "INTERNAL_CONTROLS_ENFORCE": cloud,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Entity(
                    code="A",
                    name="Comercial A",
                    company_name="Razón A",
                    tax_id="TAX-A",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="B",
                    name="Comercial B",
                    company_name="Razón B",
                    tax_id="TAX-B",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="C",
                    name="Comercial C",
                    company_name="Razón C",
                    tax_id="TAX-C",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                UserCompanyAccess(user_id="admin", company_code="A"),
            ]
        )
        database.session.commit()
        ids = {entity.code: entity.id for entity in database.session.execute(database.select(Entity)).scalars().all()}
    return application, ids


def _cerrar_app(application: Flask) -> None:
    """Libera la sesión y el motor SQLite de una aplicación de prueba."""
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def application() -> Iterator[tuple[Flask, dict[str, str]]]:
    """Proporciona el escenario HTTP de escritorio para las pruebas de edición."""
    app_and_ids = _crear_app()
    try:
        yield app_and_ids
    finally:
        _cerrar_app(app_and_ids[0])


def _cliente(application: Flask) -> FlaskClient:
    """Autentica un administrador sin pasar por el formulario de acceso."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _formulario(**overrides: str) -> dict[str, str]:
    """Construye el formulario de la entidad A con modificaciones opcionales."""
    datos = {
        "id_fiscal": "TAX-A",
        "nombre_comercial": "Comercial A",
        "razon_social": "Razón A",
        "habilitado": "on",
    }
    datos.update(overrides)
    return datos


def _assert_entidad_a_intacta(application: Flask) -> None:
    """Verifica que un rechazo de edición no haya mutado la entidad A."""
    with application.app_context():
        entidad = database.session.execute(database.select(Entity).filter_by(code="A")).scalar_one()
        assert (
            entidad.tax_id,
            entidad.company_name,
            entidad.name,
            entidad.enabled,
            entidad.status,
        ) == ("TAX-A", "Razón A", "Comercial A", True, "activo")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id_fiscal", "TAX-B"),
        ("razon_social", "Razón B"),
    ],
)
def test_edicion_con_identidad_duplicada_no_responde_500(application, campo, valor):
    """Una colisión de tax_id o razón social vuelve al formulario."""
    app, _ids = application
    client = _cliente(app)
    respuesta = client.post(
        "/accounting/entity/edit/A",
        data=_formulario(**{campo: valor}, nombre_comercial="Comercial editada"),
    )

    assert respuesta.status_code == 200
    assert "Ya existe otra entidad con esa identificación fiscal o razón social." in respuesta.get_data(as_text=True)
    _assert_entidad_a_intacta(app)


def test_edicion_con_colision_simultanea_no_responde_500(application):
    """Campos que colisionan con entidades distintas siguen dando un error controlado."""
    app, _ids = application
    client = _cliente(app)
    respuesta = client.post(
        "/accounting/entity/edit/A",
        data=_formulario(
            id_fiscal="TAX-B",
            razon_social="Razón C",
            nombre_comercial="Comercial editada",
        ),
    )

    assert respuesta.status_code == 200
    assert "Ya existe otra entidad con esa identificación fiscal o razón social." in respuesta.get_data(as_text=True)
    _assert_entidad_a_intacta(app)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id_fiscal", ""),
        ("razon_social", ""),
        ("id_fiscal", "   "),
        ("razon_social", "   "),
    ],
)
def test_edicion_exige_identidad_minima(application, campo, valor):
    """El servidor no acepta identificación o razón social vacías."""
    app, _ids = application
    client = _cliente(app)
    respuesta = client.post(
        "/accounting/entity/edit/A",
        data=_formulario(**{campo: valor}, nombre_comercial="Comercial editada"),
    )

    assert respuesta.status_code == 200
    assert "La identificación fiscal y la razón social son obligatorias." in respuesta.get_data(as_text=True)
    _assert_entidad_a_intacta(app)


def test_edicion_valida_se_guarda(application):
    """Una identidad libre sigue actualizando la entidad."""
    app, _ids = application
    client = _cliente(app)
    respuesta = client.post(
        "/accounting/entity/edit/A",
        data=_formulario(id_fiscal="TAX-A2", razon_social="Razón A2", nombre_comercial="Comercial A2"),
    )

    assert respuesta.status_code == 302
    with app.app_context():
        entidad = database.session.execute(database.select(Entity).filter_by(code="A")).scalar_one()
        assert entidad.tax_id == "TAX-A2"
        assert entidad.company_name == "Razón A2"
        assert entidad.name == "Comercial A2"


def test_entidad_inexistente_responde_404(application):
    """Editar un código ausente no desreferencia None."""
    app, _ids = application
    client = _cliente(app)

    assert client.get("/accounting/entity/edit/NO-EXISTE").status_code == 404


def test_borrado_cloud_se_rechaza_controladamente():
    """El guard sensible se traduce a mensaje y la fila sin dependencias permanece."""
    app, ids = _crear_app(cloud=True)
    try:
        client = _cliente(app)
        respuesta = client.post(f"/accounting/entity/delete/{ids['C']}", follow_redirects=True)

        assert respuesta.status_code == 200
        assert "La eliminación de entidades no está disponible en modo Cloud; utilice Inactivar." in respuesta.get_data(
            as_text=True
        )
        with app.app_context():
            entidad = database.session.get(Entity, ids["C"])
            assert entidad is not None
            assert (entidad.tax_id, entidad.company_name, entidad.enabled) == ("TAX-C", "Razón C", True)
    finally:
        _cerrar_app(app)


def test_el_boton_de_borrado_no_se_muestra_en_cloud():
    """Cloud no ofrece una acción que el guard rechazará."""
    app, _ids = _crear_app(cloud=True)
    try:
        client = _cliente(app)
        respuesta = client.get("/accounting/entity/C")

        assert respuesta.status_code == 200
        assert "/accounting/entity/delete/" not in respuesta.get_data(as_text=True)
    finally:
        _cerrar_app(app)
