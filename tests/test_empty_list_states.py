# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los listados vacíos comunican el estado y paginan de forma coherente.

Escenario de negocio (issues #2049, #2048 y #2046): una búsqueda sin
resultados dejaba el cuerpo de la tabla vacío y el paginador mostraba
«Página 1 de 0». La persona usuaria no sabía si la búsqueda falló, si no hay
datos o si carece de alcance sobre la compañía.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, UserCompanyAccess, database


@pytest.fixture
def cliente_estado_vacio():
    """App aislada para que las pruebas de listas no hereden el estado del worker."""
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
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        database.session.commit()

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    yield client
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _assert_estado_vacio(client, url: str, mensaje: str) -> None:
    respuesta = client.get(url)

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert mensaje in html
    assert "0 items encontrados" in html
    assert "Página 1 de 0" not in html


def test_busqueda_de_clientes_sin_resultados(cliente_estado_vacio):
    """El listado de clientes explica que el filtro no encontró filas."""
    _assert_estado_vacio(
        cliente_estado_vacio,
        "/sales/customer/list?search=NO-SUCH-CUSTOMER",
        "No se encontraron clientes para los filtros seleccionados.",
    )


def test_busqueda_de_lotes_sin_resultados(cliente_estado_vacio):
    """El listado de lotes muestra el estado vacío con mensaje traducible."""
    _assert_estado_vacio(
        cliente_estado_vacio,
        "/inventory/batch/list?search=NO-SUCH-BATCH",
        "No se encontraron lotes para los filtros seleccionados.",
    )


def test_lista_de_bodegas_sin_alcance(cliente_estado_vacio):
    """Una lista de bodegas vacía comunica el alcance y no muestra Página 1 de 0."""
    _assert_estado_vacio(
        cliente_estado_vacio,
        "/inventory/warehouse/list",
        "No hay bodegas para los filtros o el alcance de compañía actual.",
    )


def test_la_paginacion_vacia_omite_la_pagina(app):
    """Sin resultados solo se informa el total, sin una página inexistente."""
    with app.test_request_context("/"):
        macro = app.jinja_env.get_template("macros.html").module.rendizar_paginacion
        html = macro(
            consulta=SimpleNamespace(total=0, page=1, pages=0, has_prev=False, has_next=False),
            vista="cacao_app.pagina_inicio",
        )

    assert "0 items encontrados" in html
    assert "Página" not in html
