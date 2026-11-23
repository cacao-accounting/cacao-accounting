# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2009: las casillas de venta y vigencia de listas de precios se respetan."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, PriceList, database


@pytest.fixture
def admin_modulo(app):
    """Habilita el módulo administrativo necesario para la ruta."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            modulo.enabled = True
        database.session.commit()


@pytest.mark.parametrize(
    ("datos_casillas", "esperado"),
    [
        ({}, (False, False)),
        ({"is_selling": "y", "is_active": "y"}, (True, True)),
    ],
)
def test_checkbox_omitido_o_marcado_se_persiste(
    app, entorno_contable, admin_modulo, authenticated_client, datos_casillas, esperado
):
    """La ausencia de la casilla equivale a desmarcada; su envío la activa."""
    del entorno_contable
    del admin_modulo
    nombre = f"Lista {uuid4().hex[:8]}"
    datos = {
        "name": nombre,
        "company": "cacao",
        "currency": "NIO",
        **datos_casillas,
    }

    response = authenticated_client("admin").post("/settings/price-lists", data=datos)

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        lista = database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one()
        assert (lista.is_selling, lista.is_active) == esperado
        database.session.delete(lista)
        database.session.commit()
