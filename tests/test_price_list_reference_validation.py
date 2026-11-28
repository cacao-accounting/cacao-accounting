# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2010: las listas de precios validan compañía y moneda antes de guardar.

#2301: la batería restaura el estado compartido del worker aunque falle.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, PriceList, database
from cacao_accounting.i18n import _

RUTA = "/settings/price-lists"


@pytest.fixture
def admin_de_configuracion(app, entorno_contable):
    """Habilita el módulo admin y restaura su estado original al salir."""
    with app.app_context():
        row = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        original = (True, bool(row.enabled)) if row is not None else (False, None)
        if row is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            row.enabled = True
        database.session.commit()

    created_names: list[str] = []
    try:
        yield entorno_contable, created_names
    finally:
        with app.app_context():
            for name in created_names:
                rows = database.session.execute(database.select(PriceList).filter_by(name=name)).scalars().all()
                for pl in rows:
                    database.session.delete(pl)
            row = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            existed, enabled = original
            if not existed and row is not None:
                database.session.delete(row)
            elif row is not None and enabled is not None:
                row.enabled = enabled
            database.session.commit()


@pytest.mark.parametrize(
    ("company", "currency", "mensaje_key"),
    [
        ("NOPE", "NIO", "La compañía seleccionada no existe."),
        ("cacao", "NOPE", "La moneda seleccionada no existe o no está activa."),
    ],
)
def test_lista_de_precios_rechaza_referencias_inexistentes(
    admin_de_configuracion, authenticated_client, company, currency, mensaje_key
):
    """Compañía o moneda inexistente redirige sin crear la lista."""
    entorno, created_names = admin_de_configuracion
    nombre = f"Lista invalida {uuid4().hex[:8]}"
    created_names.append(nombre)
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        RUTA,
        data={"name": nombre, "company": company, "currency": currency, "is_active": "on"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "alert-danger" in html
    with entorno.app.app_context():
        esperado = _(mensaje_key)
    assert esperado in html
    with entorno.app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is None


def test_lista_de_precios_persiste_referencias_validas(admin_de_configuracion, authenticated_client):
    """Control positivo: compañía y moneda existentes crean la lista."""
    entorno, created_names = admin_de_configuracion
    nombre = f"Lista valida {uuid4().hex[:8]}"
    created_names.append(nombre)
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        RUTA,
        data={"name": nombre, "company": "cacao", "currency": "NIO", "is_active": "on"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    with entorno.app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is not None
