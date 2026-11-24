# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1962: las casillas de estado inactivo se interpretan por presencia."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Tax, TaxTemplate, database


@pytest.fixture
def admin_modulo(app):
    """Habilita el módulo administrativo y restaura su estado previo."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        creado = modulo is None
        anterior = None if creado else modulo.enabled
        if modulo is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            modulo.enabled = True
        database.session.commit()
    try:
        yield
    finally:
        with app.app_context():
            modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if modulo is not None:
                if creado:
                    database.session.delete(modulo)
                else:
                    modulo.enabled = anterior
                database.session.commit()


@pytest.mark.parametrize(("casilla", "esperado"), [(None, False), ("on", True)])
def test_impuesto_respeta_la_casilla_de_estado(app, admin_modulo, authenticated_client, casilla, esperado):
    """Sin checkbox el impuesto nace inactivo; con checkbox, activo."""
    del admin_modulo
    nombre = f"Impuesto casilla {uuid4().hex[:8]}"
    datos = {"name": nombre, "rate": "10", "tax_type": "percentage", "applies_to": "both"}
    if casilla is not None:
        datos["is_active"] = casilla

    response = authenticated_client("admin").post("/settings/taxes", data=datos)

    assert response.status_code == 302
    with app.app_context():
        impuesto = database.session.execute(database.select(Tax).filter_by(name=nombre)).scalar_one()
        assert impuesto.is_active is esperado
        database.session.delete(impuesto)
        database.session.commit()


@pytest.mark.parametrize(("casilla", "esperado"), [(None, False), ("on", True)])
def test_plantilla_fiscal_respeta_la_casilla_de_estado(app, admin_modulo, authenticated_client, casilla, esperado):
    """La plantilla sigue la misma semántica de presencia del checkbox."""
    del admin_modulo
    nombre = f"Plantilla casilla {uuid4().hex[:8]}"
    datos = {"name": nombre, "company": "cacao", "template_type": "selling"}
    if casilla is not None:
        datos["is_active"] = casilla

    response = authenticated_client("admin").post("/settings/tax-templates", data=datos)

    assert response.status_code == 302
    with app.app_context():
        plantilla = database.session.execute(database.select(TaxTemplate).filter_by(name=nombre)).scalar_one()
        assert plantilla.is_active is esperado
        database.session.delete(plantilla)
        database.session.commit()
