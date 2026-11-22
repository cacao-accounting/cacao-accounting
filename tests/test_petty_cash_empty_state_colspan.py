# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1975: el estado vacío de Caja Chica abarca todas las columnas.

Una celda de estado vacío con un ``colspan`` distinto al número de encabezados
deja la tabla desalineada. La regresión renderiza el listado real sin registros
en una base aislada y compara ambos valores.
"""

from __future__ import annotations

import re

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    User,
    database,
)

MENSAJE_VACIO = "No hay cajas chicas registradas."
RUTA = "/cash_management/petty-cash/list"


@pytest.fixture
def app_caja_chica_vacia():
    """App aislada, sin cajas chicas, con un administrador autenticable."""
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
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="cash", default=False, enabled=True),
                User(
                    user="admin",
                    name="Admin",
                    password=b"test-password",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_estado_vacio_de_caja_chica_abarca_todas_las_columnas(app_caja_chica_vacia):
    """El ``colspan`` del mensaje coincide con los encabezados de la tabla."""
    application = app_caja_chica_vacia
    with application.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user_id, auth_version = usuario.id, usuario.auth_version

    cliente = application.test_client()
    with cliente.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    respuesta = cliente.get(RUTA)

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    celda = re.search(rf'<td colspan="(\d+)"[^>]*>\s*{re.escape(MENSAJE_VACIO)}', html)
    assert celda is not None, "El listado vacío debe mostrar su mensaje de estado vacío."

    tabla = html[: celda.start()].rsplit("<table", 1)[-1]
    encabezados = len(re.findall(r"<th\b", tabla))
    assert int(celda.group(1)) == encabezados
