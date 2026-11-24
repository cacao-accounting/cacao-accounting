# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2012: las pantallas de matching hidratan la configuración persistida.

Al seleccionar una compañía con reglas guardadas, compras y ventas deben
prefilar tolerancias, modos y checkboxes en lugar de mostrar los valores por
defecto y sobrescribir la política existente al guardar.
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    CompanyDefaultAccount,
    Entity,
    Modules,
    PurchaseMatchingConfig,
    SalesMatchingConfig,
    database,
)

CAMPOS_COMPRAS = (
    "matching_type",
    "price_tolerance_type",
    "price_tolerance_value",
    "qty_tolerance_type",
    "qty_tolerance_value",
)


def _input(cuerpo: str, name: str) -> str:
    """Devuelve la etiqueta input del campo indicado."""
    coincidencia = re.search(rf"<input[^>]*name=\"{name}\"[^>]*>", cuerpo)
    assert coincidencia is not None, f"No se encontró el input {name}."
    return coincidencia.group(0)


def _select(cuerpo: str, name: str, value: str) -> str:
    """Devuelve la opción seleccionada del select indicado."""
    coincidencia = re.search(rf"<option value=\"{value}\" selected>", cuerpo)
    assert coincidencia is not None, f"La opción {name}={value} no está seleccionada."
    return coincidencia.group(0)


@pytest.fixture
def matching_hidratado(app):
    """Compañía aislada con configuración de compras y ventas persistida."""
    sufijo = uuid4().hex[:6]
    company = f"h{sufijo}"
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
        else:
            creado = False
            anterior = modulo.enabled
            modulo.enabled = True
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía {company}",
                company_name=f"Compañía {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                PurchaseMatchingConfig(
                    company=company,
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("5"),
                    qty_tolerance_type="absolute",
                    qty_tolerance_value=Decimal("3"),
                    require_purchase_order=False,
                    bridge_account_required=False,
                    auto_reconcile=False,
                    allow_price_difference=True,
                ),
                SalesMatchingConfig(
                    company=company,
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("4.5"),
                    require_sales_order=False,
                    allow_price_difference=True,
                ),
                CompanyDefaultAccount(company=company, apply_advances_automatically=True),
            ]
        )
        database.session.commit()
    yield company
    with app.app_context():
        database.session.execute(database.delete(CompanyDefaultAccount).where(CompanyDefaultAccount.company == company))
        database.session.execute(database.delete(PurchaseMatchingConfig).where(PurchaseMatchingConfig.company == company))
        database.session.execute(database.delete(SalesMatchingConfig).where(SalesMatchingConfig.company == company))
        database.session.execute(database.delete(Entity).where(Entity.code == company))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def test_compras_hidrata_configuracion_existente(app, authenticated_client, matching_hidratado):
    """El formulario de compras refleja la fila guardada, no los valores por defecto."""
    response = authenticated_client("admin").get(f"/settings/purchase-reconciliation?company={matching_hidratado}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Editar configuración" in cuerpo
    assert "Nueva configuración" not in cuerpo
    _select(cuerpo, "matching_type", "2-way")
    _select(cuerpo, "price_tolerance_type", "absolute")
    _select(cuerpo, "qty_tolerance_type", "absolute")
    assert 'value="5.0000"' in _input(cuerpo, "price_tolerance_value")
    assert 'value="3.0000"' in _input(cuerpo, "qty_tolerance_value")
    assert "checked" not in _input(cuerpo, "require_purchase_order")
    assert "checked" not in _input(cuerpo, "bridge_account_required")
    assert "checked" not in _input(cuerpo, "auto_reconcile")
    assert "checked" in _input(cuerpo, "allow_price_difference")
    assert "checked" in _input(cuerpo, "apply_advances_automatically")


def test_ventas_hidrata_configuracion_existente(app, authenticated_client, matching_hidratado):
    """El formulario de ventas refleja la fila guardada, no los valores por defecto."""
    response = authenticated_client("admin").get(f"/settings/sales-matching?company={matching_hidratado}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Editar configuración" in cuerpo
    assert "Nueva configuración" not in cuerpo
    _select(cuerpo, "matching_type", "2-way")
    _select(cuerpo, "price_tolerance_type", "absolute")
    assert 'value="4.5000"' in _input(cuerpo, "price_tolerance_value")
    assert "checked" not in _input(cuerpo, "require_sales_order")
    assert "checked" in _input(cuerpo, "allow_price_difference")
