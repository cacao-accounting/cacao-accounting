# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Estado vacío accesible en los listados de Ventas.

Escenario de negocio: un usuario abre un listado de Ventas con el alcance y
filtros actuales sin resultados. La tabla debe explicar que no hay documentos
para esos filtros, no mostrar solo un encabezado vacío.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database

CONTRASENA = "listas-vacias-2026"
MENSAJE = "No se encontraron documentos para los filtros seleccionados."


@pytest.fixture
def ventas_sin_documentos():
    """Cloud de Ventas sin documentos de negocio."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "ruta",
    [
        "/sales/quotation/list",
        "/sales/sales-invoice/list",
        "/sales/sales-order/list",
        "/sales/sales-request/list",
        "/sales/delivery-note/list",
        "/sales/sales-invoice/debit-note/list",
        "/sales/sales-invoice/return/list",
    ],
)
def test_listado_vacio_explica_el_resultado(ventas_sin_documentos, ruta):
    """Cada listado vacío muestra el mensaje dentro de la tabla."""
    client = ventas_sin_documentos.test_client()
    _iniciar(client)

    response = client.get(ruta)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE in cuerpo
    assert 'role="status"' in cuerpo
