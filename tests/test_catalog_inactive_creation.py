# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1720: los catálogos respetan el checkbox Activo al crear."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, PriceList, Tax, TaxTemplate, database


@pytest.fixture
def admin_habilitado(app):
    """Habilita el módulo administrativo que el fixture base no siembra."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            module.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        for model in (Tax, TaxTemplate, PriceList):
            database.session.execute(database.delete(model).where(model.name.like("QA3-%")))
        database.session.commit()


def _crear(client, ruta: str, datos: dict[str, str]):
    return client.post(ruta, data=datos)


@pytest.mark.parametrize(
    ("ruta", "modelo", "datos"),
    [
        ("/settings/taxes", Tax, {"tax_type": "percentage", "rate": "10"}),
        ("/settings/tax-templates", TaxTemplate, {"company": "cacao", "template_type": "selling"}),
        ("/settings/price-lists", PriceList, {"company": "cacao", "currency": "NIO"}),
    ],
)
def test_catalogo_sin_checkbox_queda_inactivo(app, authenticated_client, admin_habilitado, ruta, modelo, datos):
    """Omitir is_active (checkbox desmarcado) persiste inactivo."""
    del admin_habilitado
    nombre = f"QA3-inactivo-{uuid4().hex[:6]}"
    client = authenticated_client("admin")

    response = _crear(client, ruta, {"name": nombre, **datos})

    assert response.status_code == 302
    with app.app_context():
        fila = database.session.execute(database.select(modelo).filter_by(name=nombre)).scalar_one()
        assert fila.is_active is False


@pytest.mark.parametrize(
    ("ruta", "modelo", "datos"),
    [
        ("/settings/taxes", Tax, {"tax_type": "percentage", "rate": "10"}),
        ("/settings/tax-templates", TaxTemplate, {"company": "cacao", "template_type": "selling"}),
        ("/settings/price-lists", PriceList, {"company": "cacao", "currency": "NIO"}),
    ],
)
def test_catalogo_con_checkbox_queda_activo(app, authenticated_client, admin_habilitado, ruta, modelo, datos):
    """Marcar el checkbox persiste activo."""
    del admin_habilitado
    nombre = f"QA3-activo-{uuid4().hex[:6]}"
    client = authenticated_client("admin")

    response = _crear(client, ruta, {"name": nombre, "is_active": "on", **datos})

    assert response.status_code == 302
    with app.app_context():
        fila = database.session.execute(database.select(modelo).filter_by(name=nombre)).scalar_one()
        assert fila.is_active is True
