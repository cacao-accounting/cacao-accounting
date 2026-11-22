# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2010: las listas de precios validan compañía y moneda antes de guardar.

Un system admin podía enviar referencias inexistentes: el ``flush`` fallaba
por FK y la ruta respondía 500. La regresión exige una redirección controlada
sin persistencia y conserva el alta válida como control positivo.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, PriceList, database

RUTA = "/settings/price-lists"


@pytest.fixture
def admin_de_configuracion(app, entorno_contable):
    """Habilita el módulo de administración y devuelve credenciales de compañía."""
    with app.app_context():
        if database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none() is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
            database.session.commit()
    return entorno_contable


@pytest.mark.parametrize(
    ("company", "currency", "mensaje"),
    [
        ("NOPE", "NIO", "La compañía seleccionada no existe."),
        ("cacao", "NOPE", "La moneda seleccionada no existe o no está activa."),
    ],
)
def test_lista_de_precios_rechaza_referencias_inexistentes(
    admin_de_configuracion, authenticated_client, company, currency, mensaje
):
    """Compañía o moneda inexistente redirige sin crear la lista."""
    nombre = f"Lista inválida {uuid4().hex[:8]}"
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        RUTA,
        data={"name": nombre, "company": company, "currency": currency, "is_active": "on"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with admin_de_configuracion.app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is None


def test_lista_de_precios_persiste_referencias_validas(admin_de_configuracion, authenticated_client):
    """Control positivo: compañía y moneda existentes crean la lista."""
    nombre = f"Lista válida {uuid4().hex[:8]}"
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        RUTA,
        data={"name": nombre, "company": "cacao", "currency": "NIO", "is_active": "on"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    with admin_de_configuracion.app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is not None
