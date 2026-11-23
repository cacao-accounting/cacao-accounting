# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1911: las tablas fiscales de administración muestran etiquetas traducidas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Tax, TaxTemplate, TaxTemplateItem, database

FONDOS: list[tuple[str, str, str]] = []


@pytest.fixture
def admin_modulo(app):
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
        for tax_id, template_id, item_id in FONDOS:
            item = database.session.get(TaxTemplateItem, item_id)
            if item is not None:
                database.session.delete(item)
            template = database.session.get(TaxTemplate, template_id)
            if template is not None:
                database.session.delete(template)
            tax = database.session.get(Tax, tax_id)
            if tax is not None:
                database.session.delete(tax)
        database.session.commit()
        FONDOS.clear()


def _datos_fiscales(admin_modulo) -> tuple[Tax, TaxTemplate]:
    """Crea un impuesto porcentual y una plantilla de compra con una fila."""
    del admin_modulo
    sufijo = uuid4().hex[:8]
    with database.session.begin():
        impuesto = Tax(
            name=f"Impuesto {sufijo}",
            tax_type="percentage",
            applies_to="both",
            rate=10,
            is_active=True,
        )
        plantilla = TaxTemplate(
            name=f"Plantilla {sufijo}",
            company="cacao",
            template_type="buying",
            is_active=True,
        )
        database.session.add_all([impuesto, plantilla])
        database.session.flush()
        item = TaxTemplateItem(
            tax_template_id=plantilla.id,
            tax_id=impuesto.id,
            sequence=10,
            calculation_base="net_document",
            behavior="additive",
        )
        database.session.add(item)
        database.session.flush()
        FONDOS.append((impuesto.id, plantilla.id, item.id))
    return impuesto, plantilla


def test_lista_de_impuestos_traduce_tipo_y_aplicacion(app, authenticated_client, admin_modulo):
    """La tabla no imprime los códigos ``percentage``/``both``."""
    impuesto, _ = _datos_fiscales(admin_modulo)
    client = authenticated_client("admin")

    response = client.get("/settings/taxes")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f"{impuesto.name}</td><td>Porcentaje" in body
    assert "<td>Compra y venta</td>" in body


def test_plantilla_y_filas_traducen_tipo_base_y_comportamiento(app, authenticated_client, admin_modulo):
    """Plantilla e ítems muestran Compra, Documento neto y Aditivo."""
    _, plantilla = _datos_fiscales(admin_modulo)
    client = authenticated_client("admin")

    listado = client.get("/settings/tax-templates")
    items = client.get(f"/settings/tax-templates/{plantilla.id}/items")

    assert listado.status_code == 200
    assert f"{plantilla.name}</td><td>Compra</td>" in listado.get_data(as_text=True)
    assert items.status_code == 200
    assert "<td>Documento neto</td><td>Aditivo</td>" in items.get_data(as_text=True)
