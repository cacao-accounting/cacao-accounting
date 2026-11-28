# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1745: la plantilla fiscal rechaza base y comportamiento inválidos."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Tax, TaxTemplate, TaxTemplateItem, database


@pytest.fixture
def plantilla_fiscal(app):
    """Habilita admin y crea un impuesto y una plantilla de venta."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            module.enabled = True
        sufijo = uuid4().hex[:8]
        impuesto = Tax(name=f"Impuesto plantilla {sufijo}", tax_type="percentage", applies_to="sales", rate=15)
        plantilla = TaxTemplate(name=f"Plantilla {sufijo}", company="cacao", template_type="selling")
        database.session.add_all([impuesto, plantilla])
        database.session.commit()
        ids = {"tax": impuesto.id, "template": plantilla.id}
    yield ids
    with app.app_context():
        database.session.execute(database.delete(TaxTemplateItem).where(TaxTemplateItem.tax_template_id == ids["template"]))
        plantilla = database.session.get(TaxTemplate, ids["template"])
        if plantilla is not None:
            database.session.delete(plantilla)
        impuesto = database.session.get(Tax, ids["tax"])
        if impuesto is not None:
            database.session.delete(impuesto)
        database.session.commit()


def _post(client, template_id: str, **extra: str):
    """Envía el alta de una fila de plantilla."""
    datos = {
        "sequence": "10",
        "calculation_base": "net_document",
        "behavior": "additive",
    }
    datos.update(extra)
    return client.post(f"/settings/tax-templates/{template_id}/items", data=datos)


@pytest.mark.parametrize(
    "campo",
    [
        {"behavior": "deductiv"},
        {"behavior": "sumativo"},
        {"calculation_base": "previous-total"},
        {"calculation_base": "base_inventada"},
    ],
)
def test_valores_invalidos_no_se_persisten(app, authenticated_client, plantilla_fiscal, campo):
    """Un valor fuera del contrato no altera el signo ni la base del impuesto."""
    client = authenticated_client("admin")

    response = _post(client, plantilla_fiscal["template"], tax_id=plantilla_fiscal["tax"], **campo)

    assert response.status_code == 302
    with app.app_context():
        filas = (
            database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=plantilla_fiscal["template"]))
            .scalars()
            .all()
        )
        assert filas == []


def test_valores_validos_se_persisten(app, authenticated_client, plantilla_fiscal):
    """La combinación deducible con total previo sigue admitida."""
    client = authenticated_client("admin")

    response = _post(
        client,
        plantilla_fiscal["template"],
        tax_id=plantilla_fiscal["tax"],
        calculation_base="previous_total",
        behavior="deductive",
    )

    assert response.status_code == 302
    with app.app_context():
        fila = database.session.execute(
            database.select(TaxTemplateItem).filter_by(tax_template_id=plantilla_fiscal["template"])
        ).scalar_one()
        assert (fila.calculation_base, fila.behavior) == ("previous_total", "deductive")
